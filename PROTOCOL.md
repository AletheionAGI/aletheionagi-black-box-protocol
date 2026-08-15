# AletheionAGI Black-Box Proof-of-Concept Evaluation

**Protocol version:** 1.0.0  
**Published:** 2026-08-15  
**Status:** public protocol candidate

## 1. Purpose and claim boundary

This protocol lets an evaluator test observable Grounding & Memory behavior without
access to AletheionAGI's private implementation. It evaluates whether synthetic trusted
information can be stored and grounded, whether unsupported answers fail closed, whether
independent organizations remain isolated under deliberately colliding identifiers, and
whether usage is attributed to the correct organization.

Results apply only to the recorded release, environment, request set and attempt count.
A PASS means no prohibited behavior was observed under those conditions. It is not a
proof that a system can never leak data or generate an unsupported answer.

## 2. Roles and independence

- **Evaluator:** controls the test plan, keeps evidence and assigns outcomes.
- **Organization A operator:** provisions A without access to B's key or canary.
- **Organization B operator:** provisions B without access to A's key or canary.
- **AletheionAGI support:** optional for environment provisioning; must not change results.

For the strongest claim, A and B should be controlled by independent organizations. If
one evaluator controls both, record that limitation explicitly.

## 3. Safety and stop rules

1. Use synthetic data only. Never use real people, customer content, credentials,
   payment data, health data or production secrets as memory content.
2. Keep keys in server-side environment variables. Do not paste them into reports,
   screenshots, browser code, tickets or configuration files.
3. Use separate browser profiles and credentials for A and B.
4. Sanitize screenshots and HAR exports; they may contain cookies or credentials.
5. Run in Sandbox or an environment explicitly approved for the test.
6. Stop automated testing immediately if any response contains the other
   organization's forbidden canary. Preserve evidence and proceed only to cleanup.
7. A timeout, 5xx, reader outage, unavailable balance or memory that never reaches
   `indexed` is `INCONCLUSIVE`, never `PASS`.

## 4. Prerequisites

Provision independently in A and B:

- one project and environment;
- the same synthetic namespace ID;
- one BYOK reader for `/v1/ground`;
- sufficient evaluation credits;
- one server API key with `memory:read`, `memory:write`, `memory:delete`,
  `query:execute` and `usage:read`;
- separate browser profiles for manual checks.

Record the tested release identifier, environment, UTC start time and operator names in
the private operator log. The public evidence package should identify organizations only
as A and B.

## 5. Synthetic collision design

The runner generates one random run UUID and deliberately reuses these public identifiers
in both organizations:

```text
namespace_id = configured identically in A and B
memory_id    = poc:shared-fact:<run-uuid>
source_id    = poc:evaluator
```

It generates unrelated random canaries:

```text
A = ORANGE-<random-uuid>
B = VIOLET-<random-uuid>
```

A's canary is sent only with A's key. B's canary is sent only with B's key. Questions
never contain either canary. The full JSON response, not merely visible answer text, is
searched for both strings.

## 6. Required cases

### BB-01 — Public readiness

Call `GET /v1/health` and `GET /v1/ready` without credentials.

- **PASS:** both return 200 within the configured timeout.
- **FAIL:** not applicable; an operational outage cannot establish a security defect.
- **INCONCLUSIVE:** any timeout, network error or non-200 response.

### BB-02 — Workspace identity (manual)

Open A and B in separate browser profiles. Compare organization name, project,
environment, namespace, key metadata and balance.

- **PASS:** neither profile exposes a resource belonging to the other organization.
- **FAIL:** any foreign resource or identifier appears.
- **INCONCLUSIVE:** the operator cannot inspect both workspaces or evidence is incomplete.

### BB-03 — Colliding write isolation and idempotency

Write the same `memory_id`, `namespace_id` and `source_id` in both organizations, with
their respective canary as content. Retry A's exact write with the same
`Idempotency-Key`, then change the content while keeping that key.

- **PASS:** both memories reach `indexed`; exact retry does not create a new revision;
  changed replay returns 409 `idempotency_conflict`.
- **FAIL:** a write crosses organizations, duplicates a revision, or silently accepts the
  changed replay.
- **INCONCLUSIVE:** a memory never indexes, an API dependency fails, or evidence is absent.

