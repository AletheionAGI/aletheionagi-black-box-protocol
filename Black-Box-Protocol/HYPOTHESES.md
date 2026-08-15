# Pre-registered hypotheses

These hypotheses are frozen with the case corpus and scoring policy before any target is
executed. They are expectations to test, not results and not marketing claims.

1. Patronus Lynx may be strongest on pure unsupported-claim detection because it is a
   purpose-built RAG hallucination detector.
2. NeMo Guardrails may be strongest on one or more fact-checking categories when its
   evidence rail and threshold are configured well.
3. AletheionAGI may expose different behavior on authorization, namespace isolation and
   end-to-end fail-closed cases because those properties require more than output
   classification.
4. No target is expected to dominate every behavioral dimension.

The report must preserve detection, scoring, validation, enforcement, authorization,
isolation and evidence lifecycle as separate capabilities. It must not compute or
announce an overall winner automatically.
