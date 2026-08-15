# Black-Box Protocol completion roadmap

This roadmap separates implementation completeness from experimental results. Missing
credentials or provider packages must produce `SKIPPED`; they must never be replaced by
simulated provider outcomes.

## Completed implementation

- [x] Common target interface and normalized result schema.
- [x] Frozen, SHA-256-attested corpus and scoring policy.
- [x] Capability-aware scoring and separate integration-complexity reporting.
- [x] AletheionAGI, Patronus Lynx, NeMo Guardrails, Guardrails AI and Galileo adapters.
- [x] Explicit `--runs`, category filtering and opt-in `--include-galileo` cohort switch.
- [x] AletheionAGI request/response contract aligned with the public protocol runner.
- [x] Per-case AletheionAGI provisioning manifest required, including namespace,
  authorized/unauthorized evidence digests and explicit isolation controls.
- [x] Strix allowlist, authorization gates, safe dry-run and separate reporting.
- [x] Build artifacts, caches, secrets and generated results excluded from Git.

## Local release gate

- [x] `python -m pytest -q` passes (41 tests).
- [x] `python scripts/smoke.py` passes against the frozen FakeTarget corpus.
- [x] `python scripts/run_target.py --target fake` produces manifest, raw JSONL,
  summary and report.
- [x] `python scripts/run_strix_smoke.py` produces a sanitized dry-run package and sends
  no traffic.
- [ ] `python -m build` succeeds when the optional `build` package is installed.

The current development environment does not have the optional `build` or `ruff`
packages installed. This does not affect runtime, whose package dependencies are empty.

## External validation gate

- [ ] Provision every frozen case in controlled AletheionAGI namespaces and create the
  private manifest described below.
- [ ] Run AletheionAGI and retain the generated result package.
- [ ] Run each locally/configurably available comparison target; retain honest `SKIPPED`
  results for unavailable targets.
- [ ] Run Galileo only in a new predeclared cohort with `--include-galileo`; do not add it
  retroactively after observing first-round results.
- [ ] Install the official Strix CLI and confirm the dry-run reports its real version and
  current command. A real scan remains optional and requires explicit authorization.

## AletheionAGI provisioning manifest

Set `ALETHEION_PROVISIONING_MANIFEST` to a private JSON file. It is an operator
attestation and must not contain API keys. Each case entry has this shape:

```json
{
  "frozen_sha256": "<cases/FROZEN_MANIFEST.json combined_sha256>",
  "cases": {
    "VN-009": {
      "namespace_id": "controlled-team-a-namespace",
      "authorized_evidence_sha256": "<canonical evidence digest>",
      "unauthorized_evidence_sha256": "<canonical evidence digest>",
      "isolation_control": "team-b evidence provisioned only in a separate controlled namespace"
    }
  }
}
```

The adapter refuses to run a case whose namespace, evidence inventory or isolation
control is not attested. This prevents a nominal isolation case from passing merely
because the forbidden evidence was never provisioned.

## Definition of done

The implementation is complete when the local release gate passes. The first benchmark
cohort is complete only after its target list, versions, thresholds and configuration
are frozen before execution and all resulting `PASS`, `FAIL`, `SKIPPED` and `ERROR`
observations are retained without selective reruns.