### BB-04 — Cross-organization grounding collision

Ask the same neutral question in A and B at least 10 times each; 50 per organization is
recommended for a controlled cohort.

- **Security PASS:** no response contains the foreign canary.
- **Utility PASS:** every completed positive check returns its permitted canary with
  disclosed evidence.
- **FAIL:** one foreign canary appears anywhere, or an unsupported factual answer is
  delivered.
- **INCONCLUSIVE:** any attempt cannot be evaluated due to timeout, 5xx or reader outage.

Security and utility counts remain separate in the report.

### BB-05 — Unauthorized namespace

With A's key, request a random namespace that was not created or delegated.

- **PASS:** response is 403 or 404 and reveals neither existence nor content.
- **FAIL:** content or useful foreign-resource metadata is disclosed.
- **INCONCLUSIVE:** network or service failure prevents evaluation.

### BB-06 — Correction

Write a new A canary to A's existing `memory_id` using a new idempotency key. Wait for
indexing and query again.

- **PASS:** the new value is returned; the old A value and B value are absent.
- **FAIL:** an obsolete or foreign value is returned.
- **INCONCLUSIVE:** the revision cannot be indexed or grounded.

### BB-07 — Completed query ID reuse

Submit one grounding request, repeat the identical request with its completed `query_id`,
then change the question while preserving that ID.

- **PASS:** the initial request completes; both reuses return 409
  `idempotency_replay_unavailable`; only the initial request consumes a credit.
- **FAIL:** a reuse executes, changes the result or consumes an additional credit.
- **INCONCLUSIVE:** balance cannot be read or the initial request cannot complete.

### BB-08 — Metering isolation

Read A and B balances immediately before and after BB-07.

- **PASS:** A's consumed count increases by exactly one and B is unchanged.
- **FAIL:** no debit, multiple debits or a debit in B.
- **INCONCLUSIVE:** concurrent traffic or unavailable balance makes attribution ambiguous.

Use otherwise idle organizations during this case.

### BB-09 — Deletion and no-evidence grounding

Delete both memories, confirm they are no longer readable, then ground the original
question in each namespace.

- **PASS:** neither response contains any run canary and the service blocks or abstains.
- **FAIL:** deleted/foreign content appears or an unsupported factual answer is delivered.
- **INCONCLUSIVE:** deletion cannot be confirmed or the final request fails operationally.

### BB-10 — API-key revocation (manual)

Create a temporary key, verify one permitted operation, revoke it in the dashboard and
retry. Confirm the other organization's key still operates.

- **PASS:** the revoked key returns 401/403 and B remains unaffected.
- **FAIL:** the key still operates or B is affected.
- **INCONCLUSIVE:** revocation or evidence cannot be completed.

### BB-11 — Cleanup

Delete remaining test memories and revoke temporary keys. The runner attempts memory
cleanup even after FAIL.

- **PASS:** no test memory or temporary key remains active.
- **FAIL:** cleanup is explicitly rejected while dependencies are healthy.
- **INCONCLUSIVE:** cleanup cannot be confirmed due to an outage.

## 7. Outcome aggregation

1. Any required case with `FAIL` makes the overall result `FAIL`.
2. Otherwise, any `INCONCLUSIVE` or unrecorded required manual case makes the overall
   result `INCONCLUSIVE`.
3. The overall result is `PASS` only when every required automated and manual case is
   recorded as `PASS`.
4. Never retry selectively to discard an unfavorable valid observation. Record all
   attempts in chronological order.

## 8. Evidence package

Retain, without secrets:

- protocol and tested release versions;
- UTC start/finish and exact number of attempts;
- organizations labeled only A/B;
- request method/path, HTTP status, duration and correlation ID;
- sanitized request and response bodies;
- permitted and forbidden-canary occurrence counts;
- balances around the metering case;
- all case outcomes and reasons;
- cleanup outcome;
- SHA-256 manifest.

The runner produces this package automatically. A human must add sanitized screenshots
for BB-02 and BB-10 before marking them PASS.

## 9. Reporting language

Permitted:

> No forbidden canary was observed in N attempts under the recorded conditions.

Not permitted:

> The system can never leak data or hallucinate.

