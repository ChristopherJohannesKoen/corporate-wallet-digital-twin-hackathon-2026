from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> dict:
    command = [sys.executable, *args]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return {
        "command": " ".join(args),
        "status": "passed",
        "stdout_tail": completed.stdout.strip().splitlines()[-8:],
    }


def main() -> None:
    supplied_default = ROOT / "ref" / "Data Sets" / "Data.zip"
    configured = os.getenv("SYNBANK_DATA_ZIP")
    archive = Path(configured).expanduser().resolve() if configured else supplied_default

    checks = [
        run("scripts/run_client_demo.py"),
        run("scripts/run_evidence_qa.py"),
        run("scripts/run_genai_evals.py"),
        run("scripts/export_v2_contracts.py"),
        run("scripts/validate_production_target.py"),
    ]
    offline_args = ["scripts/run_offline_validation.py"]
    if archive.exists():
        offline_args.extend(["--data-zip", str(archive)])
        history_mode = "supplied-confidential-archive"
    else:
        offline_args.append("--skip-history")
        history_mode = "representative-lab-only"
    checks.append(run(*offline_args))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "team": "Corporate Wallet Digital Twin",
        "member": "Christopher Koen",
        "solution_version": "V2.1",
        "history_mode": history_mode,
        "checks": checks,
        "status": "PASSED",
        "claim_boundary": "SYN BANK SIMULATION + PUBLIC E1 + REPRESENTATIVE BENCHMARKS",
    }
    output = ROOT / "outputs" / "judging_validation_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
