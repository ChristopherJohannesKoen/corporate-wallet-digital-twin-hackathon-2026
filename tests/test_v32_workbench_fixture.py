"""The promotion readiness fixture the workbench renders.

The projection logic lives in Python rather than TypeScript so these assertions
can reach it. What the view must never do — publish a single blended score, show
a rehearsal count without the elapsed bank count, or omit a refused capability —
is checked here, where a failure is a test failure rather than something a
reviewer has to notice on a screen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wallet_twin_v32 import assert_no_composite_score
from wallet_twin_v32.catalogue import GATE_CATALOGUE

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "dashboard" / "app" / "data" / "promotion-fixture.json"


@pytest.fixture(scope="module")
def fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rebuilt() -> dict:
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from export_v32_workbench_fixture import build_fixture

    return build_fixture()


# --------------------------------------------------------------------------
# The prohibition
# --------------------------------------------------------------------------


def test_no_composite_score_anywhere_in_the_fixture(fixture: dict) -> None:
    assert_no_composite_score(fixture)
    assert_no_composite_score(fixture["summary"])


def test_both_scores_are_present_and_disagree(fixture: dict) -> None:
    """The two numbers disagreeing *is* the finding. Averaging them would
    destroy it, which is why there is no third number."""
    summary = fixture["summary"]
    assert summary["promotion_machinery_readiness"] == 1.0
    assert summary["bank_evidence_readiness"] == 0.0


def test_the_fixture_states_why_there_is_no_single_percentage(fixture: dict) -> None:
    assert "never combined" in fixture["why_no_single_percentage"]


def test_the_excluded_synthetic_weight_is_published(fixture: dict) -> None:
    """Turns "BER is low" into "here is exactly how much is simulated"."""
    summary = fixture["summary"]
    assert summary["synthetic_weight_excluded_from_ber"] == summary["pmr_weight_available"]
    assert summary["synthetic_weight_excluded_from_ber"] > 0


# --------------------------------------------------------------------------
# Simulated time beside elapsed time
# --------------------------------------------------------------------------


def test_both_day_counts_are_in_the_fixture(fixture: dict) -> None:
    clock = fixture["clock"]
    assert clock["consecutive_clean_rehearsal_days"] == 30
    assert clock["elapsed_bank_shadow_days"] == 0
    assert clock["incidents_injected"] == 1


def test_the_reset_reason_is_carried_through_to_the_view(fixture: dict) -> None:
    assert "RECONCILIATION" in fixture["clock"]["last_reset_reason"]


# --------------------------------------------------------------------------
# The gate register
# --------------------------------------------------------------------------


def test_every_catalogue_gate_appears_exactly_once(fixture: dict) -> None:
    rendered = [
        gate["gate_id"] for transition in fixture["transitions"] for gate in transition["gates"]
    ]
    assert sorted(rendered) == sorted(gate.gate_id for gate in GATE_CATALOGUE)
    assert len(rendered) == len(set(rendered)) == 30


def test_every_gate_row_says_what_would_make_the_real_gate_pass(fixture: dict) -> None:
    """The field a reviewer acts on. A red cell with no next action is a
    complaint, not a control."""
    for transition in fixture["transitions"]:
        for gate in transition["gates"]:
            assert len(gate["what_would_make_real_pass"]) > 40, gate["gate_id"]
            assert len(gate["consequence_if_failed"]) > 40, gate["gate_id"]


def test_every_gate_row_carries_its_owner_and_a_different_approver(fixture: dict) -> None:
    for transition in fixture["transitions"]:
        for gate in transition["gates"]:
            assert gate["owner_role"] != gate["approver_role"], gate["gate_id"]


def test_the_projection_has_four_states_not_two(fixture: dict) -> None:
    """"The bank passed this" and "the rehearsal passed this" are different
    facts, and "nobody has looked" is different again from "this failed"."""
    assert set(fixture["projection_legend"]) == {
        "real-pass",
        "rehearsal-pass",
        "waiting",
        "failed",
    }


def test_every_gate_currently_projects_as_rehearsal_pass(fixture: dict) -> None:
    """The honest V3.2 position: the machinery works everywhere and the bank
    has authorised nothing."""
    projections = {
        gate["projection"] for transition in fixture["transitions"] for gate in transition["gates"]
    }
    assert projections == {"rehearsal-pass"}


def test_no_gate_row_claims_a_real_evidence_mode(fixture: dict) -> None:
    for transition in fixture["transitions"]:
        for gate in transition["gates"]:
            assert gate["real_outcome"] == "NOT_EVALUATED", gate["gate_id"]
            assert gate["ber_contribution"] == 0.0, gate["gate_id"]


def test_signature_status_is_reported_per_gate(fixture: dict) -> None:
    for transition in fixture["transitions"]:
        for gate in transition["gates"]:
            assert gate["signature_status"] == "SIGNED_REHEARSAL"
            assert gate["trust_domain"] == "rehearsal"


# --------------------------------------------------------------------------
# States and capabilities
# --------------------------------------------------------------------------


def test_five_state_columns_each_showing_both_tracks(fixture: dict) -> None:
    states = fixture["states"]
    assert len(states) == 5
    assert [item["state"] for item in states] == [
        "OFFLINE_CANDIDATE",
        "SHADOW_READY",
        "PILOT_READY",
        "SCALE_READY",
        "CAUSAL_CHAMPION",
    ]
    assert [item["real_attained"] for item in states] == [True, False, False, False, False]
    assert [item["rehearsed_attained"] for item in states] == [
        True,
        True,
        False,
        False,
        False,
    ]


def test_refused_capabilities_are_rendered_with_reasons(fixture: dict) -> None:
    """A register of what is allowed, with refusals omitted, cannot be audited
    for whether the right things are refused."""
    refused = [item for item in fixture["capabilities"] if not item["granted"]]
    assert refused
    for item in refused:
        assert item["refusal_reason"], item["capability"]


def test_autonomous_client_action_is_shown_as_permanently_withheld(
    fixture: dict,
) -> None:
    entry = next(
        item
        for item in fixture["capabilities"]
        if item["capability"] == "AUTONOMOUS_CLIENT_ACTION"
    )
    assert entry["granted"] is False
    assert entry["refusal_reason"] == "PERMANENTLY_WITHHELD_BY_DESIGN"


def test_the_signing_block_says_no_real_bank_capability(fixture: dict) -> None:
    signing = fixture["signing"]
    assert signing["real_bank_signing_available"] is False
    assert signing["executed"] == ["LocalECDSASigner"]
    assert set(signing["not_executed"]) == {"SigstoreSigner", "KMSSigner"}


def test_every_gate_has_a_published_negative_case(fixture: dict) -> None:
    assert fixture["gates_without_failure_injection"] == []


# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------


def test_the_committed_fixture_matches_a_fresh_build(rebuilt: dict, fixture: dict) -> None:
    """The fixture is byte-gated in CI, so a stale commit fails the diff gate."""
    assert rebuilt == fixture


def test_the_fixture_carries_no_wall_clock_stamp(fixture: dict) -> None:
    assert fixture["generated_at"].startswith("2026-06-30")
    assert fixture["as_of"] == "2026-06-30"


def test_the_bank_production_status_is_unchanged(fixture: dict) -> None:
    assert fixture["summary"]["bank_production_status"] == "NOT_PROMOTABLE"
    assert fixture["summary"]["bank_shadow_authorized"] is False
