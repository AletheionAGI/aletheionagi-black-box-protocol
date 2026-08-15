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

```powershell
Copy-Item config.example.json config.json
python -m aletheion_black_box plan --config config.json
python -m aletheion_black_box run --config config.json --execute
```

For a source checkout without installation, set `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH = "src"
python -m aletheion_black_box plan --config config.example.json
```

Or install the local CLI:

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
