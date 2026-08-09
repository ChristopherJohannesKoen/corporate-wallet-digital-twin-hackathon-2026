from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.production_target import write_production_target_report


if __name__ == "__main__":
    report = write_production_target_report()
    print(
        json.dumps(
            {
                "implementation_definitions_ready": report["implementation_definitions_ready"],
                "controls": f"{report['controls_passed']}/{report['controls_total']}",
                "environment_state": report["environment_state"],
            },
            indent=2,
        )
    )
