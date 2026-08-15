"""All judging surfaces must consume the same V3.2 submission truth."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from html import unescape
from pathlib import Path

import pytest
from pypdf import PdfReader
from wallet_twin_v2.artifacts import git_content_changes

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "data/v2/submission_truth_v3.2.0.json"
DASHBOARD_TRUTH = ROOT / "dashboard/app/data/submission-truth-v3.2.0.json"
LIVE = ROOT / "outputs/v2_validation/live_provider_comparison.json"
PROMOTION = ROOT / "dashboard/app/data/promotion-fixture.json"
PRESENTATION_MANIFEST = ROOT / "assets/presentation/v3.2-committed-artifact-manifest.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_submission_truth_copies_are_byte_identical() -> None:
    assert TRUTH.read_bytes() == DASHBOARD_TRUTH.read_bytes()


def test_submission_truth_matches_live_provider_evidence() -> None:
    truth = load(TRUTH)["genai"]
    live = load(LIVE)
    assert (truth["target_runs"], truth["runs"], truth["accepted_runs"]) == (9, 9, 8)
    assert truth["accepted_runs"] == live["accepted_runs"]
    assert truth["submission_gate_passed"] is True
    assert set(truth["accepted_providers"]) == {"openai", "anthropic", "google"}
    assert set(truth["accepted_clients"]) == {"E01", "E02", "E09"}
    assert {
        (item["entity_id"], item["provider"])
        for item in truth["showcase_briefs"].values()
    } == {("E01", "openai"), ("E02", "anthropic"), ("E09", "google")}
    for item in truth["showcase_briefs"].values():
        assert item["execution_status"] == "PROVIDER_GENERATED"
        assert item["acceptance_status"] == "ACCEPTED"
        metrics = item["validation_metrics"]
        assert metrics["schema_compliance"] is True
        assert metrics["numeric_preservation"] is True
        assert metrics["citation_precision"] is True
        assert metrics["abstention_present"] is True
        assert metrics["unsupported_critical_claims"] == 0


def test_submission_truth_matches_promotion_fixture() -> None:
    truth = load(TRUTH)["promotion"]
    fixture = load(PROMOTION)
    assert truth["real_state"] == fixture["summary"]["real_state"] == "OFFLINE_CANDIDATE"
    assert truth["rehearsed_state"] == fixture["summary"]["rehearsed_state"] == "SHADOW_READY"
    assert truth["promotion_machinery_readiness"] == 1.0
    assert truth["bank_evidence_readiness"] == 0.0
    assert truth["bank_shadow_authorized"] is False
    assert truth["elapsed_bank_shadow_days"] == 0


def test_wallet_surface_names_the_v32_manifest_as_status_authority() -> None:
    wallet = load(ROOT / "dashboard/app/data/wallet-v311-fixture.json")
    release = wallet["projection"]["release"]
    assert release["hackathon_status_source"] == "outputs/judging_manifest_v3.2.0.json"


def test_presentation_manifest_normalizes_text_but_binds_deck_bytes() -> None:
    manifest = load(PRESENTATION_MANIFEST)
    deck = ROOT / manifest["artifact"]
    assert hashlib.sha256(deck.read_bytes()).hexdigest() == manifest["deck_sha256"]
    for source in manifest["sources"]:
        data = (ROOT / source["path"]).read_bytes()
        if source["hash_mode"] == "LF_NORMALIZED_TEXT":
            data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        else:
            assert source["hash_mode"] == "BYTE_EXACT"
        assert hashlib.sha256(data).hexdigest() == source["sha256"]


def test_submission_dirty_check_is_content_based() -> None:
    changed = git_content_changes()
    assert "GIT_INSPECTION_FAILED" not in changed
    # A regenerated file with an identical Git blob may be stat-dirty on
    # Windows; it is not a content change and must not cap readiness.
    if not (ROOT / ".git").exists():
        pytest.skip("content check requires a Git worktree")
    assert all(path.strip() for path in changed)
    assert "dashboard/app/data/wallet-v311-fixture.json" not in changed


def test_judge_facing_markdown_uses_current_provider_and_promotion_facts() -> None:
    for path in (ROOT / "README.md", ROOT / "docs/judging_map.md"):
        text = path.read_text(encoding="utf-8")
        assert "8" in text and "9" in text
        assert "SHADOW_READY" in text
        assert "all nine runs remain NOT_EXECUTED" not in text
        assert "Rehearsed to   CAUSAL_CHAMPION" not in text


@pytest.mark.skipif(
    not (ROOT / "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf").exists(),
    reason="one-pager not built",
)
def test_one_pager_publishes_current_provider_result() -> None:
    text = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(ROOT / "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf").pages
    )
    assert "8 / 9 PROVIDER OUTPUTS ACCEPTED" in text
    assert "0 EXECUTED" not in text


@pytest.mark.skipif(
    not (ROOT / "output/presentation/Corporate-Wallet-Digital-Twin.pptx").exists(),
    reason="deck not built",
)
def test_deck_publishes_current_provider_and_rehearsal_result() -> None:
    path = ROOT / "output/presentation/Corporate-Wallet-Digital-Twin.pptx"
    with zipfile.ZipFile(path) as archive:
        xml = " ".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            or re.fullmatch(r"ppt/notesSlides/notesSlide\d+\.xml", name)
        )
    text = " ".join(
        unescape(item).strip()
        for item in re.findall(r"<a:t[^>]*>(.*?)</a:t>", xml, flags=re.DOTALL)
        if item.strip()
    )
    assert "accepted outputs" in text
    assert "8 accepted; one blocked safely" in text
    assert "OFFLINE_CANDIDATE" in text and "SHADOW_READY" in text
    assert "all nine target runs remain NOT_EXECUTED" not in text


@pytest.mark.skipif(
    not (ROOT / "notebooks/01_wallet_twin_demo.ipynb").exists(),
    reason="notebook not built",
)
def test_notebook_publishes_current_provider_result() -> None:
    notebook = load(ROOT / "notebooks/01_wallet_twin_demo.ipynb")
    text = json.dumps(notebook)
    assert "Accepted provider outputs:" in text
    assert "Hackathon external-provider evaluation" in text or "hackathon external-provider evaluation" in text
    assert "8 of 9" in text or '"accepted_runs": 8' in text or "Accepted provider outputs: 8" in text
