"""V3.0 frozen regression boundary.

V3.1.0 extends V3.0 rather than replacing it.  These assertions fail if the
V3.1 decision layer perturbs any V3.0 projection.  Regenerate the asset with
``python scripts/freeze_v3_regression.py`` only when a V3.0 change is
intentional and reviewed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wallet_twin_v3.repository import repository

import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from freeze_v3_regression import build_frozen_surface  # noqa: E402

FROZEN = Path(__file__).with_name("v3_0_frozen_surface.json")


@pytest.fixture(scope="module")
def frozen() -> dict:
    return json.loads(FROZEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def current() -> dict:
    return build_frozen_surface()


def test_frozen_asset_declares_the_v3_0_boundary(frozen: dict) -> None:
    assert frozen["frozen_version"] == "3.0.0"
    assert frozen["as_of"] == "2026-06-30"


def test_v3_0_counts_are_unchanged(frozen: dict, current: dict) -> None:
    assert current["counts"] == frozen["counts"]


def test_v3_0_projection_digests_are_unchanged(frozen: dict, current: dict) -> None:
    for surface, expected in frozen["digests"].items():
        assert current["digests"][surface] == expected, (
            f"V3.0 regression boundary broken for '{surface}'. "
            "V3.1 must be additive."
        )


def test_v3_0_ranking_and_selection_are_unchanged(frozen: dict, current: dict) -> None:
    assert current["ranked_opportunity_ids"] == frozen["ranked_opportunity_ids"]
    assert current["selected_action_ids"] == frozen["selected_action_ids"]


def test_v3_0_interpretation_invariants_are_unchanged(
    frozen: dict, current: dict
) -> None:
    assert current["invariants"] == frozen["invariants"]


def test_v3_0_repository_still_serves_the_legacy_decision_lab() -> None:
    payload = repository.decision_lab(repository.as_of, ["*"])
    assert len(payload["opportunities"]) == 100
    assert payload["release"]["bank_production_status"] == "NOT_PROMOTABLE"
