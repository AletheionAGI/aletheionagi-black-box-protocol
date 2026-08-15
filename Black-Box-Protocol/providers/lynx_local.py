"""Opt-in local Lynx runner implementing the adapter JSON stdin/stdout contract.

This script downloads/loads an 8B model only when the operator explicitly runs it.
"""

from __future__ import annotations

import json
import os
import re
import sys
import argparse

os.environ["CUDA_VISIBLE_DEVICES"] = ""


PROMPT = """Given the following QUESTION, DOCUMENT and ANSWER you must analyze the provided answer and determine whether it is faithful to the contents of the DOCUMENT. The ANSWER must not offer new information beyond the context provided in the DOCUMENT. The ANSWER also must not contradict information provided in the DOCUMENT. Output your final verdict by strictly following this format: \"PASS\" if the answer is faithful to the DOCUMENT and \"FAIL\" if the answer is not faithful to the DOCUMENT. Show your reasoning.

--
QUESTION (THIS DOES NOT COUNT AS BACKGROUND INFORMATION):
{question}

--
DOCUMENT:
{context}

--
ANSWER:
{answer}

--

Your output should be in JSON FORMAT with the keys \"REASONING\" and \"SCORE\":
{{\"REASONING\": <your reasoning as bullet points>, \"SCORE\": <your final score>}}
"""


def build_evaluator():
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit("install transformers and a compatible torch build") from exc
    model_id = os.getenv(
        "LYNX_MODEL_ID", "PatronusAI/Llama-3-Patronus-Lynx-8B-Instruct-v1.1"
    )
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, device_map="cpu", torch_dtype=torch.float32, low_cpu_mem_usage=True
    )

    def evaluate(request):
        prompt = PROMPT.format(
            question=request["question"],
            context="\n".join(request.get("context", [])),
            answer=request["answer"],
        )
        inputs = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)
        outputs = model.generate(
            **inputs, max_new_tokens=600, do_sample=True, temperature=0.6, top_p=0.9
        )
        text = tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True
        ).strip()
        match = re.search(
            r'''["']?SCORE["']?\s*:\s*["']?(PASS|FAIL)["']?''',
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            match = re.search(r"\b(PASS|FAIL)\b", text, flags=re.IGNORECASE)
        if not match:
            raise RuntimeError(f"Lynx output did not contain a parseable SCORE: {text[:500]!r}")
        score = match.group(1).upper()
        return {"label": "supported" if score == "PASS" else "unsupported", "raw": text}

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
