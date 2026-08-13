"""Run the public-only comparative provider evaluation.

Credentials are environment-injected only; no payload or key is ever persisted.

**This script will not silently discard accepted evidence.** A run made without
credentials produces ``NOT_EXECUTED`` for every provider, and writing that over a
previous run that accepted real briefs destroys the only record of a live
evaluation — the artifact is the evidence, and re-running costs real API spend
against rotated keys. When the existing artifact reports more accepted runs than
the new one, the write is refused unless ``--allow-regression`` is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.live_provider_eval import (  # noqa: E402
    run_comparative_provider_evaluation,
    run_live_provider_evaluation,
)

OUTPUT = ROOT / "outputs" / "v2_validation" / "live_provider_comparison.json"


def existing_accepted(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("accepted_runs", 0))
    except (ValueError, TypeError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", nargs="?", default="all", choices=("all", "openai", "anthropic", "google"))
    parser.add_argument("--cases", type=int, default=3, help="deprecated; showcase set is fixed to three clients")
    parser.add_argument(
        "--allow-regression",
        action="store_true",
        help="permit overwriting an evaluation that accepted more briefs than this run",
    )
    args = parser.parse_args()

    result = (
        run_comparative_provider_evaluation()
        if args.provider == "all"
        else run_live_provider_evaluation(args.provider, args.cases)
    )
    accepted = int(result["accepted_runs"])
    previous = existing_accepted(OUTPUT)

    if accepted < previous and not args.allow_regression:
        print(
            json.dumps(
                {
                    "status": "REFUSED_TO_OVERWRITE_ACCEPTED_EVIDENCE",
                    "existing_accepted_runs": previous,
                    "this_run_accepted_runs": accepted,
                    "reason": (
                        "This run accepted fewer briefs than the artifact already on disk, "
                        "which usually means credentials were absent. Supply fresh rotated "
                        "provider credentials, or pass --allow-regression to discard the "
                        "existing evaluation deliberately."
                    ),
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "accepted_runs": accepted,
                "previous_accepted_runs": previous,
                "submission_gate_passed": result["submission_gate_passed"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
