# AletheionAGI Vendor-Neutral Black-Box Protocol

The AletheionAGI Black-Box Protocol is a vendor-neutral behavioral protocol for
evaluating grounding, hallucination handling, evidence authorization, isolation and
fail-closed behavior without requiring access to a system's internal implementation.

Security and isolation tests must only be executed against environments and data the
tester owns or is explicitly authorized to test. Do not bypass authentication, inspect
private endpoints, use real tenant data or exceed provider terms and rate limits.

## First reproducible round

The default comparison contains four targets:

1. AletheionAGI public Grounding API;
2. Patronus Lynx as a local unsupported/contradiction detector;
3. NVIDIA NeMo Guardrails fact-checking rail;
4. Guardrails AI provenance/grounded-hallucination validator.

Galileo Protect is implemented as an experimental phase-2 adapter and is excluded from
the default `run_all.py` cohort. A newly pre-registered cohort can opt in with
`--include-galileo`; it must not be added retroactively after results are observed.

No overall winner is computed. Detection, scoring, validation, enforcement,
authorization, namespace isolation and evidence lifecycle remain separate capabilities.
A detector can pass an unsupported-claim case by classifying it correctly, but cannot
pass a `fail_closed` case unless it actually blocks or abstains.

For generative grounding systems, protocol 1.1 also accepts a grounded safe alternative
that omits every pre-registered forbidden-output marker. This is distinct from claiming
that the system detected the supplied unsafe candidate. Authorization cases run only
when an actual requester/label denial policy is attested; attaching an arbitrary label
without an enforcing policy is `SKIPPED`, never PASS or FAIL.

## Pre-registration and mandatory freeze

The corpus and scoring policy must be frozen **before any target is run**:

```powershell
python scripts/freeze_cases.py
```

This writes `cases/FROZEN_MANIFEST.json` containing SHA-256 hashes for:

- every JSONL case file;
- `cases/case.schema.json`;
- `protocol/scoring.py`;
- [`HYPOTHESES.md`](HYPOTHESES.md).

Every target run verifies this manifest again. If a case, schema, scoring rule or
pre-registered hypothesis changes, execution stops before another provider is called.
`--refresh` exists only for designing a new cohort before results are observed. After a
target has run, changes require a new protocol version and a new cohort; selective
reruns may not replace unfavorable valid observations.

Provider versions, thresholds and non-secret configuration are snapshotted in the run
manifest before the first case. Configuration drift during the run aborts execution.

## Differentiating cases

The frozen corpus measures systems, not only hallucination classifiers:

- sufficient versus insufficient evidence;
- a supported claim and an unsupported claim in the same answer;
- contradictory authorized sources;
- relevant evidence mixed with malicious evidence;
- perfect but unauthorized evidence;
- namespace A versus namespace B;
- partially supported responses;
- cases where abstention or fail-closed enforcement is the only acceptable behavior.

The hypotheses are recorded before results. A scientifically credible outcome may show
different strengths—for example Lynx on detection, NeMo on fact-checking and
AletheionAGI on isolation/fail-closed behavior. That is a hypothesis, not a result.

## Quick start

### 1. Configure credentials

Copy the environment template and fill at least `ALETHEION_API_KEY`,
`NVIDIA_API_KEY` and `GUARDRAILS_AI_API_KEY`. Keep `.env` private; it is ignored by
Git. The Guardrails key is needed to install its Hub validator, while its inference is
local.

```bash
cp .env.example .env
```

On PowerShell:

```powershell
Copy-Item .env.example .env
```

### 2. Install Lynx, NeMo and Guardrails AI

The setup scripts install `uv`, an isolated Python 3.12 runtime and three independent
virtual environments. They are idempotent and can be executed again safely.

Linux/macOS:

```bash
./scripts/setup.sh
```

Windows PowerShell:

```powershell
.\scripts\setup.ps1
```

The provider environments are:

- `.venv-lynx312`: PyTorch, Accelerate and Transformers 4.43.2;
- `.venv-nemo312`: NeMo Guardrails 0.17.0 and NVIDIA AI Endpoints;
- `.venv-guardrails312`: Guardrails AI 0.10.2 and the GroundedAI hallucination validator.

The first inference downloads approximately 15 GB for Patronus Lynx and 7.2 GB for
Phi-3.5, plus a small GroundedAI adapter. The tested CPU-only Lynx configuration loads
the model in FP32 and needs roughly 32 GB of available RAM. A GPU is not required.

### 3. Review and run

The shortest path performs the idempotent setup and then runs the suite:

```bash
./scripts/run.sh
```

```powershell
.\scripts\run.ps1
```

To reuse an already provisioned frozen Aletheion corpus:

```bash
./scripts/run.sh --reuse-provisioning
```

```powershell
.\scripts\run.ps1 --reuse-provisioning
```

Direct Python execution is also supported. `--execute` automatically invokes the
platform bootstrap when `uv` or any provider environment is missing:

```bash
python scripts/setup_and_run.py                 # no-traffic readiness check
python scripts/setup_and_run.py --execute       # setup, provision and run
python scripts/setup_and_run.py --execute --reuse-provisioning
```

Use `--skip-provider-setup` only when provider dependencies are managed externally.
The first execution sends real synthetic traffic, consumes Aletheion grounding credits
and makes NVIDIA API calls. Later model runs reuse the local Hugging Face cache.

