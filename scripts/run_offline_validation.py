from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_PATH / "src"))

from wallet_twin_v2.offline_lab import ROOT, write_offline_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the explicitly non-production V2 offline validation laboratory.")
    parser.add_argument("--skip-history", action="store_true", help="Skip the supplied transaction-history validation pass.")
    parser.add_argument(
        "--data-zip",
        type=Path,
        default=None,
        help="Path to the confidential Syn Bank Data.zip (or set SYNBANK_DATA_ZIP).",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "v2_validation")
    args = parser.parse_args()
    result = write_offline_outputs(args.output, include_history=not args.skip_history, zip_path=args.data_zip)
    print(json.dumps({
        "report_version": result["report_version"],
        "output": str(args.output / "offline_validation_report.json"),
        "watermark": result["global_watermark"],
    }, indent=2))


if __name__ == "__main__":
    main()
