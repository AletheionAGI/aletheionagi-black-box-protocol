# AletheionAGI Black-Box Protocol

An independent, vendor-neutral black-box proof-of-concept evaluation, with an included
reference runner for the public AletheionAGI API. It tests observable behavior only:
organization isolation, grounded-answer containment, abstention, idempotency,
correction/deletion, query replay and metering. It does not require or reveal private
architecture.

The methodology may also be used to evaluate third-party systems with the same attacks,
synthetic corpus, questions and acceptance criteria, but only within the authorization
and testing scope permitted by their operators.

The protocol uses two independent organizations and synthetic canaries. Every case has
an explicit `PASS`, `FAIL` or `INCONCLUSIVE` result. A timeout, 5xx response or missing
evidence is never treated as a pass.

## What is included

- [`PROTOCOL.md`](PROTOCOL.md): normative test method and interpretation rules.
- [`Black-Box-Protocol/`](Black-Box-Protocol/README.md): multi-target, vendor-neutral
  benchmark with a pre-registered case schema, frozen SHA-256 corpus, capability-aware
  scoring and adapters for the first open/reproducible comparison cohort.
- `aletheion-black-box`: dependency-free Python 3.11+ runner.
- [`config.example.json`](config.example.json): safe, non-secret configuration template.
- [`schemas/`](schemas): machine-readable configuration and result schemas.
- [`templates/manual-checklist.md`](templates/manual-checklist.md): the two checks that
  require a human operator (workspace UI and key revocation).
- `tests/`: offline tests for classification, sanitization and HTTP behavior.

## Safety first

Use only synthetic data. Run in Sandbox or an explicitly approved evaluation
environment. The automated suite consumes grounding credits: by default it plans 24
grounding calls when `attempts_per_organization` is 10. The runner will not send any
request unless both the configuration and command line explicitly acknowledge execution.

Never put API keys in the configuration file. Supply them through environment variables:

```powershell
$env:ALETHEION_API_KEY_A = "<organization-a-key>"
$env:ALETHEION_API_KEY_B = "<organization-b-key>"
```

## Quick start

The simplest path runs the vendor-neutral suite and automatically provisions its frozen
synthetic corpus in authorized delegated AletheionAGI namespaces:

```bash
cd Black-Box-Protocol
cp .env.example .env
# Fill the required values in .env, then review the no-traffic plan:
python scripts/setup_and_run.py
# Provision the synthetic corpus and run the suite:
python scripts/setup_and_run.py --execute
```

The dry-run must report `traffic_sent: false`. `--execute` performs real synthetic memory
writes, waits for indexing and consumes grounding credits. Use only Sandbox or another
explicitly approved environment. Generated results stay under `Black-Box-Protocol/results/`,
and the private provisioning manifest is excluded from Git.

See [`Black-Box-Protocol/.env.example`](Black-Box-Protocol/.env.example) for every
available target and [`Black-Box-Protocol/README.md`](Black-Box-Protocol/README.md) for
provider installation and configuration.

### Two-organization reference runner

The separate reference runner implements the normative two-organization evaluation in
[`PROTOCOL.md`](PROTOCOL.md):

```powershell
Copy-Item config.example.json config.json
$env:PYTHONPATH = "src"
python -m aletheion_black_box plan --config config.json
python -m aletheion_black_box run --config config.json --execute
```

It can also be installed as a local CLI:

```powershell
python -m pip install .
aletheion-black-box plan --config config.json
aletheion-black-box run --config config.json --execute
```

Before `run`, create the same synthetic namespace ID from `config.json` independently in
Organization A and Organization B, configure a BYOK reader in each environment, and give
each key the scopes listed in [`PROTOCOL.md`](PROTOCOL.md).

## Evidence

Each run creates `evidence/<run-id>/` containing:

- `exchanges.jsonl`: sanitized request/response transcript;
- `result.json`: machine-readable case outcomes;
- `report.md`: human-readable evaluation report;
- `config.sanitized.json`: effective non-secret configuration;
- `SHA256SUMS`: integrity hashes for the evidence package.

Authorization headers and environment-variable values are never written. Synthetic
canaries are intentionally retained because they are the observable isolation signal.

## Independent interpretation

The strongest permitted conclusion is scoped to the tested release and attempts:

> No forbidden canary was observed in N attempts under the recorded conditions.

Do not claim that a finite run proves leakage or hallucination can never occur.

Copyright © 2026 AletheionAGI. Licensed under the Apache License, Version 2.0.
