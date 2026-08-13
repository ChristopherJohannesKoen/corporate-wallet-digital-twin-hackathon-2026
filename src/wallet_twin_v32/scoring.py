"""Two scores, kept apart on purpose.

**PMR — Promotion Machinery Readiness.** Does the promotion apparatus work? Do
gates fire, does evidence bind, do signatures verify, do injected incidents
reset the counters they should? Computed on the rehearsal track, where
synthetic evidence is exactly what ought to count.

**BER — Bank Evidence Readiness.** Does the *bank* have the evidence? Computed
on the real track, where synthetic evidence contributes **zero**.

There is deliberately no third number combining them. A composite would let a
PMR near 1.0 pull a BER of 0.0 up to a comfortable-looking middle, and a reader
skimming one figure would come away believing the system is halfway to
production when the bank has authorised nothing at all. The two numbers
disagreeing *is* the finding — averaging them destroys it.

``synthetic_weight_excluded_from_ber`` makes the gap explicit: it is the gate
weight that passes under simulation and has no real-track support. Publishing it
turns "BER is low" into "here is precisely how much of this readiness is
simulated".
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from .catalogue import GATE_CATALOGUE, severity_weight
from .contracts import (
    GateDefinition,
    GateEvaluation,
    GateOutcome,
    PromotionScore,
)
from .modes import DecisionTrack, bank_evidence_weight

SCORING_VERSION = "v32-promotion-scoring-1.0.0"


def _evaluations_on(
    evaluations: Iterable[GateEvaluation], track: DecisionTrack
) -> Dict[str, GateEvaluation]:
    """Latest evaluation per gate on one track.

    Later evaluations supersede earlier ones for the same gate; a gate
    re-evaluated after evidence was refreshed should not be counted twice.
    """
    latest: Dict[str, GateEvaluation] = {}
    for evaluation in evaluations:
        if evaluation.track is not track:
            continue
        existing = latest.get(evaluation.gate_id)
        if existing is None or evaluation.evaluated_at >= existing.evaluated_at:
            latest[evaluation.gate_id] = evaluation
    return latest


def _available_weight(gates: Sequence[GateDefinition]) -> int:
    return sum(severity_weight(gate) for gate in gates)


def compute_score(
    evaluations: Iterable[GateEvaluation],
    gates: Sequence[GateDefinition] = GATE_CATALOGUE,
) -> PromotionScore:
    """PMR and BER over the whole catalogue."""
    evaluations = list(evaluations)
    available = float(_available_weight(gates))

    rehearsal = _evaluations_on(evaluations, DecisionTrack.REHEARSAL)
    real = _evaluations_on(evaluations, DecisionTrack.REAL)

    pmr_earned = 0.0
    ber_earned = 0.0
    synthetic_excluded = 0.0
    waived = 0

    for gate in gates:
        weight = float(severity_weight(gate))

        rehearsal_evaluation = rehearsal.get(gate.gate_id)
        if rehearsal_evaluation is not None and rehearsal_evaluation.satisfied():
            pmr_earned += weight
            if rehearsal_evaluation.outcome is GateOutcome.WAIVED:
                waived += 1

        real_evaluation = real.get(gate.gate_id)
        if real_evaluation is not None and real_evaluation.satisfied():
            # A real-track evaluation cannot carry synthetic evidence — the
            # GateEvaluation validator refuses it — so this factor is 0.5, 0.8
            # or 1.0. A WAIVED real gate has no evidence mode and earns nothing
            # toward BER: a waiver is a decision to proceed without evidence,
            # not evidence.
            if real_evaluation.evidence_mode is not None:
                ber_earned += weight * bank_evidence_weight(
                    real_evaluation.evidence_mode
                )
            if real_evaluation.outcome is GateOutcome.WAIVED:
                waived += 1
        elif rehearsal_evaluation is not None and rehearsal_evaluation.satisfied():
            # Passes under simulation, unsupported in reality. This is the
            # number that keeps a high PMR from reading as progress toward
            # production.
            synthetic_excluded += weight

    return PromotionScore(
        promotion_machinery_readiness=round(pmr_earned / available, 6) if available else 0.0,
        bank_evidence_readiness=round(ber_earned / available, 6) if available else 0.0,
        pmr_weight_earned=round(pmr_earned, 6),
        pmr_weight_available=available,
        ber_weight_earned=round(ber_earned, 6),
        ber_weight_available=available,
        synthetic_weight_excluded_from_ber=round(synthetic_excluded, 6),
        waived_gate_count=waived,
    )


def transition_satisfied(
    transition: str,
    evaluations: Iterable[GateEvaluation],
    track: DecisionTrack,
) -> Tuple[bool, List[str]]:
    """Whether every blocking gate of a transition is satisfied on a track.

    Returns the verdict and the reason codes behind it. An unevaluated blocking
    gate blocks — ``UNKNOWN`` is not a pass, and treating a missing evaluation
    as absence of a problem is how promotion machinery quietly stops working.
    """
    latest = _evaluations_on(evaluations, track)
    reasons: List[str] = []
    satisfied = True

    for gate in GATE_CATALOGUE:
        if gate.transition_id != transition or not gate.blocking:
            continue
        evaluation = latest.get(gate.gate_id)
        if evaluation is None:
            satisfied = False
            reasons.append(f"NOT_EVALUATED:{gate.gate_id}")
        elif not evaluation.satisfied():
            satisfied = False
            reasons.append(f"{evaluation.outcome.value}:{gate.gate_id}")
    if satisfied:
        reasons.append(f"ALL_BLOCKING_GATES_SATISFIED_ON_{track.value}")
    return satisfied, reasons


def passed_gate_ids(
    evaluations: Iterable[GateEvaluation], track: DecisionTrack
) -> List[str]:
    """Gate ids satisfied on a track, for capability resolution."""
    latest = _evaluations_on(evaluations, track)
    return sorted(
        gate_id for gate_id, evaluation in latest.items() if evaluation.satisfied()
    )


def unevaluated_gates(
    evaluations: Iterable[GateEvaluation], track: DecisionTrack
) -> List[str]:
    """Gates in the catalogue with no evaluation on this track."""
    latest = _evaluations_on(evaluations, track)
    return sorted(gate.gate_id for gate in GATE_CATALOGUE if gate.gate_id not in latest)


def gates_without_failure_injection(
    evaluations: Iterable[GateEvaluation],
) -> List[str]:
    """Gates never observed failing under a deliberately injected fault.

    A gate with only a positive test has not been shown to be a gate — it has
    been shown to be a line that returns True. This list is published rather
    than used to reduce a score, because it measures test coverage of the
    machinery rather than the bank's evidence.
    """
    verified = {
        evaluation.gate_id
        for evaluation in evaluations
        if evaluation.failure_injection_verified
    }
    return sorted(gate.gate_id for gate in GATE_CATALOGUE if gate.gate_id not in verified)


def score_breakdown(
    evaluations: Iterable[GateEvaluation],
) -> Mapping[str, Mapping[str, object]]:
    """Per-gate contribution to each score, for the workbench register."""
    evaluations = list(evaluations)
    rehearsal = _evaluations_on(evaluations, DecisionTrack.REHEARSAL)
    real = _evaluations_on(evaluations, DecisionTrack.REAL)
    breakdown: Dict[str, Mapping[str, object]] = {}

    for gate in GATE_CATALOGUE:
        real_evaluation = real.get(gate.gate_id)
        rehearsal_evaluation = rehearsal.get(gate.gate_id)
        weight = severity_weight(gate)
        real_mode = real_evaluation.evidence_mode if real_evaluation else None
        breakdown[gate.gate_id] = {
            "severity": gate.severity.value,
            "weight": weight,
            "blocking": gate.blocking,
            "real_outcome": real_evaluation.outcome.value if real_evaluation else "NOT_EVALUATED",
            "rehearsal_outcome": (
                rehearsal_evaluation.outcome.value
                if rehearsal_evaluation
                else "NOT_EVALUATED"
            ),
            "real_evidence_mode": real_mode.value if real_mode else None,
            "ber_contribution": round(
                weight * bank_evidence_weight(real_mode), 6
            )
            if real_mode and real_evaluation and real_evaluation.satisfied()
            else 0.0,
            "failure_injection_verified": bool(
                (real_evaluation and real_evaluation.failure_injection_verified)
                or (rehearsal_evaluation and rehearsal_evaluation.failure_injection_verified)
            ),
            "what_would_make_real_pass": gate.what_would_make_real_pass,
        }
    return breakdown


def assert_no_composite_score(payload: Mapping[str, object]) -> None:
    """Guard against a composite creeping back in.

    Used by tests and the exporter. The prohibition is a design decision that
    would otherwise be easy to undo by accident in a later refactor, so it is
    enforced mechanically rather than left to review.
    """
    forbidden = {
        "overall_readiness",
        "promotability",
        "promotability_percent",
        "composite_score",
        "readiness_score",
        "overall_score",
    }
    present = sorted(forbidden & set(payload))
    if present:
        raise ValueError(
            "composite promotion score present: "
            + ",".join(present)
            + " — PMR and BER must be published separately so a working "
            "rehearsal cannot read as bank readiness"
        )


__all__ = [
    "SCORING_VERSION",
    "assert_no_composite_score",
    "compute_score",
    "gates_without_failure_injection",
    "passed_gate_ids",
    "score_breakdown",
    "transition_satisfied",
    "unevaluated_gates",
]
