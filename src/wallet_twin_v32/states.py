"""The promotion state machine and what each state permits.

V3.1.1 answers "what should the banker do?". It cannot answer "is this system
allowed to be used, and for what?" — that question has no representation
anywhere in V1-V3.1. This module gives it one.

Five states, strictly ordered::

    OFFLINE_CANDIDATE → SHADOW_READY → PILOT_READY → SCALE_READY → CAUSAL_CHAMPION

The ordering is the point. A state is reached by satisfying every blocking gate
of every transition up to it, so states cannot be skipped and a later state
cannot be claimed while an earlier gate fails. ``attained_state`` computes this
cumulatively rather than trusting a stored value.

Capabilities are deliberately **not** a function of state alone. A system can be
SHADOW_READY — operationally sound enough to score in hidden shadow — while
still being unable to report a measured competitor share, because that specific
claim needs E3 multibank observation that no gate about operational readiness
covers. Tying capability to state alone would let operational maturity silently
license an analytical claim it says nothing about.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet, Iterable, Mapping, Optional, Tuple

STATE_MACHINE_VERSION = "v32-promotion-state-machine-1.0.0"


class PromotionState(str, Enum):
    """What the system is authorised to be, not how good its numbers are."""

    OFFLINE_CANDIDATE = "OFFLINE_CANDIDATE"
    SHADOW_READY = "SHADOW_READY"
    PILOT_READY = "PILOT_READY"
    SCALE_READY = "SCALE_READY"
    CAUSAL_CHAMPION = "CAUSAL_CHAMPION"


#: Strict promotion order. Index is the rank used for comparison; nothing else
#: in the package may hardcode an ordering.
PROMOTION_ORDER: Tuple[PromotionState, ...] = (
    PromotionState.OFFLINE_CANDIDATE,
    PromotionState.SHADOW_READY,
    PromotionState.PILOT_READY,
    PromotionState.SCALE_READY,
    PromotionState.CAUSAL_CHAMPION,
)

#: The entry state. Reaching it requires no transition: it is what a system is
#: before anything has been demonstrated, not something earned.
INITIAL_STATE = PromotionState.OFFLINE_CANDIDATE


def rank(state: PromotionState) -> int:
    return PROMOTION_ORDER.index(state)


#: Every legal transition, as (from, to). There is exactly one path.
TRANSITIONS: Tuple[Tuple[PromotionState, PromotionState], ...] = tuple(
    (PROMOTION_ORDER[index], PROMOTION_ORDER[index + 1])
    for index in range(len(PROMOTION_ORDER) - 1)
)


def transition_id(source: PromotionState, target: PromotionState) -> str:
    """Stable identifier used to bind gates to a transition."""
    return f"{source.value}__TO__{target.value}"


#: Transition identifiers in promotion order.
TRANSITION_IDS: Tuple[str, ...] = tuple(
    transition_id(source, target) for source, target in TRANSITIONS
)


def next_state(state: PromotionState) -> Optional[PromotionState]:
    """The single state promotion may advance to, or None at the top."""
    position = rank(state)
    if position + 1 >= len(PROMOTION_ORDER):
        return None
    return PROMOTION_ORDER[position + 1]


def is_legal_transition(source: PromotionState, target: PromotionState) -> bool:
    return (source, target) in TRANSITIONS


class PromotionCapability(str, Enum):
    """What the system may actually be used for.

    Separated from state because the two answer different questions. State is
    "how far has this been promoted"; capability is "which specific claim or
    action is licensed". A capability is granted only when both its state
    threshold and its evidence prerequisites hold.
    """

    #: Offline analysis on governed historical data. Always available; this is
    #: what the twin does before any promotion at all.
    OFFLINE_ANALYSIS = "OFFLINE_ANALYSIS"
    #: Demonstrate the system on synthetic or public data to a human audience.
    SYNTHETIC_DEMONSTRATION = "SYNTHETIC_DEMONSTRATION"
    #: Score live bank flow without any of it reaching a banker.
    HIDDEN_SHADOW_SCORING = "HIDDEN_SHADOW_SCORING"
    #: Show output to a named, supervised RM cohort who know it is a pilot.
    SUPERVISED_RM_PILOT = "SUPERVISED_RM_PILOT"
    #: Show output to RMs as part of ordinary work.
    PRODUCTION_RM_DECISION_SUPPORT = "PRODUCTION_RM_DECISION_SUPPORT"
    #: State a competitor's share of a client's wallet as a measured quantity.
    MEASURED_SHARE_REPORTING = "MEASURED_SHARE_REPORTING"
    #: Attach a bank-approved money value to an opportunity.
    COMMERCIAL_VALUE_CLAIM = "COMMERCIAL_VALUE_CLAIM"
    #: Claim the system *caused* incremental revenue.
    CAUSAL_VALUE_CLAIM = "CAUSAL_VALUE_CLAIM"
    #: Take a client-affecting action without a human deciding.
    AUTONOMOUS_CLIENT_ACTION = "AUTONOMOUS_CLIENT_ACTION"
    # V3.2 consequence-level capabilities. These are the banker-facing
    # permissions required by the Promotion Twin plan; the older operational
    # capabilities above remain as compatibility projections.
    DISCOVERY_CONVERSATION = "DISCOVERY_CONVERSATION"
    POSTERIOR_WALLET = "POSTERIOR_WALLET"
    MEASURED_SHARE = "MEASURED_SHARE"
    SCENARIO_ECONOMICS = "SCENARIO_ECONOMICS"
    PRODUCT_PROPOSAL = "PRODUCT_PROPOSAL"
    LIVE_GENAI = "LIVE_GENAI"
    CAUSAL_VALUE = "CAUSAL_VALUE"


#: The lowest state at which a capability *could* be granted. Necessary, never
#: sufficient — see ``EVIDENCE_PREREQUISITES``.
CAPABILITY_STATE_THRESHOLD: Mapping[PromotionCapability, PromotionState] = {
    PromotionCapability.OFFLINE_ANALYSIS: PromotionState.OFFLINE_CANDIDATE,
    PromotionCapability.SYNTHETIC_DEMONSTRATION: PromotionState.OFFLINE_CANDIDATE,
    PromotionCapability.HIDDEN_SHADOW_SCORING: PromotionState.SHADOW_READY,
    PromotionCapability.SUPERVISED_RM_PILOT: PromotionState.PILOT_READY,
    PromotionCapability.PRODUCTION_RM_DECISION_SUPPORT: PromotionState.SCALE_READY,
    PromotionCapability.MEASURED_SHARE_REPORTING: PromotionState.SHADOW_READY,
    PromotionCapability.COMMERCIAL_VALUE_CLAIM: PromotionState.SHADOW_READY,
    PromotionCapability.CAUSAL_VALUE_CLAIM: PromotionState.CAUSAL_CHAMPION,
    PromotionCapability.AUTONOMOUS_CLIENT_ACTION: PromotionState.CAUSAL_CHAMPION,
    PromotionCapability.DISCOVERY_CONVERSATION: PromotionState.PILOT_READY,
    PromotionCapability.POSTERIOR_WALLET: PromotionState.PILOT_READY,
    PromotionCapability.MEASURED_SHARE: PromotionState.SHADOW_READY,
    PromotionCapability.SCENARIO_ECONOMICS: PromotionState.OFFLINE_CANDIDATE,
    PromotionCapability.PRODUCT_PROPOSAL: PromotionState.PILOT_READY,
    PromotionCapability.LIVE_GENAI: PromotionState.SHADOW_READY,
    PromotionCapability.CAUSAL_VALUE: PromotionState.CAUSAL_CHAMPION,
}

#: Gate ids that must additionally hold on the REAL track before a capability is
#: granted. These encode the analytical prerequisites that operational maturity
#: does not imply.
#:
#: The three entries here are the whole reason capability is modelled separately
#: from state: without them, reaching SHADOW_READY would silently license a
#: measured-share claim that no shadow gate examines.
EVIDENCE_PREREQUISITES: Mapping[PromotionCapability, FrozenSet[str]] = {
    PromotionCapability.MEASURED_SHARE_REPORTING: frozenset(
        {"e3-multibank-observation-approved"}
    ),
    PromotionCapability.COMMERCIAL_VALUE_CLAIM: frozenset(
        {"bank-approved-economics-registered"}
    ),
    PromotionCapability.CAUSAL_VALUE_CLAIM: frozenset(
        {"randomised-trial-validated", "trial-first-stage-strength-adequate"}
    ),
    PromotionCapability.MEASURED_SHARE: frozenset(
        {"e3-multibank-observation-approved"}
    ),
    PromotionCapability.PRODUCT_PROPOSAL: frozenset(
        {
            "bank-approved-economics-registered",
            "feasibility-gates-block-selection",
            "selected-critical-path-evidence-complete",
        }
    ),
    PromotionCapability.LIVE_GENAI: frozenset({"genai-bank-approved"}),
    PromotionCapability.CAUSAL_VALUE: frozenset(
        {"randomised-trial-validated", "trial-first-stage-strength-adequate"}
    ),
}

#: Capabilities that are refused at every state, whatever the evidence. Listing
#: them explicitly is a design statement: they are not "not yet reached", they
#: are outside what this system is for. ``AUTONOMOUS_CLIENT_ACTION`` keeps a
#: state threshold above so the refusal is visibly deliberate rather than an
#: omission from the table.
PERMANENTLY_WITHHELD: FrozenSet[PromotionCapability] = frozenset(
    {PromotionCapability.AUTONOMOUS_CLIENT_ACTION}
)

CAPABILITIES: Tuple[PromotionCapability, ...] = tuple(PromotionCapability)


def attained_state(passed_transitions: Iterable[str]) -> PromotionState:
    """The highest state reachable given which transitions fully passed.

    Cumulative and order-respecting: the walk stops at the first transition that
    did not pass, so passing a later transition while an earlier one fails
    grants nothing. This is what makes "states cannot be skipped" a property of
    the computation rather than a rule someone has to remember to check.
    """
    passed = set(passed_transitions)
    state = INITIAL_STATE
    for source, target in TRANSITIONS:
        if transition_id(source, target) not in passed:
            break
        state = target
    return state


def granted_capabilities(
    state: PromotionState,
    passed_real_gate_ids: Iterable[str],
) -> Dict[PromotionCapability, bool]:
    """Which capabilities are licensed, and which are refused.

    Returns every capability, not just the granted ones. A caller that only sees
    what is allowed cannot tell the difference between a capability that was
    refused and one that was never considered.
    """
    passed = set(passed_real_gate_ids)
    verdicts: Dict[PromotionCapability, bool] = {}
    for capability in CAPABILITIES:
        if capability in PERMANENTLY_WITHHELD:
            verdicts[capability] = False
            continue
        threshold = CAPABILITY_STATE_THRESHOLD[capability]
        if rank(state) < rank(threshold):
            verdicts[capability] = False
            continue
        required = EVIDENCE_PREREQUISITES.get(capability, frozenset())
        verdicts[capability] = required.issubset(passed)
    return verdicts


def capability_refusal_reason(
    capability: PromotionCapability,
    state: PromotionState,
    passed_real_gate_ids: Iterable[str],
) -> Optional[str]:
    """Why a capability is withheld, in terms a reviewer can act on.

    ``None`` means it is granted. Anything else names the specific obstacle, so
    the workbench can say *what would make the real gate pass* instead of
    showing an unexplained red cell.
    """
    if capability in PERMANENTLY_WITHHELD:
        return "PERMANENTLY_WITHHELD_BY_DESIGN"
    threshold = CAPABILITY_STATE_THRESHOLD[capability]
    if rank(state) < rank(threshold):
        return f"REQUIRES_STATE_{threshold.value}_CURRENT_{state.value}"
    missing = sorted(
        EVIDENCE_PREREQUISITES.get(capability, frozenset()) - set(passed_real_gate_ids)
    )
    if missing:
        return "REQUIRES_REAL_GATES_" + ",".join(missing)
    return None