The infrastructure and FakeTarget require only Python 3.11+:

```powershell
python scripts/freeze_cases.py
python scripts/smoke.py
python scripts/run_target.py --target fake
```

Lower-level target commands remain available for debugging:

```powershell
python scripts/run_all.py
python scripts/run_all.py --runs 3
python scripts/run_all.py --include-galileo
python scripts/run_target.py --target nemo_guardrails --categories unsupported_claim,insufficient_evidence,contradictory_evidence
```

Missing packages, models, credentials or unsupported capabilities are recorded as
`SKIPPED`; timeouts and provider failures are `ERROR`. Neither is converted into PASS.

## Adapter configuration

Copy `.env.example` to `.env` and fill only the targets you want to run:

```powershell
Copy-Item .env.example .env
```

Every script loads `Black-Box-Protocol/.env` automatically. Values already exported by
the parent shell take precedence, so CI can inject secrets without editing the file.
The loader performs no variable or command interpolation, `.env` is ignored by Git, and
secret values are never copied into manifests or reports.

### AletheionAGI

Set `ALETHEION_API_KEY`, `ALETHEION_CORPUS_FROZEN_SHA256` and
`ALETHEION_PROVISIONING_MANIFEST`. Generate a private manifest template with:

```powershell
python scripts/prepare_aletheion_manifest.py --output private-provisioning.json
```

After provisioning the controlled corpus, replace every namespace placeholder and add
an `isolation_control` description to the isolation cases. The adapter validates the
frozen digest and the exact authorized/unauthorized evidence inventory for every case;
it refuses nominal isolation tests lacking that attestation. See
[`ROADMAP.md`](ROADMAP.md) for the completion gates.

### Patronus Lynx

The old GitHub repository URL currently returns 404, but Patronus still publishes the
official model in its Hugging Face namespace. The default is
`PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct-v1.1`; verify its CC-BY-NC-4.0 terms for
your use. The environment is installed by the setup step; model weights are downloaded
from Hugging Face on the first inference and then reused from the local cache.

The tested CPU setup uses Python 3.12 and Transformers 4.43.2, matching the runtime
recorded by the model. The configured command is persistent so the 8B model is loaded
once per suite:

```powershell
uv venv --python 3.12 .venv-lynx312
uv pip install --python .venv-lynx312/bin/python "transformers==4.43.2" accelerate torch
$env:LYNX_COMMAND = ".venv-lynx312/bin/python providers/lynx_local.py --serve"
python scripts/run_target.py --target patronus_lynx
```

The wrapper uses Patronus's published QUESTION/DOCUMENT/ANSWER prompt and preserves
Lynx as a detector; it does not pretend Lynx provides authorization or enforcement.

### NeMo Guardrails

The included [`providers/nemo_local.py`](providers/nemo_local.py) executes NeMo's
official `self_check_facts` action with the same ordered evidence as
`$relevant_chunks`, using `NVIDIA_API_KEY` and `NEMO_NVIDIA_MODEL`. Freeze
`NEMO_FACT_CHECK_THRESHOLD` before the run. The reference default is `0.5`, matching
the documented self-check facts behavior.

### Guardrails AI

The included [`providers/guardrails_ai_local.py`](providers/guardrails_ai_local.py)
uses the official `groundedai/grounded_ai_hallucination` validator with
`microsoft/Phi-3.5-mini-instruct` on CPU. `GUARDRAILS_AI_API_KEY` is needed to install
the Hub validator; inference itself is local. Record the exact validator/package
version in `GUARDRAILS_AI_VALIDATOR`.

### Galileo Protect — phase 2

The experimental adapter uses the documented `POST /v2/protect/invoke` endpoint and
requires an explicitly configured hallucination stage. It is not part of the default
cohort and must not be added retroactively to an already observed cohort.

## Outputs

Each invocation creates:

```text
results/<timestamp>/
|-- manifest.json
|-- raw/<target>.jsonl
|-- summary.json
`-- REPORT.md
```

The report contains methodology, versions, configuration, aggregate and per-category
results, failures, skipped capabilities, latency, limitations and reproduction data. It
contains no marketing language and never announces a general winner.

### Protocol performance versus integration complexity

`Protocol Performance` contains the behavioral PASS/FAIL measurements. `Integration
Complexity` is a separate descriptive inventory of dependencies, wrappers, required
secrets, configuration items, external services, local model artifacts and setup steps.
The inventory exposes setup burden and integration friction, but it is not normalized
into an effort score and never changes a grounding outcome or competitive ranking.

Authorized adversarial testing of AletheionAGI infrastructure is documented separately
under [`adversarial/`](adversarial/README.md). Strix findings are never mixed into the
vendor-neutral competitive score.

## Official references checked for this implementation

- [Patronus Lynx model card](https://huggingface.co/PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct-v1.1)
- [NVIDIA NeMo hallucination and fact-checking rails](https://docs.nvidia.com/nemo/guardrails/configure-guardrails/guardrail-catalog/fact-checking)
- [Guardrails AI Hub](https://guardrailsai.com/hub)
- [Galileo Protect invoke API](https://docs.galileo.ai/api-reference/protect/invoke)

Security claims apply only to the recorded cases, attempts, versions and environment.
