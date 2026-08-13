"""V3.2 promotion contracts — every invariant with its negative test.

A gate with only a positive test has not been implemented, it has been
asserted. The same is true of a governance invariant: proving the honest case
constructs is worth little unless the dishonest case is proven to raise.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from wallet_twin_v32 import (
    GATE_CATALOGUE,
    NOT_DETERMINED_UP_TO_150,
    SEVERITY_WEIGHTS,
    DecisionTrack,
    E3SampleSizePlan,
    GateDefinition,
    GateEvaluation,
    GateEvidence,
    GateOutcome,
    GateSeverity,
    IncidentInjection,
    PromotionApproval,
    PromotionEvidenceMode,
    PromotionState,
    RehearsalScenario,
    SignedEvidenceEnvelope,
    VirtualClockState,
    evidence_supports_gate,
)
from wallet_twin_v32.catalogue import GATES_BY_ID

AS_OF = date(2026, 6, 30)
NOW = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64
SYNTHETIC = PromotionEvidenceMode.SYNTHETIC_REHEARSAL
PUBLIC = PromotionEvidenceMode.PUBLIC_PACKAGE
REAL_BANK = PromotionEvidenceMode.REAL_BANK
ATTESTED = PromotionEvidenceMode.BANK_ATTESTED


def evidence(**overrides) -> GateEvidence:
    payload = {
        "evidence_id": "ev-1",
        "gate_id": "supply-chain-clean",
        "mode": PUBLIC,
        "artifact_uri": "outputs/sbom.spdx.json",
        "content_sha256": DIGEST,
        "summary": "SBOM published for the released digest",
        "as_of": AS_OF,
        "generated_at": NOW,
        "produced_by": "ci",
    }
    payload.update(overrides)
    return GateEvidence(**payload)


def evaluation(**overrides) -> GateEvaluation:
    payload = {
        "gate_id": "supply-chain-clean",
        "transition_id": "OFFLINE_CANDIDATE__TO__SHADOW_READY",
        "track": DecisionTrack.REAL,
        "outcome": GateOutcome.PASS,
        "evidence_mode": PUBLIC,
        "evidence_ids": ["ev-1"],
        "evaluated_at": NOW,
    }
    payload.update(overrides)
    return GateEvaluation(**payload)


# --------------------------------------------------------------------------
# The central invariant: synthetic evidence cannot support a real verdict
# --------------------------------------------------------------------------


def test_synthetic_evidence_cannot_pass_a_real_gate() -> None:
    with pytest.raises(ValidationError, match="synthetic evidence cannot support"):
        evaluation(evidence_mode=SYNTHETIC, track=DecisionTrack.REAL)


def test_synthetic_evidence_can_pass_a_rehearsal_gate() -> None:
    result = evaluation(evidence_mode=SYNTHETIC, track=DecisionTrack.REHEARSAL)
    assert result.satisfied()


def test_real_evidence_is_admissible_in_a_rehearsal() -> None:
    """Rehearsing with real artifacts strengthens the rehearsal; only the
    reverse direction is a misrepresentation."""
    result = evaluation(evidence_mode=ATTESTED, track=DecisionTrack.REHEARSAL)
    assert result.satisfied()


def test_pass_without_evidence_is_refused() -> None:
    with pytest.raises(ValidationError, match="PASS requires an evidence_mode"):
        evaluation(evidence_mode=None)


def test_pass_without_evidence_ids_is_refused() -> None:
    with pytest.raises(ValidationError, match="requires at least one evidence_id"):
        evaluation(evidence_ids=[])


def test_unknown_is_not_a_failure_and_needs_no_evidence() -> None:
    result = evaluation(outcome=GateOutcome.UNKNOWN, evidence_mode=None, evidence_ids=[])
    assert not result.satisfied()
    assert result.outcome is not GateOutcome.FAIL


# --------------------------------------------------------------------------
# Waivers
# --------------------------------------------------------------------------


def test_waiver_requires_a_named_approver() -> None:
    with pytest.raises(ValidationError, match="requires a named waived_by"):
        evaluation(outcome=GateOutcome.WAIVED, evidence_mode=None, evidence_ids=[])


def test_waiver_with_a_named_approver_satisfies_but_is_counted() -> None:
    result = evaluation(
        outcome=GateOutcome.WAIVED,
        evidence_mode=None,
        evidence_ids=[],
        waived_by="head-of-operations",
        waiver_rationale="compensating control in place",
    )
    assert result.satisfied()


def test_waived_by_on_a_non_waiver_outcome_is_refused() -> None:
    with pytest.raises(ValidationError, match="waived_by is set on a PASS"):
        evaluation(waived_by="someone")


# --------------------------------------------------------------------------
# The four time fields
# --------------------------------------------------------------------------


def test_published_cannot_precede_generated() -> None:
    with pytest.raises(ValidationError, match="published before it exists"):
        evidence(published_at=NOW - timedelta(hours=1))


def test_expiry_must_follow_generation() -> None:
    with pytest.raises(ValidationError, match="expires_at is not after generated_at"):
        evidence(expires_at=NOW)


def test_simulation_clock_is_refused_on_non_synthetic_evidence() -> None:
    """The field that advances during an accelerated rehearsal must be the one
    named for simulated time, never the ones that mean elapsed time."""
    with pytest.raises(ValidationError, match="virtual clock has no meaning"):
        evidence(mode=REAL_BANK, simulation_clock=NOW)


def test_simulation_clock_is_allowed_on_synthetic_evidence() -> None:
    item = evidence(mode=SYNTHETIC, simulation_clock=NOW + timedelta(days=17))
    assert item.simulation_clock is not None


# --------------------------------------------------------------------------
# Signing envelopes
# --------------------------------------------------------------------------


def envelope(**overrides) -> SignedEvidenceEnvelope:
    payload = {
        "envelope_id": "env-1",
        "evidence_id": "ev-1",
        "payload_sha256": DIGEST,
        "mode": SYNTHETIC,
        "key_id": "local-rehearsal-p256",
        "key_authorised_modes": [SYNTHETIC],
        "signature_algorithm": "ecdsa-p256-sha256",
        "trust_domain": "rehearsal",
    }
    payload.update(overrides)
    return SignedEvidenceEnvelope(**payload)


def test_rehearsal_key_cannot_sign_real_bank_evidence() -> None:
    with pytest.raises(ValidationError, match="not .*authorised to sign REAL_BANK"):
        envelope(mode=REAL_BANK)


def test_rehearsal_key_cannot_sign_bank_attested_evidence() -> None:
    with pytest.raises(ValidationError, match="not .*authorised to sign BANK_ATTESTED"):
        envelope(mode=ATTESTED)


def test_a_key_authorised_for_a_mode_may_sign_it() -> None:
    item = envelope(
        mode=ATTESTED,
        key_id="aws-kms-bank",
        key_authorised_modes=[REAL_BANK, ATTESTED],
        trust_domain="bank",
    )
    assert item.mode is ATTESTED


def test_signature_status_cannot_claim_more_than_the_signature_shows() -> None:
    with pytest.raises(ValidationError, match="claims VERIFIED with no signature"):
        envelope(signature_status="VERIFIED")


def test_a_present_signature_cannot_report_unsigned() -> None:
    with pytest.raises(ValidationError, match="still reports UNSIGNED"):
        envelope(signature="MEUCIQ...", signature_status="UNSIGNED")


# --------------------------------------------------------------------------
# Maker/checker
# --------------------------------------------------------------------------


def approval(**overrides) -> PromotionApproval:
    payload = {
        "approval_id": "ap-1",
        "transition_id": "OFFLINE_CANDIDATE__TO__SHADOW_READY",
        "track": DecisionTrack.REHEARSAL,
        "submitted_by": "maker@bank",
        "submitted_role": "ENGINEERING",
        "reviewed_by": "checker@bank",
        "reviewed_role": "MODEL_RISK",
        "decision": "APPROVED",
        "rationale": "all blocking gates satisfied on the rehearsal track",
        "submitted_at": NOW,
        "reviewed_at": NOW + timedelta(hours=2),
    }
    payload.update(overrides)
    return PromotionApproval(**payload)


def test_submitter_cannot_review_their_own_promotion() -> None:
    with pytest.raises(ValidationError, match="FOUR_EYES_SUBMITTER_CANNOT_REVIEW"):
        approval(reviewed_by="maker@bank")


def test_reviewer_must_hold_a_different_role() -> None:
    with pytest.raises(ValidationError, match="DUPLICATE_REVIEWER_ROLE"):
        approval(reviewed_role="ENGINEERING")


def test_review_cannot_precede_submission() -> None:
    with pytest.raises(ValidationError, match="reviewed before it was submitted"):
        approval(reviewed_at=NOW - timedelta(hours=1))


def test_a_valid_four_eyes_approval_constructs() -> None:
    assert approval().decision == "APPROVED"


# --------------------------------------------------------------------------
# Virtual clock: simulated time is not bank time
# --------------------------------------------------------------------------


def clock(**overrides) -> VirtualClockState:
    payload = {
        "clock_id": "shadow-rehearsal",
        "simulation_clock": NOW,
        "rehearsal_days_elapsed": 47,
        "consecutive_clean_rehearsal_days": 30,
        "elapsed_bank_shadow_days": 0,
        "incidents_injected": 1,
    }
    payload.update(overrides)
    return VirtualClockState(**payload)


def test_a_rehearsal_can_never_record_an_elapsed_bank_day() -> None:
    with pytest.raises(ValidationError, match="elapsed_bank_shadow_days must be 0"):
        clock(elapsed_bank_shadow_days=30)


def test_clean_days_cannot_exceed_simulated_days() -> None:
    with pytest.raises(ValidationError, match="exceed total simulated days"):
        clock(rehearsal_days_elapsed=10, consecutive_clean_rehearsal_days=30)


def test_a_virtual_clock_cannot_run_on_the_real_track() -> None:
    with pytest.raises(ValidationError, match="cannot run on the REAL track"):
        clock(track=DecisionTrack.REAL)


def test_the_canonical_rehearsal_shape_constructs() -> None:
    """Thirty clean days out of forty-seven simulated, and zero bank days."""
    state = clock()
    assert state.consecutive_clean_rehearsal_days == 30
    assert state.elapsed_bank_shadow_days == 0


# --------------------------------------------------------------------------
# Incidents are isolated to the rehearsal
# --------------------------------------------------------------------------


def incident(**overrides) -> IncidentInjection:
    payload = {
        "incident_id": "inc-1",
        "scenario_id": "critical-reconciliation-break",
        "injected_on_rehearsal_day": 17,
        "severity": GateSeverity.CRITICAL,
        "description": "reconciliation breaks on day 17 and resets the counter",
        "expected_failing_gate_id": "reconciliation-exact",
        "simulation_clock": NOW,
    }
    payload.update(overrides)
    return IncidentInjection(**payload)


def test_a_simulated_incident_cannot_touch_the_real_track() -> None:
    with pytest.raises(ValidationError, match="cannot .*affect the real track"):
        incident(affects_real_track=True)


def test_a_critical_incident_must_reset_the_clean_counter() -> None:
    with pytest.raises(ValidationError, match="would let a broken run count as clean"):
        incident(resets_rehearsal_counter=False)


def test_a_non_critical_incident_need_not_reset() -> None:
    assert incident(
        severity=GateSeverity.STANDARD, resets_rehearsal_counter=False
    ).resets_rehearsal_counter is False


# --------------------------------------------------------------------------
# E3 sample-size planner: never manufacture a recommendation
# --------------------------------------------------------------------------


def plan(**overrides) -> E3SampleSizePlan:
    payload = {
        "plan_id": "e3-plan-1",
        "as_of": AS_OF,
        "target_coverage": 0.9,
        "target_half_width": 0.05,
        "tested_sample_sizes": [20, 50, 100, 150],
        "recommended_n": 100,
        "determination": "TARGET_REACHED_AT_N_100",
        "replications_per_n": 500,
    }
    payload.update(overrides)
    return E3SampleSizePlan(**payload)


def test_no_recommendation_requires_the_undetermined_sentinel() -> None:
    with pytest.raises(ValidationError, match="requires determination"):
        plan(recommended_n=None, determination="INCONCLUSIVE")


def test_the_sentinel_cannot_accompany_a_recommendation() -> None:
    with pytest.raises(ValidationError, match="says undetermined while recommending"):
        plan(determination=NOT_DETERMINED_UP_TO_150)


def test_an_untested_sample_size_cannot_be_recommended() -> None:
    with pytest.raises(ValidationError, match="was never tested"):
        plan(recommended_n=75, determination="TARGET_REACHED_AT_N_75")


def test_the_undetermined_outcome_is_representable() -> None:
    result = plan(recommended_n=None, determination=NOT_DETERMINED_UP_TO_150)
    assert result.recommended_n is None


# --------------------------------------------------------------------------
# Gate definitions and the catalogue
# --------------------------------------------------------------------------


def test_a_real_gate_cannot_declare_a_synthetic_minimum() -> None:
    definition = GATES_BY_ID["supply-chain-clean"]
    with pytest.raises(ValidationError, match="not .*satisfiable by simulation"):
        GateDefinition(
            **{
                **definition.model_dump(),
                "minimum_real_evidence_mode": SYNTHETIC,
            }
        )


def test_every_catalogue_gate_states_what_would_make_it_pass() -> None:
    """The field a reviewer actually acts on. A gate that cannot say what would
    satisfy it is a blocker, not a gate."""
    for gate in GATE_CATALOGUE:
        assert len(gate.what_would_make_real_pass) > 40, gate.gate_id
        assert len(gate.consequence_if_failed) > 40, gate.gate_id


def test_every_catalogue_gate_names_an_owner_and_a_separate_approver() -> None:
    for gate in GATE_CATALOGUE:
        assert gate.owner_role and gate.approver_role, gate.gate_id
        assert gate.owner_role != gate.approver_role, gate.gate_id


def test_gate_ids_are_unique() -> None:
    ids = [gate.gate_id for gate in GATE_CATALOGUE]
    assert len(ids) == len(set(ids))


def test_severity_weights_are_the_specified_five_three_one() -> None:
    assert SEVERITY_WEIGHTS == {"CRITICAL": 5, "HIGH": 3, "STANDARD": 1}


def test_bank_data_gates_demand_bank_evidence() -> None:
    """A gate about elapsed bank shadow days cannot be satisfied by a public
    artifact, however well signed."""
    assert (
        GATES_BY_ID["elapsed-clean-shadow-days"].minimum_real_evidence_mode is ATTESTED
    )
    assert GATES_BY_ID["randomised-trial-validated"].minimum_real_evidence_mode is ATTESTED
    assert (
        GATES_BY_ID["bank-approved-economics-registered"].minimum_real_evidence_mode
        is ATTESTED
    )


# --------------------------------------------------------------------------
# Evidence/gate binding
# --------------------------------------------------------------------------


def test_evidence_bound_to_another_gate_is_refused() -> None:
    ok, reason = evidence_supports_gate(
        GATES_BY_ID["supply-chain-clean"],
        evidence(gate_id="service-availability"),
        DecisionTrack.REAL,
    )
    assert not ok
    assert reason == "EVIDENCE_BOUND_TO_A_DIFFERENT_GATE"


def test_public_evidence_cannot_satisfy_a_bank_attested_gate() -> None:
    ok, reason = evidence_supports_gate(
        GATES_BY_ID["elapsed-clean-shadow-days"],
        evidence(gate_id="elapsed-clean-shadow-days", mode=PUBLIC),
        DecisionTrack.REAL,
    )
    assert not ok
    assert reason == "REQUIRES_AT_LEAST_BANK_ATTESTED_GOT_PUBLIC_PACKAGE"


def test_attested_evidence_satisfies_a_lower_minimum() -> None:
    ok, _ = evidence_supports_gate(
        GATES_BY_ID["supply-chain-clean"],
        evidence(mode=ATTESTED),
        DecisionTrack.REAL,
    )
    assert ok


def test_synthetic_evidence_is_refused_at_the_binding_layer_too() -> None:
    """Redundant with the GateEvaluation validator, deliberately: the two
    layers fail independently."""
    ok, reason = evidence_supports_gate(
        GATES_BY_ID["supply-chain-clean"],
        evidence(mode=SYNTHETIC),
        DecisionTrack.REAL,
    )
    assert not ok
    assert reason == "REFUSED_SYNTHETIC_EVIDENCE_ON_REAL_TRACK"


# --------------------------------------------------------------------------
# Rehearsal scenarios
# --------------------------------------------------------------------------


def test_a_negative_scenario_expecting_pass_is_refused() -> None:
    with pytest.raises(ValidationError, match="is not testing a gate"):
        RehearsalScenario(
            scenario_id="neg-1",
            title="reconciliation break",
            description="break reconciliation and expect the gate to hold",
            transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
            targeted_gate_ids=["reconciliation-exact"],
            expected_outcome=GateOutcome.PASS,
            is_negative_scenario=True,
        )


def test_a_scenario_must_target_a_gate() -> None:
    with pytest.raises(ValidationError, match="targets no gate"):
        RehearsalScenario(
            scenario_id="neg-2",
            title="untargeted",
            description="a scenario that names no gate proves nothing",
            transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
            targeted_gate_ids=[],
            expected_outcome=GateOutcome.FAIL,
            is_negative_scenario=True,
        )


def test_a_negative_scenario_expecting_failure_constructs() -> None:
    scenario = RehearsalScenario(
        scenario_id="neg-3",
        title="reconciliation break on day 17",
        description="inject a critical reconciliation failure mid-rehearsal",
        transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
        targeted_gate_ids=["reconciliation-exact"],
        expected_outcome=GateOutcome.FAIL,
        is_negative_scenario=True,
    )
    assert scenario.expected_outcome is GateOutcome.FAIL


# --------------------------------------------------------------------------
# States
# --------------------------------------------------------------------------


def test_promotion_states_are_the_specified_five_in_order() -> None:
    from wallet_twin_v32 import PROMOTION_ORDER

    assert PROMOTION_ORDER == (
        PromotionState.OFFLINE_CANDIDATE,
        PromotionState.SHADOW_READY,
        PromotionState.PILOT_READY,
        PromotionState.SCALE_READY,
        PromotionState.CAUSAL_CHAMPION,
    )
