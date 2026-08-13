"""Corporate Wallet Digital Twin V3.2 — Promotion Readiness Twin.

V3.2 extends V3.1 rather than replacing it. V2 remains the governed evidence and
economics substrate, V3 the latent-structure layer, V3.1 the decision object a
banker acts on — and V3.2 adds the question none of them can answer:

    Is this system allowed to be used, and for what?

Every gate is evaluated twice. The **REAL** track governs actual bank
authorisation. The **REHEARSAL** track proves the promotion machinery works.
Keeping them apart is the entire design: a rehearsal in which every gate passes
demonstrates that the apparatus functions and demonstrates nothing whatever
about whether a bank has approved anything.

Three properties hold by construction rather than by convention:

- Synthetic evidence cannot support a real-track verdict. The type refuses it,
  the mode algebra refuses it, and the trust registry refuses to sign it.
- Synthetic evidence contributes zero to Bank Evidence Readiness, so a fully
  rehearsed system scores zero on the number that describes the bank.
- PMR and BER are never combined. A composite would let a working rehearsal
  read as progress toward production, which is the precise misreading this twin
  exists to prevent.

Bank production status remains ``NOT_PROMOTABLE``.
"""

from .catalogue import (
    CATALOGUE_VERSION,
    GATE_CATALOGUE,
    GATES_BY_ID,
    blocking_gates_for_transition,
    catalogue_summary,
    gates_for_transition,
    resolve_legacy_alias,
)
from .contracts import (
    CONTRACTS_VERSION,
    NOT_DETERMINED_UP_TO_150,
    SEVERITY_WEIGHTS,
    E3SampleSizePlan,
    GateDefinition,
    GateEvaluation,
    GateEvidence,
    GateOutcome,
    GateSeverity,
    IncidentInjection,
    PromotionApproval,
    PromotionDecision,
    PromotionScore,
    RehearsalScenario,
    SignedEvidenceEnvelope,
    VirtualClockState,
    evidence_supports_gate,
)
from .engine import (
    ENGINE_VERSION,
    capability_register,
    evaluate_promotion,
    passed_transitions,
    transition_report,
)
from .modes import (
    EVIDENCE_MODE_POLICY_VERSION,
    DecisionTrack,
    PromotionEvidenceMode,
    admits_track,
    bank_evidence_weight,
    is_synthetic,
    satisfies_minimum,
)
from .scoring import (
    SCORING_VERSION,
    assert_no_composite_score,
    compute_score,
    gates_without_failure_injection,
    passed_gate_ids,
    score_breakdown,
    transition_satisfied,
    unevaluated_gates,
)
from .states import (
    PROMOTION_ORDER,
    STATE_MACHINE_VERSION,
    TRANSITION_IDS,
    TRANSITIONS,
    PromotionCapability,
    PromotionState,
    attained_state,
    capability_refusal_reason,
    granted_capabilities,
    is_legal_transition,
    next_state,
    rank,
    transition_id,
)

__all__ = [
    "CATALOGUE_VERSION",
    "CONTRACTS_VERSION",
    "DecisionTrack",
    "E3SampleSizePlan",
    "ENGINE_VERSION",
    "EVIDENCE_MODE_POLICY_VERSION",
    "GATES_BY_ID",
    "GATE_CATALOGUE",
    "GateDefinition",
    "GateEvaluation",
    "GateEvidence",
    "GateOutcome",
    "GateSeverity",
    "IncidentInjection",
    "NOT_DETERMINED_UP_TO_150",
    "PROMOTION_ORDER",
    "PromotionApproval",
    "PromotionCapability",
    "PromotionDecision",
    "PromotionEvidenceMode",
    "PromotionScore",
    "PromotionState",
    "RehearsalScenario",
    "SCORING_VERSION",
    "SEVERITY_WEIGHTS",
    "STATE_MACHINE_VERSION",
    "SignedEvidenceEnvelope",
    "TRANSITIONS",
    "TRANSITION_IDS",
    "VirtualClockState",
    "admits_track",
    "assert_no_composite_score",
    "attained_state",
    "bank_evidence_weight",
    "blocking_gates_for_transition",
    "capability_refusal_reason",
    "capability_register",
    "catalogue_summary",
    "compute_score",
    "evaluate_promotion",
    "evidence_supports_gate",
    "gates_for_transition",
    "gates_without_failure_injection",
    "granted_capabilities",
    "is_legal_transition",
    "is_synthetic",
    "next_state",
    "passed_gate_ids",
    "passed_transitions",
    "rank",
    "resolve_legacy_alias",
    "satisfies_minimum",
    "score_breakdown",
    "transition_id",
    "transition_report",
    "transition_satisfied",
    "unevaluated_gates",
]

__version__ = "3.2.0"
