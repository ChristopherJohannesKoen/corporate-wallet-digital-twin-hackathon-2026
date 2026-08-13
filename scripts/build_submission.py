"""Canonical V3.1.1 hackathon submission build.

This is the only normal workflow allowed to write the final notebook, workbook,
PDF, PowerPoint and judging manifest. Live-provider execution is opt-in and
requires the controls enforced by ``run_live_provider_eval.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.1.1"
NODE = os.getenv("CODEX_NODE", "node")


def enter_locked_runtime() -> None:
    """Make the documented ``python`` command use the uv-locked interpreter.

    Windows installations commonly leave an older ``python.exe`` first on
    PATH.  Re-executing once through uv makes the canonical command portable
    while preserving its simple evaluator-facing interface.
    """

    marker = "WALLET_TWIN_SUBMISSION_LOCKED_RUNTIME"
    if os.getenv(marker) == "1":
        return
    environment = os.environ.copy()
    environment[marker] = "1"
    completed = subprocess.run(
        ["uv", "run", "--frozen", "python", str(Path(__file__).resolve()), *sys.argv[1:]],
        cwd=ROOT,
        env=environment,
    )
    raise SystemExit(completed.returncode)


def run(label: str, command: list[str], *, env: dict[str, str] | None = None) -> dict:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    completed = subprocess.run(command, cwd=ROOT, env=merged, text=True, capture_output=True)
    result = {
        "name": label,
        "command": " ".join(command).replace(str(ROOT), "<REPOSITORY_ROOT>"),
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_tail": completed.stdout.strip().splitlines()[-12:],
        "stderr_tail": completed.stderr.strip().splitlines()[-12:],
    }
    if completed.returncode:
        raise RuntimeError(json.dumps(result, indent=2))
    print(f"PASS {label}")
    return result


def hash_file(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest.hexdigest(), "size_bytes": path.stat().st_size}


def git_value(*args: str, default: str) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    return completed.stdout.strip() if completed.returncode == 0 else default


def require_files(paths: Iterable[Path]) -> None:
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise RuntimeError(f"Missing canonical artifacts: {missing}")


def main() -> None:
    enter_locked_runtime()
    from pypdf import PdfReader

    checks: list[dict] = []
    checks.append(run("locked environment", [sys.executable, "-c", "import fastapi,numpy,pandas,pydantic; print('environment-ok')"]))
    for script in ("export_v3_contracts.py", "export_v31_contracts.py", "export_v311_wallet_surface.py"):
        checks.append(run(script.removesuffix(".py"), [sys.executable, f"scripts/{script}"]))
    for script in (
        "run_evidence_qa.py",
        "build_finance_sme_review_pack.py",
        "run_offline_validation.py",
        "run_v3_validation.py",
        "run_measurement_sensitivity.py",
        "run_genai_evals.py",
    ):
        checks.append(run(script.removesuffix(".py"), [sys.executable, f"scripts/{script}"]))

    live_env = os.getenv("RUN_LIVE_PROVIDER_EVAL", "").lower() in {"1", "true", "yes"}
    live_command = [sys.executable, "scripts/run_live_provider_eval.py"]
    checks.append(run(
        "provider comparison" if live_env else "provider target report",
        live_command,
        env={"LIVE_PROVIDER_EVAL_ACK_PUBLIC_ONLY": "true"},
    ))

    checks.append(run("executed judging notebook", [sys.executable, "scripts/build_v31_notebook.py"]))
    checks.append(run("evidence workbook", [NODE, "scripts/build_public_facts_workbook.mjs", str(ROOT)]))
    checks.append(run("workbook verification", [NODE, "scripts/verify_public_facts_workbook.mjs", str(ROOT)]))
    checks.append(run("one-page PDF", [sys.executable, "scripts/build_submission_pdf.py", str(ROOT)]))
    checks.append(run("PowerPoint", [NODE, "scripts/build_v31_presentation.mjs", str(ROOT)]))

    artifacts = [
        ROOT / "notebooks/01_wallet_twin_demo.ipynb",
        ROOT / "output/notebook/01_wallet_twin_demo.html",
        ROOT / "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf",
        ROOT / "output/presentation/Corporate-Wallet-Digital-Twin.pptx",
        ROOT / "outputs/audit/Public-Facts-Anchor-Register-V3.1.1.xlsx",
        ROOT / "contracts/openapi.json",
        ROOT / "outputs/v2_validation/offline_validation_report.json",
        ROOT / "dashboard/app/data/wallet-v311-fixture.json",
        ROOT / "public-mirror-manifest.json",
    ]
    require_files(artifacts[:-1])
    pdf_pages = len(PdfReader(str(artifacts[2])).pages)
    if pdf_pages != 1:
        raise RuntimeError(f"One-pager contains {pdf_pages} pages")

    wallet = json.loads((ROOT / "dashboard/app/data/wallet-v311-fixture.json").read_text(encoding="utf-8"))["projection"]
    providers = json.loads((ROOT / "outputs/v2_validation/live_provider_comparison.json").read_text(encoding="utf-8"))
    live_accepted = sum(
        1
        for item in providers.get("evaluations", [])
        if item.get("acceptance_status") == "ACCEPTED"
    )
    public_manifest = json.loads(artifacts[-1].read_text(encoding="utf-8")) if artifacts[-1].exists() else None
    submission_ready = bool(public_manifest and public_manifest.get("status") == "PASS" and live_accepted >= 3)
    status = "HACKATHON_SUBMISSION_READY" if submission_ready else "HACKATHON_SUBMISSION_BLOCKED_EXTERNAL_GATES"

    dirty = bool(git_value("status", "--porcelain", default="UNKNOWN"))
    manifest = {
        "version": VERSION,
        "status": status,
        "bank_production_status": "NOT_PROMOTABLE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": os.getenv(
            "SUBMISSION_SOURCE_COMMIT",
            git_value("rev-parse", "HEAD", default="UNCOMMITTED"),
        ),
        "clean_worktree": not dirty,
        "data_mode": "PRIVATE_EVALUATOR" if os.getenv("SYNBANK_DATA_ZIP") else "AUTO_PRIVATE_IF_LOCAL_ARCHIVE_PRESENT_ELSE_PUBLIC_MIRROR",
        "checks": checks,
        "artifacts": [hash_file(path) for path in artifacts if path.exists()],
        "counts": {
            "wallet_cells": len(wallet["cells"]),
            "approved_anchor_cells": wallet["approved_anchor_cells"],
            "prior_led_cells": wallet["prior_led_cells"],
            "approved_source_facts": wallet["approved_source_facts"],
            "pending_source_facts": wallet["pending_source_facts"],
            "live_provider_briefs_accepted": live_accepted,
        },
        "claim_boundary": "Share is posterior unless E3-observed; economics are representative scenarios; causal incremental value is null; pending facts are excluded.",
        "confidentiality_boundary": "No supplied or derived row-level Syn Bank data, credentials, full provider payloads or private caches may enter the public mirror.",
        "open_external_gates": (
            ([] if live_accepted >= 3 else [
                "at least three accepted live-provider briefs using fresh rotated credentials"
            ])
            + ([] if public_manifest and public_manifest.get("status") == "PASS" else [
                "anonymous clean-history public mirror publication and verification"
            ])
        ),
        "bank_production_open_gates": [
            "representative E3 multibank calibration panel",
            "approved bank pricing, FTP, capital, risk, cost and hurdle inputs",
            "bank AWS/Databricks/identity/catalogue/SIEM controls",
            "supervised RM pilot and randomized outcome trial",
        ],
    }
    output = ROOT / "outputs/judging_manifest_v3.1.1.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "manifest": str(output), "pdf_pages": pdf_pages}, indent=2))


if __name__ == "__main__":
    main()
