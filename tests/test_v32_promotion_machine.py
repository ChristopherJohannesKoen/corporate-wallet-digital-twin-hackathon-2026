"""The promotion state machine, capabilities and the two scores.

These are the acceptance criteria that decide whether the twin is honest:
states cannot be skipped, a score never overrides a failed gate, synthetic
evidence contributes nothing to bank readiness, and the specific analytical
gaps (E3, economics, trial) disable exactly the claims they bear on and nothing
else.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List

import pytest

from wallet_twin_v32 import (
    GATE_CATALOGUE,
    DecisionTrack,
    GateEvaluation,
    GateOutcome,
    PromotionCapability,
    PromotionEvidenceMode,
    PromotionState,
    assert_no_composite_score,
    attained_state,
    capability_refusal_reason,
    compute_score,
    evaluate_promotion,
    gates_without_failure_injection,
    granted_capabilities,
    is_legal_transition,
    next_state,
    rank,
    resolve_legacy_alias,
    score_breakdown,
    transition_report,
    transition_satisfied,
)
from wallet_twin_v32.catalogue import GATES_BY_ID, gates_for_transition
from wallet_twin_v32.states import TRANSITION_IDS

AS_OF = date(2026, 6, 30)
NOW = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
SYNTHETIC = PromotionEvidenceMode.SYNTHETIC_REHEARSAL
PUBLIC = PromotionEvidenceMode.PUBLIC_PACKAGE
ATTESTED = PromotionEvidenceMode.BANK_ATTESTED

OFFLINE_TO_SHADOW, SHADOW_TO_PILOT, PILOT_TO_SCALE, SCALE_TO_CHAMPION = TRANSITION_IDS


def passes(
    gate_id: str,
    track: DecisionTrack,
    mode: PromotionEvidenceMode,
    *,
    injected: bool = False,
) -> GateEvaluation:
    return GateEvaluation(
        gate_id=gate_id,
        transition_id=GATES_BY_ID[gate_id].transition_id,
        track=track,
        outcome=GateOutcome.PASS,
        evidence_mode=mode,
        evidence_ids=[f"ev-{gate_id}"],
        evaluated_at=NOW,
        failure_injection_verified=injected,
    )


def fails(gate_id: str, track: DecisionTrack) -> GateEvaluation:
    return GateEvaluation(
        gate_id=gate_id,
        transition_id=GATES_BY_ID[gate_id].transition_id,
        track=track,
        outcome=GateOutcome.FAIL,
        evaluated_at=NOW,
    )


def pass_transition(
    transition: str, track: DecisionTrack, mode: PromotionEvidenceMode
) -> List[GateEvaluation]:
    """Pass every gate of a transition, honouring each gate's minimum mode."""
    results = []
    for gate in gates_for_transition(transition):
        effective = mode
        if track is DecisionTrack.REAL:
            # Use the strongest of the requested mode and the gate's minimum so
            # the helper cannot accidentally construct an inadmissible pass.
            from wallet_twin_v32.modes import satisfies_minimum

            if not satisfies_minimum(mode, gate.minimum_real_evidence_mode):
                effective = gate.minimum_real_evidence_mode
        results.append(passes(gate.gate_id, track, effective))
    return results


def rehearse_everything() -> List[GateEvaluation]:
    """A fully passing rehearsal across all four transitions."""
    results: List[GateEvaluation] = []
    for transition in TRANSITION_IDS:
        results.extend(pass_transition(transition, DecisionTrack.REHEARSAL, SYNTHETIC))
    return results


# --------------------------------------------------------------------------
# States cannot be skipped
# --------------------------------------------------------------------------


def test_no_transitions_means_offline_candidate() -> None:
    assert attained_state([]) is PromotionState.OFFLINE_CANDIDATE


def test_a_later_transition_alone_advances_nothing() -> None:
    """Passing SCALE→CHAMPION while OFFLINE→SHADOW fails grants no state."""
    assert attained_state([SCALE_TO_CHAMPION]) is PromotionState.OFFLINE_CANDIDATE


def test_a_gap_in_the_middle_stops_the_walk() -> None:
    attained = attained_state([OFFLINE_TO_SHADOW, PILOT_TO_SCALE, SCALE_TO_CHAMPION])
    assert attained is PromotionState.SHADOW_READY


def test_the_full_sequence_reaches_champion() -> None:
    assert attained_state(TRANSITION_IDS) is PromotionState.CAUSAL_CHAMPION


def test_only_adjacent_transitions_are_legal() -> None:
    assert is_legal_transition(
        PromotionState.OFFLINE_CANDIDATE, PromotionState.SHADOW_READY
    )
    assert not is_legal_transition(
        PromotionState.OFFLINE_CANDIDATE, PromotionState.PILOT_READY
    )
    assert not is_legal_transition(
        PromotionState.SHADOW_READY, PromotionState.OFFLINE_CANDIDATE
    )


