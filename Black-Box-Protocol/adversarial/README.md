# AletheionAGI Adversarial Testing

This directory integrates the official Strix CLI exclusively for authorized testing of
AletheionAGI-owned infrastructure. It is a separate adversarial layer, not a target in
the vendor-neutral grounding benchmark. It must never be pointed at competitors or
third-party systems.

The wrapper accepts only three exact HTTPS hostnames: `aletheionagi.com`,
`www.aletheionagi.com`, and `api.aletheionagi.com`. Suffix lookalikes, arbitrary
subdomains, credentials in URLs, non-default ports, query strings and fragments are
rejected. The initial target is validated locally; the scope instructs Strix to stop if
it encounters an external redirect because redirects followed internally by an
external process cannot be intercepted by this wrapper.

## Safe dry-run

Set `STRIX_TARGET` and run:

```powershell
python scripts/run_strix_smoke.py
python scripts/run_strix_aletheion.py --dry-run
```

Dry-run is the default and sends no traffic. It records the detected CLI version,
sanitized command, scope hash, OpenAPI hash when supplied, and readiness state under
`results/strix/<timestamp>/`.

## Explicit execution gate

A real run requires all of the following:

- an exact allowlisted target;
- `STRIX_ENABLED=true`;
- `STRIX_AUTHORIZATION_ACK=true`;
- `STRIX_LLM` and `STRIX_LLM_API_KEY`;
- the official `strix` executable on `PATH`;
- the explicit `--execute` CLI flag.

```powershell
python scripts/run_strix_aletheion.py --execute
```

The wrapper launches `strix` without a shell, uses quick/non-interactive mode, applies a
timeout, and stores sanitized stdout/stderr separately. Exit code 2 means the official
headless CLI reported vulnerabilities; it still produces only review-required output.
Nothing is automatically classified as confirmed without human reproduction and a
proof of concept.

### Install Strix separately

Strix is not a package dependency of this benchmark. Its official installer currently
requires a shell environment, a running Docker installation and an LLM provider key:

```bash
curl -sSL https://strix.ai/install | bash
strix --version
```

On Windows, the same official PyPI package can be installed in an isolated tool
environment when `uv` is available:

```powershell
uv tool install strix-agent
strix --version
```

The optional OpenAPI file is validated, hashed and supplied as an additional `--target`
before the allowlisted live base URL. This follows the official API-testing example;
the wrapper never invents or augments a specification.

Official references:

- [Strix CLI reference](https://docs.strix.ai/usage/cli)
- [Official Strix repository](https://github.com/usestrix/strix)
