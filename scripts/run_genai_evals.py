from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.genai_eval import evaluate_golden_set


if __name__ == "__main__":
    result = evaluate_golden_set()
    output = ROOT / "outputs" / "v2_validation" / "genai_golden_eval.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(output), "release_gate": result["release_gate"]}, indent=2))