def test_champion_has_no_successor() -> None:
    assert next_state(PromotionState.CAUSAL_CHAMPION) is None


# --------------------------------------------------------------------------
# A blocking gate is not overridden by anything
# --------------------------------------------------------------------------


def test_one_failed_blocking_gate_blocks_the_transition() -> None:
    evaluations = pass_transition(OFFLINE_TO_SHADOW, DecisionTrack.REAL, ATTESTED)
    evaluations = [
        item for item in evaluations if item.gate_id != "prompt-injection-resistance"
    ]
    evaluations.append(fails("prompt-injection-resistance", DecisionTrack.REAL))
    satisfied, reasons = transition_satisfied(
        OFFLINE_TO_SHADOW, evaluations, DecisionTrack.REAL
    )
    assert not satisfied
    assert "FAIL:prompt-injection-resistance" in reasons


def test_an_unevaluated_blocking_gate_blocks() -> None:
    """UNKNOWN is not a pass. A missing evaluation is not an absent problem."""
    evaluations = pass_transition(OFFLINE_TO_SHADOW, DecisionTrack.REAL, ATTESTED)[:-1]
    satisfied, reasons = transition_satisfied(
        OFFLINE_TO_SHADOW, evaluations, DecisionTrack.REAL
    )
    assert not satisfied
    assert any(reason.startswith("NOT_EVALUATED:") for reason in reasons)


def test_a_high_score_never_overrides_a_failed_gate() -> None:
    """The scores are reporting, not authorisation."""
    evaluations = rehearse_everything()
    evaluations.append(fails("prompt-injection-resistance", DecisionTrack.REAL))
    decision = evaluate_promotion(evaluations, decision_id="d-1", as_of=AS_OF)
    assert decision.score.promotion_machinery_readiness == 1.0
    assert decision.real_state is PromotionState.OFFLINE_CANDIDATE
    assert decision.bank_shadow_authorized is False


def test_a_non_blocking_gate_failure_does_not_block() -> None:
    """E3 is non-blocking by design: it gates a claim, not the transition."""
    assert GATES_BY_ID["e3-multibank-observation-approved"].blocking is False
    evaluations = pass_transition(PILOT_TO_SCALE, DecisionTrack.REAL, ATTESTED)
    evaluations = [
        item
        for item in evaluations
        if item.gate_id != "e3-multibank-observation-approved"
    ]
    evaluations.append(fails("e3-multibank-observation-approved", DecisionTrack.REAL))
    satisfied, _ = transition_satisfied(
        PILOT_TO_SCALE, evaluations, DecisionTrack.REAL
    )
    assert satisfied


# --------------------------------------------------------------------------
# Capabilities: the specific gaps disable exactly what they bear on
# --------------------------------------------------------------------------


def test_missing_e3_disables_measured_share_without_blocking_hidden_shadow() -> None:
    verdicts = granted_capabilities(PromotionState.SHADOW_READY, [])
    assert verdicts[PromotionCapability.HIDDEN_SHADOW_SCORING] is True
    assert verdicts[PromotionCapability.MEASURED_SHARE_REPORTING] is False
    reason = capability_refusal_reason(
        PromotionCapability.MEASURED_SHARE_REPORTING, PromotionState.SHADOW_READY, []
    )
    assert reason == "REQUIRES_REAL_GATES_e3-multibank-observation-approved"


def test_e3_present_enables_measured_share() -> None:
    verdicts = granted_capabilities(
        PromotionState.SHADOW_READY, ["e3-multibank-observation-approved"]
    )
    assert verdicts[PromotionCapability.MEASURED_SHARE_REPORTING] is True


def test_missing_economics_disables_the_commercial_value_claim() -> None:
    verdicts = granted_capabilities(
        PromotionState.SCALE_READY, ["e3-multibank-observation-approved"]
    )
    assert verdicts[PromotionCapability.COMMERCIAL_VALUE_CLAIM] is False
    assert verdicts[PromotionCapability.PRODUCTION_RM_DECISION_SUPPORT] is True


def test_a_null_trial_leaves_the_system_scale_ready() -> None:
    """The honest outcome of a trial that found nothing is a null result, not a
    demotion and not a champion."""
    evaluations: List[GateEvaluation] = []
    for transition in (OFFLINE_TO_SHADOW, SHADOW_TO_PILOT, PILOT_TO_SCALE):
        evaluations.extend(pass_transition(transition, DecisionTrack.REAL, ATTESTED))
    evaluations.append(fails("randomised-trial-validated", DecisionTrack.REAL))

    decision = evaluate_promotion(evaluations, decision_id="d-null", as_of=AS_OF)
    assert decision.real_state is PromotionState.SCALE_READY
    assert PromotionCapability.CAUSAL_VALUE_CLAIM not in decision.granted_capabilities
    assert PromotionCapability.PRODUCTION_RM_DECISION_SUPPORT in decision.granted_capabilities


