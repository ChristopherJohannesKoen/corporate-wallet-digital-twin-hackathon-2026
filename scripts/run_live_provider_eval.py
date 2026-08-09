from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.live_provider_eval import run_live_provider_evaluation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a public/simulated live-provider evaluation.")
    parser.add_argument("provider", choices=("openai", "anthropic", "google"))
    parser.add_argument("--cases", type=int, default=20)
    args = parser.parse_args()
    result = run_live_provider_evaluation(args.provider, args.cases)
    output = ROOT / "outputs" / "v2_validation" / f"live_provider_{args.provider}.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"output": str(output), "provider_success_rate": result["provider_success_rate"]}, indent=2))
