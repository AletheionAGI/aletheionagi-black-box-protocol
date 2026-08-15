"""NeMo Guardrails self-check-facts wrapper using NVIDIA's hosted model API."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys


PROMPT = """Determine whether the hypothesis is fully supported by the evidence. Use only the evidence. Answer only yes or no.
Evidence: {{ evidence }}
Hypothesis: {{ response }}
Supported:"""


def build_evaluator():
    from langchain_nvidia_ai_endpoints import ChatNVIDIA
    from nemoguardrails import RailsConfig
    from nemoguardrails.library.self_check.facts.actions import self_check_facts
    from nemoguardrails.llm.taskmanager import LLMTaskManager

    if not os.getenv("NVIDIA_API_KEY"):
        raise RuntimeError("NVIDIA_API_KEY is not configured")
    model = os.getenv("NEMO_NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
    config = RailsConfig.from_content(
        yaml_content=f"""
models:
  - type: main
    engine: nvidia_ai_endpoints
    model: {model}
prompts:
  - task: self_check_facts
    max_tokens: 3
    content: |-
      {PROMPT.replace(chr(10), chr(10) + '      ')}
"""
    )
    manager = LLMTaskManager(config)
    llm = ChatNVIDIA(model=model, temperature=0, max_completion_tokens=3)

    def evaluate(request):
        accuracy = asyncio.run(
            self_check_facts(
                manager,
                context={
                    "relevant_chunks": request.get("relevant_chunks", []),
                    "bot_message": request["response"],
                },
                llm=llm,
                config=config,
            )
        )
        score = float(accuracy)
        threshold = float(os.getenv("NEMO_FACT_CHECK_THRESHOLD", "0.5"))
        return {"accuracy": score, "blocked": score < threshold}

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