def test_a_weak_first_stage_also_withholds_the_causal_claim() -> None:
    reason = capability_refusal_reason(
        PromotionCapability.CAUSAL_VALUE_CLAIM,
        PromotionState.CAUSAL_CHAMPION,
        ["randomised-trial-validated"],
    )
    assert reason == "REQUIRES_REAL_GATES_trial-first-stage-strength-adequate"


def test_autonomous_client_action_is_refused_at_every_state() -> None:
    for state in PromotionState:
        verdicts = granted_capabilities(
            state, [gate.gate_id for gate in GATE_CATALOGUE]
        )
        assert verdicts[PromotionCapability.AUTONOMOUS_CLIENT_ACTION] is False
    assert (
        capability_refusal_reason(
            PromotionCapability.AUTONOMOUS_CLIENT_ACTION,
            PromotionState.CAUSAL_CHAMPION,
            [gate.gate_id for gate in GATE_CATALOGUE],
        )
        == "PERMANENTLY_WITHHELD_BY_DESIGN"
    )


def test_offline_analysis_is_available_from_the_start() -> None:
    verdicts = granted_capabilities(PromotionState.OFFLINE_CANDIDATE, [])
    assert verdicts[PromotionCapability.OFFLINE_ANALYSIS] is True
    assert verdicts[PromotionCapability.SYNTHETIC_DEMONSTRATION] is True
    assert verdicts[PromotionCapability.HIDDEN_SHADOW_SCORING] is False


# --------------------------------------------------------------------------
# Scoring: synthetic contributes nothing to bank readiness
# --------------------------------------------------------------------------


def test_a_perfect_rehearsal_scores_zero_bank_evidence_readiness() -> None:
    """The single most important property in the package."""
    score = compute_score(rehearse_everything())
    assert score.promotion_machinery_readiness == 1.0
    assert score.bank_evidence_readiness == 0.0
    assert score.synthetic_weight_excluded_from_ber == score.pmr_weight_available


def test_no_evaluations_scores_zero_on_both() -> None:
    score = compute_score([])
    assert score.promotion_machinery_readiness == 0.0
    assert score.bank_evidence_readiness == 0.0


def test_public_evidence_earns_partial_bank_readiness() -> None:
    """A signed image is real evidence about the supply chain and should not
    score as a bank attestation."""
    score = compute_score([passes("supply-chain-clean", DecisionTrack.REAL, PUBLIC)])
    weight = 3  # supply-chain-clean is HIGH
    assert score.ber_weight_earned == pytest.approx(weight * 0.5)


def test_attested_evidence_earns_full_weight() -> None:
    score = compute_score([passes("supply-chain-clean", DecisionTrack.REAL, ATTESTED)])
    assert score.ber_weight_earned == pytest.approx(3.0)


def test_a_real_waiver_earns_no_bank_readiness() -> None:
    """A waiver is a decision to proceed without evidence, not evidence."""
    waived = GateEvaluation(
        gate_id="supply-chain-clean",
        transition_id=OFFLINE_TO_SHADOW,
        track=DecisionTrack.REAL,
        outcome=GateOutcome.WAIVED,
        waived_by="security-officer",
        waiver_rationale="accepted risk, compensating control",
        evaluated_at=NOW,
    )
    score = compute_score([waived])
    assert score.ber_weight_earned == 0.0
    assert score.waived_gate_count == 1


def test_a_later_evaluation_supersedes_an_earlier_one() -> None:
    early = passes("supply-chain-clean", DecisionTrack.REAL, ATTESTED)
    late = fails("supply-chain-clean", DecisionTrack.REAL).model_copy(
        update={"evaluated_at": NOW.replace(hour=18)}
    )
    score = compute_score([early, late])
    assert score.ber_weight_earned == 0.0


def test_the_two_scores_are_never_combined() -> None:
    score = compute_score(rehearse_everything())
    payload = score.model_dump()
    assert_no_composite_score(payload)
    assert "promotion_machinery_readiness" in payload
    assert "bank_evidence_readiness" in payload


def test_a_composite_score_is_rejected_if_one_is_reintroduced() -> None:
    with pytest.raises(ValueError, match="composite promotion score present"):
        assert_no_composite_score({"promotability_percent": 62.0})


