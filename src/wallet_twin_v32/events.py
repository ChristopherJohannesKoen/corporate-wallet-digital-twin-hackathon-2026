"""V3.2 governed event registry.

The canonical Promotion Twin lifecycle events and the frozen compatibility
events share one new domain topic,
``wallet-twin.promotion.v1``. Existing topics are untouched: promotion is a
separate concern from business-twin, decision, client-learning and audit, and
routing it onto an existing topic would force every current consumer to filter
events it has no interest in.

**Adding a topic touches four places, not one.** The Postgres outbox carries a
hardcoded ``CHECK (domain_topic IN (...))`` at
``infra/sql/001_operational_schemas.sql``, and inserts fail until it is widened.
The other three are ``infra/msk/topics.yaml``, the :class:`PromotionTopic` enum
here, and :data:`TOPIC_ROUTING`. :func:`declared_topics` exists so a test can
assert the SQL and the code agree rather than leaving that to memory.

Every promotion event carries its ``track``. An audit reader must be able to
tell a rehearsal event from a real one without resolving anything else, because
the stream is where a misattributed event would be least visible.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Tuple

from wallet_twin_v2.contracts import EntitlementContext, StrictModel

from .modes import DecisionTrack, PromotionEvidenceMode

EVENTS_VERSION = "v32-promotion-events-1.1.0"


class PromotionEventType(str, Enum):
    """Canonical V3.2 events followed by frozen pre-release aliases."""

    EVIDENCE_SUBMITTED = "PromotionEvidenceSubmitted"
    EVIDENCE_VERIFIED = "PromotionEvidenceVerified"
    GATE_EVALUATION_COMPLETED = "GateEvaluationCompleted"
    DECISION_ISSUED = "PromotionDecisionIssued"
    APPROVAL_RECORDED = "PromotionApprovalRecorded"
    TRANSITION_RECORDED = "PromotionTransitionRecorded"
    REHEARSAL_STARTED = "RehearsalStarted"
    REHEARSAL_DAY_COMPLETED = "RehearsalDayCompleted"
    REHEARSAL_INCIDENT_INJECTED = "RehearsalIncidentInjected"
    REHEARSAL_CLOCK_RESET = "RehearsalClockReset"
    EVIDENCE_EXPIRED = "PromotionEvidenceExpired"
    ARTIFACT_REVOKED = "PromotionArtifactRevoked"

    # Frozen implementation-preview values. New producers use the lifecycle
    # events above; these aliases keep early consumers backward compatible.
    GATE_EVALUATED = "PromotionGateEvaluated"
    EVIDENCE_REGISTERED = "PromotionEvidenceRegistered"
    EVIDENCE_SIGNED = "PromotionEvidenceSigned"
    EVIDENCE_VERIFICATION_FAILED = "PromotionEvidenceVerificationFailed"
    DECISION_PUBLISHED = "PromotionDecisionPublished"
    APPROVAL_SUBMITTED = "PromotionApprovalSubmitted"
    APPROVAL_REVIEWED = "PromotionApprovalReviewed"
    STATE_ADVANCED = "PromotionStateAdvanced"
    CAPABILITY_GRANTED = "PromotionCapabilityGranted"
    CAPABILITY_REFUSED = "PromotionCapabilityRefused"
    REHEARSAL_SCENARIO_EXECUTED = "RehearsalScenarioExecuted"


class PromotionTopic(str, Enum):
    PROMOTION = "wallet-twin.promotion.v1"


TOPIC_ROUTING: Mapping[PromotionEventType, PromotionTopic] = {
    event_type: PromotionTopic.PROMOTION for event_type in PromotionEventType
}

PROMOTION_EVENT_TYPES: Tuple[PromotionEventType, ...] = tuple(PromotionEventType)

#: Events that may only ever appear on the rehearsal track. Emitting one with
#: ``track=REAL`` would assert that a simulated incident happened at the bank.
REHEARSAL_ONLY_EVENTS: frozenset = frozenset(
    {
        PromotionEventType.REHEARSAL_STARTED,
        PromotionEventType.REHEARSAL_DAY_COMPLETED,
        PromotionEventType.REHEARSAL_CLOCK_RESET,
        PromotionEventType.REHEARSAL_SCENARIO_EXECUTED,
        PromotionEventType.REHEARSAL_INCIDENT_INJECTED,
    }
)


def declared_topics() -> Tuple[str, ...]:
    """Topics this package publishes.

    Used by the schema test to assert the SQL ``CHECK`` constraint and the
    broker topic list both admit what the code emits.
    """
    return tuple(topic.value for topic in PromotionTopic)


class PromotionEventEnvelope(StrictModel):
    """Envelope for canonical and backward-compatible V3.2 events."""

    event_id: str
    event_type: PromotionEventType
    topic: PromotionTopic
    schema_version: str = "3.2.0"
    #: Which track this event belongs to. Never optional: an audit reader must
    #: not have to infer it.
    track: DecisionTrack
    occurred_at: datetime
    as_of: Optional[date] = None
    gate_id: Optional[str] = None
    transition_id: Optional[str] = None
    decision_id: Optional[str] = None
    evidence_id: Optional[str] = None
    envelope_id: Optional[str] = None
    scenario_id: Optional[str] = None
    evidence_mode: Optional[PromotionEvidenceMode] = None
    #: Virtual clock position for rehearsal events, so a replayed rehearsal is
    #: distinguishable from a live one by inspection.
    simulation_clock: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    reason_codes: List[str] = []
    entitlement_context: Optional[EntitlementContext] = None
    payload: Dict[str, Any] = {}

    def model_post_init(self, __context: Any) -> None:
        if self.event_type in REHEARSAL_ONLY_EVENTS and self.track is DecisionTrack.REAL:
            raise ValueError(
                f"{self.event_type.value} cannot be emitted on the REAL track; "
                "a simulated scenario did not happen at the bank"
            )
        if (
            self.evidence_mode is PromotionEvidenceMode.SYNTHETIC_REHEARSAL
            and self.track is DecisionTrack.REAL
        ):
            raise ValueError(
                "a REAL-track event cannot carry SYNTHETIC_REHEARSAL evidence"
            )
        if self.simulation_clock is not None and self.track is DecisionTrack.REAL:
            raise ValueError(
                "simulation_clock is set on a REAL-track event; virtual time has "
                "no meaning outside a rehearsal"
            )


def new_event_id() -> str:
    return str(uuid.uuid4())


def build_promotion_event(
    event_type: PromotionEventType,
    *,
    track: DecisionTrack,
    occurred_at: Optional[datetime] = None,
    as_of: Optional[date] = None,
    gate_id: Optional[str] = None,
    transition_id: Optional[str] = None,
    decision_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
    envelope_id: Optional[str] = None,
    scenario_id: Optional[str] = None,
    evidence_mode: Optional[PromotionEvidenceMode] = None,
    simulation_clock: Optional[datetime] = None,
    idempotency_key: Optional[str] = None,
    reason_codes: Optional[List[str]] = None,
    entitlement_context: Optional[EntitlementContext] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> PromotionEventEnvelope:
    return PromotionEventEnvelope(
        event_id=new_event_id(),
        event_type=event_type,
        topic=TOPIC_ROUTING[event_type],
        track=track,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        as_of=as_of,
        gate_id=gate_id,
        transition_id=transition_id,
        decision_id=decision_id,
        evidence_id=evidence_id,
        envelope_id=envelope_id,
        scenario_id=scenario_id,
        evidence_mode=evidence_mode,
        simulation_clock=simulation_clock,
        idempotency_key=idempotency_key,
        reason_codes=list(reason_codes or []),
        entitlement_context=entitlement_context,
        payload=dict(payload or {}),
    )


class PromotionEventStore:
    """In-memory, idempotency-aware sink; MSK is the production adapter.

    Mirrors ``V31EventStore`` so operational tooling written against one works
    against the other.
    """

    def __init__(self) -> None:
        self._events: List[PromotionEventEnvelope] = []
        self._idempotency: Dict[str, str] = {}

    def append(self, event: PromotionEventEnvelope) -> PromotionEventEnvelope:
        key = event.idempotency_key
        if key is not None and key in self._idempotency:
            existing = self._idempotency[key]
            for candidate in self._events:
                if candidate.event_id == existing:
                    return candidate
        if any(item.event_id == event.event_id for item in self._events):
            raise ValueError(f"duplicate event_id: {event.event_id}")
        self._events.append(event)
        if key is not None:
            self._idempotency[key] = event.event_id
        return event

    def list(
        self,
        *,
        event_type: Optional[PromotionEventType] = None,
        track: Optional[DecisionTrack] = None,
        gate_id: Optional[str] = None,
        transition_id: Optional[str] = None,
    ) -> List[PromotionEventEnvelope]:
        events = list(self._events)
        if event_type is not None:
            events = [item for item in events if item.event_type is event_type]
        if track is not None:
            events = [item for item in events if item.track is track]
        if gate_id is not None:
            events = [item for item in events if item.gate_id == gate_id]
        if transition_id is not None:
            events = [item for item in events if item.transition_id == transition_id]
        return events

    def counts_by_type(self) -> Dict[str, int]:
        counts = {event_type.value: 0 for event_type in PromotionEventType}
        for event in self._events:
            counts[event.event_type.value] += 1
        return counts

    def counts_by_track(self) -> Dict[str, int]:
        """Published beside every other count.

        A promotion stream that is overwhelmingly rehearsal is the honest
        picture of a system that has never run at a bank, and it should be
        visible without anyone having to aggregate the stream themselves.
        """
        counts = {track.value: 0 for track in DecisionTrack}
        for event in self._events:
            counts[event.track.value] += 1
        return counts

    def __len__(self) -> int:
        return len(self._events)


__all__ = [
    "EVENTS_VERSION",
    "PROMOTION_EVENT_TYPES",
    "REHEARSAL_ONLY_EVENTS",
    "TOPIC_ROUTING",
    "PromotionEventEnvelope",
    "PromotionEventStore",
    "PromotionEventType",
    "PromotionTopic",
    "build_promotion_event",
    "declared_topics",
    "new_event_id",
]
