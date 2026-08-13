"""Published artifacts must agree about the submission's own status.

V3.1.1 shipped with `outputs/judging_manifest_v3.1.1.json` reporting
`HACKATHON_SUBMISSION_READY` while `dashboard/app/data/wallet-v311-fixture.json`
reported `HACKATHON_SUBMISSION_BLOCKED_EXTERNAL_GATES`. The workbench reads the
fixture, so a judge would have seen BLOCKED on screen while the manifest claimed
READY — in a submission whose entire argument is that its numbers are governed.

Nothing caught it, because no test compared artifacts to each other. These do.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest

from wallet_twin_v2.artifacts import ROOT, committed_artifacts
from wallet_twin_v31.wallet_portfolio import HACKATHON_STATUS_PENDING

MANIFEST = ROOT / "outputs" / "judging_manifest_v3.1.1.json"
WALLET_FIXTURE = ROOT / "dashboard" / "app" / "data" / "wallet-v311-fixture.json"

#: Every value the submission verdict is allowed to take.
SUBMISSION_STATES = {
    "HACKATHON_SUBMISSION_READY",
    "HACKATHON_SUBMISSION_BLOCKED_EXTERNAL_GATES",
    "HACKATHON_SUBMISSION_PROVISIONAL_UNCOMMITTED_WORKTREE",
    HACKATHON_STATUS_PENDING,
}


def _walk(value: Any, pointer: str = "") -> Iterator[tuple[str, Any]]:
    yield pointer or "/", value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{pointer}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{pointer}/{index}")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _submission_statuses(payload: Any) -> list[tuple[str, str]]:
    return [
        (pointer, value)
        for pointer, value in _walk(payload)
        if isinstance(value, str) and value.startswith("HACKATHON_")
    ]


@pytest.mark.skipif(not MANIFEST.exists(), reason="judging manifest not built")
def test_manifest_and_wallet_surface_agree_on_submission_status():
    manifest_status = _load(MANIFEST)["status"]
    wallet_status = _load(WALLET_FIXTURE)["projection"]["release"]["hackathon_status"]
    assert wallet_status != HACKATHON_STATUS_PENDING, (
        "the wallet surface still carries the exporter placeholder; "
        "scripts/build_submission.py must stamp the computed status"
    )
    assert wallet_status == manifest_status, (
        f"the workbench would display {wallet_status!r} while the judging manifest "
        f"claims {manifest_status!r}"
    )


def test_every_published_submission_status_is_a_declared_state():
    """No artifact may invent a status string outside the governed set."""
    offenders: list[str] = []
    for path in [*committed_artifacts(), MANIFEST]:
        if not path.exists():
            continue
        for pointer, value in _submission_statuses(_load(path)):
            if value not in SUBMISSION_STATES:
                offenders.append(f"{path.relative_to(ROOT)}{pointer} = {value!r}")
    assert not offenders, "undeclared submission status:\n  " + "\n  ".join(offenders)


def test_bank_production_status_is_never_promotable_anywhere():
    """The one claim no run, artifact or code path may alter."""
    offenders: list[str] = []
    for path in [*committed_artifacts(), MANIFEST]:
        if not path.exists():
            continue
        for pointer, value in _walk(_load(path)):
            if pointer.rsplit("/", 1)[-1] == "bank_production_status" and value != "NOT_PROMOTABLE":
                offenders.append(f"{path.relative_to(ROOT)}{pointer} = {value!r}")
    assert not offenders, "bank production status was weakened:\n  " + "\n  ".join(offenders)


@pytest.mark.skipif(not MANIFEST.exists(), reason="judging manifest not built")
def test_ready_verdict_requires_a_clean_worktree():
    """A manifest built from uncommitted code may not claim reproducibility.

    It names a commit; if the tree was dirty, that commit is not what was built,
    so the strongest honest verdict is PROVISIONAL.
    """
    manifest = _load(MANIFEST)
    if manifest["status"] == "HACKATHON_SUBMISSION_READY":
        assert manifest["clean_worktree"] is True, (
            "manifest claims READY from a dirty worktree; dirty paths: "
            f"{manifest.get('dirty_paths')}"
        )


@pytest.mark.skipif(not MANIFEST.exists(), reason="judging manifest not built")
def test_manifest_records_no_absolute_paths():
    text = MANIFEST.read_text(encoding="utf-8")
    for needle in ("C:\\\\", "C:\\", "/Users/", "/home/"):
        assert needle not in text, f"manifest leaks a developer path fragment: {needle!r}"