def test_severity_weighting_means_critical_outweighs_standard() -> None:
    critical = compute_score(
        [passes("prompt-injection-resistance", DecisionTrack.REAL, ATTESTED)]
    )
    standard = compute_score(
        [passes("event-latency", DecisionTrack.REAL, ATTESTED)]
    )
    assert critical.ber_weight_earned == 5.0
    assert standard.ber_weight_earned == 1.0


# --------------------------------------------------------------------------
# The published decision
# --------------------------------------------------------------------------


def test_the_honest_hackathon_position_is_representable_and_correct() -> None:
    """A perfect rehearsal, no bank evidence at all — the V3.2 release state."""
    decision = evaluate_promotion(
        rehearse_everything(), decision_id="d-release", as_of=AS_OF
    )
    assert decision.real_state is PromotionState.OFFLINE_CANDIDATE
    assert decision.rehearsed_state is PromotionState.CAUSAL_CHAMPION
    assert decision.bank_shadow_authorized is False
    assert decision.passed_real_transitions == []
    assert len(decision.passed_rehearsal_transitions) == 4
    assert "REHEARSAL_AHEAD_OF_REAL_AS_EXPECTED" in decision.reason_codes
    assert decision.score.bank_evidence_readiness == 0.0


def test_bank_shadow_authorized_tracks_the_real_state_only() -> None:
    evaluations = rehearse_everything()
    evaluations.extend(pass_transition(OFFLINE_TO_SHADOW, DecisionTrack.REAL, ATTESTED))
    decision = evaluate_promotion(evaluations, decision_id="d-2", as_of=AS_OF)
    assert decision.real_state is PromotionState.SHADOW_READY
    assert decision.bank_shadow_authorized is True
    assert decision.score.bank_evidence_readiness > 0.0


def test_refused_capabilities_always_carry_a_reason() -> None:
    decision = evaluate_promotion(
        rehearse_everything(), decision_id="d-3", as_of=AS_OF
    )
    assert decision.refused_capabilities
    for capability, reason in decision.refused_capabilities.items():
        assert reason, capability
    granted = {item.value for item in decision.granted_capabilities}
    assert not granted & set(decision.refused_capabilities)


def test_the_transition_report_shows_both_tracks_for_every_transition() -> None:
    report = transition_report(rehearse_everything())
    assert len(report) == 4
    for row in report:
        assert row["rehearsal_satisfied"] is True
        assert row["real_satisfied"] is False
        assert row["real_reason_codes"]


def test_the_breakdown_names_what_would_make_each_real_gate_pass() -> None:
    breakdown = score_breakdown(rehearse_everything())
    assert len(breakdown) == len(GATE_CATALOGUE)
    for gate_id, row in breakdown.items():
        assert row["real_outcome"] == "NOT_EVALUATED"
        assert row["rehearsal_outcome"] == "PASS"
        assert row["ber_contribution"] == 0.0
        assert row["what_would_make_real_pass"], gate_id


# --------------------------------------------------------------------------
# Failure injection and legacy vocabulary
# --------------------------------------------------------------------------


def test_gates_never_seen_failing_are_reported_not_silently_counted() -> None:
    unverified = gates_without_failure_injection(rehearse_everything())
    assert len(unverified) == len(GATE_CATALOGUE)

    injected = [passes("reconciliation-exact", DecisionTrack.REHEARSAL, SYNTHETIC, injected=True)]
    assert "reconciliation-exact" not in gates_without_failure_injection(injected)


def test_legacy_gate_vocabularies_both_resolve_to_one_catalogue() -> None:
    """release_gates.py and the MLflow policy named the same requirement two
    different ways; both now map to one gate."""
    assert resolve_legacy_alias("interval-coverage-90") == "interval-coverage-90"
    assert (
        resolve_legacy_alias("90pct_coverage_between_85pct_and_95pct")
        == "interval-coverage-90"
    )
    assert resolve_legacy_alias("pit-zero-leakage") == "point-in-time-zero-leakage"
    assert (
        resolve_legacy_alias("zero_point_in_time_leakage")
        == "point-in-time-zero-leakage"
    )
    assert resolve_legacy_alias("no-such-gate") is None


def test_every_legacy_alias_maps_to_a_real_catalogue_gate() -> None:
    from wallet_twin_v32.catalogue import LEGACY_GATE_ALIASES

    for gate_id in LEGACY_GATE_ALIASES:
        assert gate_id in GATES_BY_ID, gate_id


def test_rank_orders_the_states() -> None:
    assert rank(PromotionState.OFFLINE_CANDIDATE) < rank(PromotionState.SHADOW_READY)
    assert rank(PromotionState.SCALE_READY) < rank(PromotionState.CAUSAL_CHAMPION)
