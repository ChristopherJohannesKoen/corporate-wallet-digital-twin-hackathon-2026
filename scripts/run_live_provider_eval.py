from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.live_provider_eval import (
    run_comparative_provider_evaluation,
    run_live_provider_evaluation,
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a public/simulated live-provider evaluation.")
    parser.add_argument("provider", nargs="?", default="all", choices=("all", "openai", "anthropic", "google"))
    parser.add_argument("--cases", type=int, default=3, help="deprecated; showcase set is fixed to three clients")
    args = parser.parse_args()
    result = (
        run_comparative_provider_evaluation()
        if args.provider == "all"
        else run_live_provider_evaluation(args.provider, args.cases)
    )
    output = ROOT / "outputs" / "v2_validation" / "live_provider_comparison.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "accepted_runs": result["accepted_runs"],
        "submission_gate_passed": result["submission_gate_passed"],
    }, indent=2))
