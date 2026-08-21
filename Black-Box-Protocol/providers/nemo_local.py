"""NeMo Guardrails self-check-facts wrapper using NVIDIA's hosted model API."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time


PROMPT = """Determine whether the hypothesis is fully supported by the evidence. Use only the evidence. Answer only yes or no.
Evidence: {{ evidence }}
Hypothesis: {{ response }}
Supported:"""


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    value = float(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _is_rate_limit_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        status = getattr(current, "status_code", None)
        response = getattr(current, "response", None)
        response_status = getattr(response, "status_code", None)
        message = str(current).lower()
        if status == 429 or response_status == 429 or "429" in message or "too many requests" in message:
            return True
        current = current.__cause__ or current.__context__
    return False


class RateLimitedEvaluator:
    """Serialize, pace and retry hosted evaluations without changing their result."""

    def __init__(self, evaluate):
        self.evaluate = evaluate
        self.minimum_interval = _env_float("NEMO_MIN_REQUEST_INTERVAL_SECONDS", 1.5)
        self.max_retries = _env_int("NEMO_RATE_LIMIT_MAX_RETRIES", 8)
        self.backoff_base = _env_float("NEMO_RATE_LIMIT_BACKOFF_SECONDS", 2.0, 0.1)
        self.backoff_max = _env_float("NEMO_RATE_LIMIT_MAX_BACKOFF_SECONDS", 60.0, 0.1)
        self.last_started_at: float | None = None

    def __call__(self, request):
        for attempt in range(self.max_retries + 1):
            if self.last_started_at is not None:
                remaining = self.minimum_interval - (time.monotonic() - self.last_started_at)
                if remaining > 0:
                    time.sleep(remaining)
            self.last_started_at = time.monotonic()
            try:
                return self.evaluate(request)
            except Exception as exc:
                if not _is_rate_limit_error(exc) or attempt == self.max_retries:
                    raise
                delay = min(self.backoff_max, self.backoff_base * (2**attempt))
                delay *= random.uniform(0.85, 1.15)
                print(
                    f"[nemo] rate limited; retry {attempt + 1}/{self.max_retries} "
                    f"in {delay:.1f}s",
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(delay)


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

    return RateLimitedEvaluator(evaluate)


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
