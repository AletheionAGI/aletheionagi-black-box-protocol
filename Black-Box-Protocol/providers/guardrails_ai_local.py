"""Guardrails AI GroundedAI hallucination validator command wrapper."""

from __future__ import annotations

import argparse
import copy
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
    from transformers import pipeline

    class QuietGroundedAIHallucination(GroundedAIHallucination):
        def run_model(self, query: str, response: str, reference: str = "") -> str:
            prompt = self.format_input(query, response, reference)
            messages = [{"role": "user", "content": prompt}]
            rendered_chat = self._tokenizer.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=False,
            )
            prompt_tokens = self._tokenizer(rendered_chat, add_special_tokens=False)["input_ids"]
            generation_config = copy.deepcopy(self._merged_model.generation_config)
            generation_config.max_new_tokens = None
            generation_config.max_length = len(prompt_tokens) + 2
            generation_config.temperature = 0.01
            generation_config.do_sample = True
            text_pipeline = pipeline(
                "text-generation",
                model=self._merged_model,
                device=self._device,
                tokenizer=self._tokenizer,
            )
            output = text_pipeline(
                messages,
                generation_config=generation_config,
                return_full_text=False,
                clean_up_tokenization_spaces=False,
            )
            return output[0]["generated_text"].strip().lower()

    validator = QuietGroundedAIHallucination(quant=False, device="cpu")
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
