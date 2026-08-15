"""Guardrails AI GroundedAI hallucination validator command wrapper."""

from __future__ import annotations

import argparse
import json
import os
import sys

# The GroundedAI plugin probes CUDA during import. This wrapper is deliberately
# CPU-only so systems with CUDA libraries but no usable GPU do not select
# FlashAttention2.
os.environ["CUDA_VISIBLE_DEVICES"] = ""


def build_evaluator():
    from guardrails import Guard
    from guardrails.errors import ValidationError
    from guardrails.hub import GroundedAIHallucination

    validator = GroundedAIHallucination(quant=False, device="cpu")
    guard = Guard().use(validator)

    def evaluate(request):
        try:
            outcome = guard.validate(
                request["answer"],
                metadata={
                    "query": request["question"],
                    "reference": "\n".join(request.get("context", [])),
                },
            )
            valid = bool(outcome.validation_passed)
            output = str(outcome.validated_output or "")
        except ValidationError as exc:
            valid = False
            output = str(exc)
        return {
            "valid": valid,
            "score": 1.0 if valid else 0.0,
            "output": output,
        }

    return evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    evaluate = build_evaluator()
    if args.serve:
        for line in sys.stdin:
            try:
                response = evaluate(json.loads(line))
            except Exception as exc:
                response = {"error": f"{type(exc).__name__}: {exc}"}
            print(json.dumps(response), flush=True)
        return 0
    json.dump(evaluate(json.load(sys.stdin)), sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
