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


def portable(value: str) -> str:
    """Strip the build machine's absolute path out of captured output.

    Sub-scripts print paths through ``json.dumps``, which escapes backslashes —
    so a naive replace of ``str(ROOT)`` matches the raw form and silently misses
    the escaped one. That is how the committed manifest came to publish the
    developer's home directory. All three renderings are handled here, at the one
    funnel every sub-script's output passes through, so a newly added script
    cannot reintroduce the leak.
    """
    root = str(ROOT)
    for rendering in (
        json.dumps(root)[1:-1],  # JSON-escaped: C:\\Users\\...
        root,                    # raw: C:\Users\...
        root.replace("\\", "/"),  # POSIX-slash
    ):
        value = value.replace(rendering, "<REPOSITORY_ROOT>")
    return value


def run(
    label: str,
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    tolerated_codes: dict[int, str] | None = None,
) -> dict:
    """Run a build step, capturing portable output for the manifest.

    ``tolerated_codes`` maps an exit code to the status recorded for it. It
    exists for steps that can legitimately decline to act — a provider
    evaluation that refuses to overwrite accepted evidence has not failed, and
    stopping the whole build over it would be wrong.
    """
    merged = os.environ.copy()
    if env:
        merged.update(env)
    completed = subprocess.run(command, cwd=ROOT, env=merged, text=True, capture_output=True)
    tolerated = (tolerated_codes or {}).get(completed.returncode)
    result = {
        "name": label,
        "command": portable(" ".join(command)),
        "status": "PASS" if completed.returncode == 0 else (tolerated or "FAIL"),
        "stdout_tail": [portable(line) for line in completed.stdout.strip().splitlines()[-12:]],
        "stderr_tail": [portable(line) for line in completed.stderr.strip().splitlines()[-12:]],
    }
    if completed.returncode and tolerated is None:
        raise RuntimeError(json.dumps(result, indent=2))
    print(f"{result['status']} {label}")
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


def stamp_wallet_release(status: str) -> None:
    """Write the computed submission status into the wallet surface.

    The exporter publishes ``HACKATHON_STATUS_PENDING`` because it runs before
    the live-provider comparison exists. Stamping here keeps one computation
    behind both artifacts, so the workbench and the judging manifest cannot
    disagree about whether the submission is ready.
    """
    from wallet_twin_v2.canonical import write_canonical_json
    from wallet_twin_v31.wallet_portfolio import HACKATHON_STATUS_PENDING

    path = ROOT / "dashboard/app/data/wallet-v311-fixture.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    release = payload["projection"]["release"]
    if release.get("hackathon_status") not in {HACKATHON_STATUS_PENDING, status}:
        raise RuntimeError(
            "wallet surface published an unexpected hackathon_status "
            f"{release.get('hackathon_status')!r}; the exporter must emit the "
            "pending placeholder so the canonical build owns the verdict"
        )
    release["hackathon_status"] = status
    write_canonical_json(path, payload)


