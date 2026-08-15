# Local provider command contract

`LYNX_COMMAND`, `NEMO_GUARDRAILS_COMMAND` and `GUARDRAILS_AI_COMMAND` point to local
executables. Each executable reads one JSON object from standard input and writes one
JSON object to standard output. Logs belong on standard error. A non-zero exit is an
`ERROR`; a missing command is `SKIPPED`.

The input always includes `question`, the candidate `answer` or `response`, the same
ordered evidence text (`context` or `relevant_chunks`), `case_id`, and
`frozen_sha256`. Wrappers must not retrieve extra evidence or change thresholds after
seeing another target's output.

Expected minimum outputs:

- Lynx: `{"label":"supported|unsupported|contradictory","confidence":0.0}`
- NeMo: `{"accuracy":0.0,"blocked":true,"abstained":true}`
- Guardrails AI: `{"valid":false,"score":0.0}`

Fields unavailable from a provider must be omitted, never guessed.
