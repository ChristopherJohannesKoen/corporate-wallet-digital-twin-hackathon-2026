from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .briefs import build_banker_brief


def grounded_prompt(evidence: dict[str, Any], prompt_template: str) -> str:
    compact = {
        "metadata": evidence["metadata"],
        "client": {
            key: value
            for key, value in evidence["client"].items()
            if key not in {"monthly", "forecasts"}
        },
        "opportunities": evidence["opportunities"][:5],
        "claim_policy": evidence["claim_policy"],
    }
    return f"{prompt_template.strip()}\n\n# Evidence package\n\n```json\n{json.dumps(compact, indent=2)}\n```"


def fallback(evidence: dict[str, Any]) -> str:
    return build_banker_brief(evidence["client"], evidence["opportunities"], evidence["metadata"]["as_of"])


def generate(evidence: dict[str, Any], prompt_path: Path, model: str = "gpt-5.6-sol") -> str:
    """Generate a grounded brief, or use the deterministic fallback.

    The optional LLM is a narrator over a precomputed evidence pack. It is never
    allowed to recompute wallet numbers or fill missing public facts.
    """

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback(evidence)
    try:
        from openai import OpenAI
    except ImportError:
        return fallback(evidence)

    client = OpenAI(api_key=api_key)
    prompt = grounded_prompt(evidence, prompt_path.read_text(encoding="utf-8"))
    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        text={"verbosity": "medium"},
        input=prompt,
    )
    text = response.output_text.strip()
    if not text or "Evidence and confidence" not in text or "Next action" not in text:
        return fallback(evidence)
    return text + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an evidence-grounded banker brief")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", type=Path, default=Path("prompts/banker_brief.md"))
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.6-sol"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = generate(evidence, args.prompt, args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(args.output), "mode": "openai" if os.getenv("OPENAI_API_KEY") else "deterministic_fallback"}))


if __name__ == "__main__":
    main()

