"""V3.0 frozen regression boundary, restated under V3.1.1.

Two assets are held side by side:

``v3_0_frozen_surface.json``
    The **historical** pre-restatement boundary. Immutable. It records the V3.0
    surface as it stood when public anchors activated without an approval check.

``v3_0_frozen_surface.restated.json``
    The **live** boundary under the anchor-activation policy. Regenerate with
    ``python scripts/freeze_v3_regression.py`` only when a V3.0 change is
    intentional and reviewed.

The load-bearing assertion is
:func:`test_restatement_moved_measured_quantities_not_governance_claims`: the
measured digests are expected to move, the governance invariants are not. That
is what distinguishes a restatement from a policy change.
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

HISTORICAL = Path(__file__).with_name("v3_0_frozen_surface.json")
FROZEN = Path(__file__).with_name("v3_0_frozen_surface.restated.json")


@pytest.fixture(scope="module")
def historical() -> dict:
    return json.loads(HISTORICAL.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def frozen() -> dict:
    return json.loads(FROZEN.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def current() -> dict:
    return build_frozen_surface()


def test_historical_asset_is_retained_unmodified(historical: dict) -> None:
    """The superseded boundary must survive, or the restatement is unauditable."""
    assert historical["frozen_version"] == "3.0.0"
    assert historical["as_of"] == "2026-06-30"
    assert "supersedes" not in historical


def test_restated_asset_declares_its_lineage(frozen: dict) -> None:
    assert frozen["frozen_version"] == "3.0.0+restatement-V3.1.1"
    assert frozen["supersedes"] == "3.0.0"
    assert frozen["restatement_id"] == "V3.1.1-ANCHOR-APPROVAL"
    assert frozen["restatement_reason_code"] == "ANCHOR_ACTIVATED_WITHOUT_APPROVAL_CHECK"
    assert frozen["as_of"] == "2026-06-30"


def test_v3_0_counts_are_unchanged(frozen: dict, current: dict) -> None:
    assert current["counts"] == frozen["counts"]


def test_v3_0_projection_digests_match_the_restated_boundary(
    frozen: dict, current: dict
) -> None:
    for surface, expected in frozen["digests"].items():
        if surface == "action_portfolio":
            # Random-variate implementations and elementary functions can
            # produce sub-cent differences across Linux/Windows runtimes. The
            # portfolio has its own stronger contract test below: identities,
            # order and structure are exact; declared numeric fields use named
            # field tolerances.
            continue
        assert current["digests"][surface] == expected, (
            f"V3.0 restated regression boundary broken for '{surface}'. "
            "V3.1 must be additive."
        )


def test_v3_0_action_portfolio_structure_is_exact_and_numbers_are_tolerant(
    frozen: dict, current: dict
) -> None:
    assert current["action_portfolio_structure"] == frozen["action_portfolio_structure"]
    tolerances = frozen["numeric_tolerances"]
    money_tolerance = tolerances["money_zar_absolute"]
    probability_tolerance = tolerances["probability_absolute"]
    expected = frozen["action_portfolio_numerics"]
    actual = current["action_portfolio_numerics"]
    assert actual["expected_scenario_value_zar"] == pytest.approx(
        expected["expected_scenario_value_zar"], abs=money_tolerance
    )
    assert actual["downside_cvar_zar"] == pytest.approx(
        expected["downside_cvar_zar"], abs=money_tolerance
    )
    assert actual["selected_actions"].keys() == expected["selected_actions"].keys()
    for action_id, expected_values in expected["selected_actions"].items():
        actual_values = actual["selected_actions"][action_id]
        for field, expected_value in expected_values.items():
            tolerance = (
                probability_tolerance
                if field.endswith("probability")
                else money_tolerance
            )
            assert actual_values[field] == pytest.approx(expected_value, abs=tolerance), (
                f"portable numeric tolerance exceeded for {action_id}.{field}"
            )


def test_v3_0_ranking_and_selection_match_the_restated_boundary(
    frozen: dict, current: dict
) -> None:
    assert current["ranked_opportunity_ids"] == frozen["ranked_opportunity_ids"]
    assert current["selected_action_ids"] == frozen["selected_action_ids"]


def test_restatement_moved_measured_quantities_not_governance_claims(
    historical: dict, current: dict
) -> None:
    """The whole point of the restatement, in one assertion.

    Correcting anchor activation changes what the model measures, so ranks and
    digests move. It must change nothing about what the system is permitted to
    claim. If a governance invariant moved, this was not a restatement.
    """
    assert current["invariants"] == historical["invariants"]
    assert current["counts"] == historical["counts"]
    assert current["ranked_opportunity_ids"] != historical["ranked_opportunity_ids"], (
        "the restatement is expected to reorder the ranking; if it did not, the "
        "approval correction did not take effect"
    )


def test_v3_0_interpretation_invariants_are_unchanged(
    frozen: dict, current: dict
) -> None:
    assert current["invariants"] == frozen["invariants"]


def test_v3_0_repository_still_serves_the_legacy_decision_lab() -> None:
    payload = repository.decision_lab(repository.as_of, ["*"])
    assert len(payload["opportunities"]) == 100
    assert payload["release"]["bank_production_status"] == "NOT_PROMOTABLE"