def main() -> None:
    enter_locked_runtime()
    from pypdf import PdfReader

    from wallet_twin_v2.artifacts import reproducibility_relevant

    checks: list[dict] = []
    checks.append(run("locked environment", [sys.executable, "-c", "import fastapi,numpy,pandas,pydantic; print('environment-ok')"]))
    # Order matters: export_v31_contracts writes contracts/openapi.json from the
    # composed app, which now includes the V3.2 promotion routes, and
    # export_v311_wallet_surface owns the wallet fixture's stamped status.
    for script in (
        "export_v3_contracts.py",
        "export_v31_contracts.py",
        "export_v311_wallet_surface.py",
        "export_v32_contracts.py",
        "export_v32_workbench_fixture.py",
    ):
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

    # The check is labelled from what the run actually did, not from an env var.
    # RUN_LIVE_PROVIDER_EVAL previously only changed this label while the command
    # and environment stayed identical, so a manifest could record "provider
    # comparison" when nothing live ran, or the reverse.
    # Exit 2 means the evaluator declined to overwrite a stronger existing
    # evaluation — credentials were absent this run. Preserving that evidence is
    # the correct outcome, so the build continues and records what happened.
    provider_check = run(
        "provider evaluation",
        [sys.executable, "scripts/run_live_provider_eval.py"],
        env={"LIVE_PROVIDER_EVAL_ACK_PUBLIC_ONLY": "true"},
        tolerated_codes={2: "PASS_EXISTING_EVIDENCE_PRESERVED"},
    )
    checks.append(provider_check)

    checks.append(run("executed judging notebook", [sys.executable, "scripts/build_v31_notebook.py"]))
    checks.append(run("evidence workbook", [NODE, "scripts/build_public_facts_workbook.mjs", str(ROOT)]))
    checks.append(run("workbook verification", [NODE, "scripts/verify_public_facts_workbook.mjs", str(ROOT)]))
    checks.append(run("one-page PDF", [sys.executable, "scripts/build_submission_pdf.py", str(ROOT)]))
    checks.append(run("PowerPoint", [NODE, "scripts/build_v31_presentation.mjs", str(ROOT)]))

    # Named rather than index-addressed. This list was read positionally —
    # artifacts[2] for the PDF page check and artifacts[-1] for the public
    # mirror manifest that drives the readiness verdict — so appending a new
    # artifact would silently have made the new file the readiness input and
    # page-checked the wrong document. The V3.2 additions below are exactly the
    # append that would have done it.
    ONE_PAGER = ROOT / "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf"
    PUBLIC_MIRROR_MANIFEST = ROOT / "public-mirror-manifest.json"

    artifacts = [
        ROOT / "notebooks/01_wallet_twin_demo.ipynb",
        ROOT / "output/notebook/01_wallet_twin_demo.html",
        ONE_PAGER,
        ROOT / "output/presentation/Corporate-Wallet-Digital-Twin.pptx",
        ROOT / "outputs/audit/Public-Facts-Anchor-Register-V3.1.1.xlsx",
        ROOT / "contracts/openapi.json",
        ROOT / "outputs/v2_validation/offline_validation_report.json",
        ROOT / "dashboard/app/data/wallet-v311-fixture.json",
        # V3.2 promotion surface.
        ROOT / "contracts/promotion-gate-catalogue.json",
        ROOT / "outputs/v32/v32_promotion_policy.json",
        ROOT / "outputs/v32/v32_signing_posture.json",
        ROOT / "outputs/v32/v32_simulation_laboratories.json",
        ROOT / "outputs/v32/v32_shadow_rehearsal.json",
        ROOT / "dashboard/app/data/promotion-fixture.json",
        PUBLIC_MIRROR_MANIFEST,
    ]
    # The mirror manifest is produced by a later step, so it is the one artifact
    # not required to exist yet. Named explicitly instead of sliced off the end.
    require_files([path for path in artifacts if path != PUBLIC_MIRROR_MANIFEST])
    pdf_pages = len(PdfReader(str(ONE_PAGER)).pages)
    if pdf_pages != 1:
        raise RuntimeError(f"One-pager contains {pdf_pages} pages")

    wallet = json.loads((ROOT / "dashboard/app/data/wallet-v311-fixture.json").read_text(encoding="utf-8"))["projection"]
    promotion = json.loads(
        (ROOT / "dashboard/app/data/promotion-fixture.json").read_text(encoding="utf-8")
    )
    # The prohibition travels with the data. If a composite ever reappears in the
    # fixture, the build fails here rather than publishing it in the manifest.
    from wallet_twin_v32 import assert_no_composite_score

    assert_no_composite_score(promotion["summary"])
    providers = json.loads((ROOT / "outputs/v2_validation/live_provider_comparison.json").read_text(encoding="utf-8"))
    live_accepted = sum(
        1
        for item in providers.get("evaluations", [])
        if item.get("acceptance_status") == "ACCEPTED"
    )
    public_manifest = (
        json.loads(PUBLIC_MIRROR_MANIFEST.read_text(encoding="utf-8"))
        if PUBLIC_MIRROR_MANIFEST.exists()
        else None
    )
    submission_ready = bool(public_manifest and public_manifest.get("status") == "PASS" and live_accepted >= 3)
    status = "HACKATHON_SUBMISSION_READY" if submission_ready else "HACKATHON_SUBMISSION_BLOCKED_EXTERNAL_GATES"

    # One computation, two artifacts. The wallet surface is exported before the
    # provider comparison resolves, so it publishes a pending placeholder that is
    # replaced here rather than guessing a verdict of its own.
    #
    # This must happen *before* the worktree is inspected. Between the exporter
    # and this call the fixture holds the pending sentinel, and sampling there
    # would report a reproducibility-gated artifact as drifted on every build —
    # a mid-build snapshot, not a fact about the commit.
    stamp_wallet_release(status)

    # `git status --porcelain` emits "XY path"; slice past the two status
    # characters and strip, rather than assuming a fixed-width prefix.
    porcelain = git_value("status", "--porcelain", default="UNKNOWN")
    changed = [line[2:].strip() for line in porcelain.splitlines() if line.strip()]
    # Document deliverables restamp their own creation time on every build, so a
    # whole-tree dirty check would make an honest READY verdict unreachable. What
    # matters is whether source or a gated artifact drifted from the named commit.
    blocking_dirty = reproducibility_relevant(changed)
    dirty = bool(blocking_dirty)
    manifest_dirty_paths = sorted(blocking_dirty)[:20]
    rebuilt_deliverables = sorted(set(changed) - set(blocking_dirty))[:20]
    # A manifest that names a commit but was built from uncommitted source
    # overstates its own reproducibility. Readiness is capped, not claimed.
    if dirty and submission_ready:
        status = "HACKATHON_SUBMISSION_PROVISIONAL_UNCOMMITTED_WORKTREE"
        # Re-stamp so the fixture and the manifest cannot disagree. Only the
        # capped path reaches here, so the common case writes once.
        stamp_wallet_release(status)
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
        "clean_worktree_scope": (
            "source and reproducibility-gated artifacts; document deliverables that "
            "restamp their own creation time are listed separately and do not affect "
            "the verdict"
        ),
        "dirty_paths": manifest_dirty_paths,
        "rebuilt_deliverables": rebuilt_deliverables,
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
            "promotion_gates": sum(
                len(item["gates"]) for item in promotion["transitions"]
            ),
        },
        # The V3.2 position, read from the exported fixture rather than restated.
        # Two scores and no third: a blended figure would let a fully rehearsed
        # system with no bank evidence read as nearly production-ready.
        "promotion": {
            "real_state": promotion["summary"]["real_state"],
            "rehearsed_state": promotion["summary"]["rehearsed_state"],
            "bank_shadow_authorized": promotion["summary"]["bank_shadow_authorized"],
            "promotion_machinery_readiness": promotion["summary"][
                "promotion_machinery_readiness"
            ],
            "bank_evidence_readiness": promotion["summary"]["bank_evidence_readiness"],
            "shadow_rehearsal_days": promotion["clock"][
                "consecutive_clean_rehearsal_days"
            ],
            # Published beside the rehearsal count everywhere it appears.
            "elapsed_bank_shadow_days": promotion["clock"]["elapsed_bank_shadow_days"],
            "real_bank_signing_available": promotion["signing"][
                "real_bank_signing_available"
            ],
            "signers_executed": promotion["signing"]["executed"],
            "signers_not_executed": promotion["signing"]["not_executed"],
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
            # V3.2 makes two of these measurable rather than merely asserted:
            # the promotion twin now names the gate, its owner, and what would
            # satisfy it, and reports zero elapsed bank shadow days beside the
            # rehearsal count.
            "thirty elapsed clean bank shadow days (rehearsed only; elapsed = 0)",
            "a real bank signing key; no signer here can sign REAL_BANK evidence",
        ],
    }
    output = ROOT / "outputs/judging_manifest_v3.1.1.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "manifest": str(output), "pdf_pages": pdf_pages}, indent=2))


if __name__ == "__main__":
    main()
