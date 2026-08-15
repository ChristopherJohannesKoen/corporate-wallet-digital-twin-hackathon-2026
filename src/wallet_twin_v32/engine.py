"""Assemble a promotion position from gate evaluations.

Everything here is a pure function of the evaluations and accountable approvals
supplied. The engine never reads a stored state and never trusts one:
``real_state`` is recomputed cumulatively from transitions whose gates still
pass *and* whose latest four-eyes decision is APPROVED. Passing metrics alone
can therefore issue a recommendation but can never promote the system.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Sequence

from .catalogue import CATALOGUE_VERSION, GATE_CATALOGUE
from .contracts import (
    CONTRACTS_VERSION,
    GateEvaluation,
    PromotionApproval,
    PromotionDecision,
)
from .modes import DecisionTrack
from .scoring import (
    compute_score,
    passed_gate_ids,
    transition_satisfied,
    unevaluated_gates,
)
from .states import (
    STATE_MACHINE_VERSION,
    TRANSITION_IDS,
    PromotionCapability,
    PromotionState,
    attained_state,
    capability_refusal_reason,
    granted_capabilities,
    rank,
)

ENGINE_VERSION = "v32-promotion-engine-1.1.0"


def passed_transitions(
    evaluations: Iterable[GateEvaluation], track: DecisionTrack
) -> List[str]:
    """Transitions whose blocking gates are all satisfied on a track.

    Evaluated over every transition rather than stopping at the first failure,
    because a later transition passing while an earlier one fails is a real and
    reportable condition — it just does not advance the state.
    ``attained_state`` handles the ordering.
    """
    evaluations = list(evaluations)
    return [
        transition
        for transition in TRANSITION_IDS
        if transition_satisfied(transition, evaluations, track)[0]
    ]


def approved_transitions(
    approvals: Iterable[PromotionApproval], track: DecisionTrack, decision_id: str
) -> List[str]:
    """Transitions with a current, explicit four-eyes approval on one track."""
    latest: Dict[str, PromotionApproval] = {}
    for approval in approvals:
        if approval.track is not track or approval.decision_id != decision_id:
            continue
        existing = latest.get(approval.transition_id)
        if existing is None or approval.reviewed_at >= existing.reviewed_at:
            latest[approval.transition_id] = approval
    return [
        transition
        for transition in TRANSITION_IDS
        if transition in latest and latest[transition].decision == "APPROVED"
    ]


def evaluate_promotion(
    evaluations: Sequence[GateEvaluation],
    *,
    approvals: Sequence[PromotionApproval] = (),
    decision_id: str,
    as_of: date,
    generated_at: Optional[datetime] = None,
    published_at: Optional[datetime] = None,
) -> PromotionDecision:
    """The published promotion position, both tracks side by side."""
    real_gate_ready = passed_transitions(evaluations, DecisionTrack.REAL)
    rehearsal_gate_ready = passed_transitions(evaluations, DecisionTrack.REHEARSAL)
    real_approved = set(
        approved_transitions(approvals, DecisionTrack.REAL, decision_id)
    )
    rehearsal_approved = set(
        approved_transitions(approvals, DecisionTrack.REHEARSAL, decision_id)
    )

    real_transitions = [item for item in real_gate_ready if item in real_approved]
    rehearsal_transitions = [
        item for item in rehearsal_gate_ready if item in rehearsal_approved
    ]

    real_state = attained_state(real_transitions)
    rehearsed_state = attained_state(rehearsal_transitions)

    real_passed_gates = passed_gate_ids(evaluations, DecisionTrack.REAL)
    verdicts = granted_capabilities(real_state, real_passed_gates)

    granted = [
        capability for capability, allowed in verdicts.items() if allowed
    ]
    refused: Dict[str, str] = {}
    for capability, allowed in verdicts.items():
        if allowed:
            continue
        reason = capability_refusal_reason(capability, real_state, real_passed_gates)
        refused[capability.value] = reason or "REFUSED"

    reason_codes: List[str] = [
        f"REAL_STATE_{real_state.value}",
        f"REHEARSED_STATE_{rehearsed_state.value}",
        f"CATALOGUE_{CATALOGUE_VERSION}",
    ]
    outstanding = unevaluated_gates(evaluations, DecisionTrack.REAL)
    if outstanding:
        reason_codes.append(f"REAL_GATES_NOT_EVALUATED_{len(outstanding)}")
    real_waiting_approval = set(real_gate_ready) - real_approved
    rehearsal_waiting_approval = set(rehearsal_gate_ready) - rehearsal_approved
    if real_waiting_approval:
        reason_codes.append(
            f"REAL_TRANSITIONS_AWAITING_APPROVAL_{len(real_waiting_approval)}"
        )
    if rehearsal_waiting_approval:
        reason_codes.append(
            "REHEARSAL_TRANSITIONS_AWAITING_APPROVAL_"
            f"{len(rehearsal_waiting_approval)}"
        )
    if rank(rehearsed_state) > rank(real_state):
        # Worth stating explicitly rather than leaving to the reader: the
        # rehearsal is ahead of the bank, which is the expected and honest
        # condition for a system that has never run at a bank.
        reason_codes.append("REHEARSAL_AHEAD_OF_REAL_AS_EXPECTED")

    kwargs = {}
    if generated_at is not None:
        kwargs["generated_at"] = generated_at

    return PromotionDecision(
        decision_id=decision_id,
        as_of=as_of,
        published_at=published_at,
        real_state=real_state,
        rehearsed_state=rehearsed_state,
        # Authorisation is a fact about the real track only. It is stored
        # explicitly so no consumer has to infer it, and validated against
        # real_state so the two cannot drift apart.
        bank_shadow_authorized=rank(real_state) >= rank(PromotionState.SHADOW_READY),
        passed_real_transitions=real_transitions,
        passed_rehearsal_transitions=rehearsal_transitions,
        granted_capabilities=sorted(granted, key=lambda item: item.value),
        refused_capabilities=refused,
        score=compute_score(evaluations),
        state_machine_version=STATE_MACHINE_VERSION,
        contracts_version=CONTRACTS_VERSION,
        reason_codes=reason_codes,
        **kwargs,
    )


def transition_report(
    evaluations: Sequence[GateEvaluation],
) -> List[Dict[str, object]]:
    """Per-transition, per-track detail for the workbench.

    Both tracks for every transition, always. A view that renders only the
    track with something to show would make an empty real track look like an
    absent question rather than an unanswered one.
    """
    report: List[Dict[str, object]] = []
    for transition in TRANSITION_IDS:
        real_ok, real_reasons = transition_satisfied(
            transition, evaluations, DecisionTrack.REAL
        )
        rehearsal_ok, rehearsal_reasons = transition_satisfied(
            transition, evaluations, DecisionTrack.REHEARSAL
        )
        gates = [gate for gate in GATE_CATALOGUE if gate.transition_id == transition]
        report.append(
            {
                "transition_id": transition,
                "gate_count": len(gates),
                "blocking_gate_count": sum(1 for gate in gates if gate.blocking),
                "real_satisfied": real_ok,
                "real_reason_codes": real_reasons,
                "rehearsal_satisfied": rehearsal_ok,
                "rehearsal_reason_codes": rehearsal_reasons,
            }
        )
    return report


def capability_register(
    decision: PromotionDecision,
) -> List[Dict[str, object]]:
    """Every capability with its verdict and, when refused, why.

    Includes the refused ones by design. A register of what is allowed, with
    refusals omitted, cannot be audited for whether the right things are
    refused.
    """
    granted = set(decision.granted_capabilities)
    rows: List[Dict[str, object]] = []
    for capability in PromotionCapability:
        rows.append(
            {
                "capability": capability.value,
                "granted": capability in granted,
                "refusal_reason": decision.refused_capabilities.get(capability.value),
            }
        )
    return rows
