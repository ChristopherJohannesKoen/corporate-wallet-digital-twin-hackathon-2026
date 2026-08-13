"""V3.1 governed event registry.

Twelve new event types are added on four domain topics rather than one topic
per event.  Existing V2/V3 events keep their envelope and gain optional
``conversation_id``, ``problem_id`` and ``solution_bundle_id`` payload fields,
so existing consumers continue to deserialize unchanged.
"""

from __future__ import annotations

import uuid
from datetime import date
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple

from wallet_twin_v2.contracts import (
    ArtifactReference,
    EntitlementContext,
    EventEnvelope,
    EventType,
    StrictModel,
)


class V31EventType(str, Enum):
    BUSINESS_TWIN_SNAPSHOT_PUBLISHED = "BusinessTwinSnapshotPublished"
    BUSINESS_GRAPH_SNAPSHOT_PUBLISHED = "BusinessGraphSnapshotPublished"
    BUSINESS_EVENT_PUBLISHED = "BusinessEventPublished"
    PROBLEM_HYPOTHESIS_PUBLISHED = "ProblemHypothesisPublished"
    STAKEHOLDER_ATTESTATION_RECORDED = "StakeholderAttestationRecorded"
    FEASIBILITY_ASSESSMENT_RECORDED = "FeasibilityAssessmentRecorded"
    CONVERSATION_ELIGIBILITY_RECORDED = "ConversationEligibilityRecorded"
    COVERAGE_PLAN_SELECTED = "CoveragePlanSelected"
    INFORMATION_QUESTION_PROPOSED = "InformationQuestionProposed"
    CLIENT_ANSWER_SUBMITTED = "ClientAnswerSubmitted"
    CLIENT_ANSWER_APPROVED = "ClientAnswerApproved"
    CONVERSATION_BRIEF_COMPILED = "ConversationBriefCompiled"


class DomainTopic(str, Enum):
    BUSINESS_TWIN = "wallet-twin.business-twin.v1"
    DECISION = "wallet-twin.decision.v1"
    CLIENT_LEARNING = "wallet-twin.client-learning.v1"
    AUDIT = "wallet-twin.audit.v1"


TOPIC_ROUTING: Mapping[V31EventType, DomainTopic] = {
    V31EventType.BUSINESS_TWIN_SNAPSHOT_PUBLISHED: DomainTopic.BUSINESS_TWIN,
    V31EventType.BUSINESS_GRAPH_SNAPSHOT_PUBLISHED: DomainTopic.BUSINESS_TWIN,
    V31EventType.BUSINESS_EVENT_PUBLISHED: DomainTopic.BUSINESS_TWIN,
    V31EventType.PROBLEM_HYPOTHESIS_PUBLISHED: DomainTopic.BUSINESS_TWIN,
    V31EventType.STAKEHOLDER_ATTESTATION_RECORDED: DomainTopic.AUDIT,
    V31EventType.FEASIBILITY_ASSESSMENT_RECORDED: DomainTopic.AUDIT,
    V31EventType.CONVERSATION_ELIGIBILITY_RECORDED: DomainTopic.DECISION,
    V31EventType.COVERAGE_PLAN_SELECTED: DomainTopic.DECISION,
    V31EventType.INFORMATION_QUESTION_PROPOSED: DomainTopic.CLIENT_LEARNING,
    V31EventType.CLIENT_ANSWER_SUBMITTED: DomainTopic.CLIENT_LEARNING,
    V31EventType.CLIENT_ANSWER_APPROVED: DomainTopic.CLIENT_LEARNING,
    V31EventType.CONVERSATION_BRIEF_COMPILED: DomainTopic.DECISION,
}

LEGACY_TOPIC_ROUTING: Mapping[EventType, DomainTopic] = {
    EventType.ELIGIBILITY_RECORDED: DomainTopic.DECISION,
    EventType.RECOMMENDATION_ASSIGNED: DomainTopic.DECISION,
    EventType.RECOMMENDATION_DISPLAYED: DomainTopic.DECISION,
    EventType.RECOMMENDATION_OPENED: DomainTopic.DECISION,
    EventType.RECOMMENDATION_DISMISSED: DomainTopic.DECISION,
    EventType.BANKER_ACTION_RECORDED: DomainTopic.DECISION,
    EventType.PIPELINE_MILESTONE_RECORDED: DomainTopic.DECISION,
    EventType.OUTCOME_RECORDED: DomainTopic.DECISION,
    EventType.EVIDENCE_APPROVED: DomainTopic.CLIENT_LEARNING,
    EventType.ACCESS_DECISION_LOGGED: DomainTopic.AUDIT,
    EventType.SHADOW_WALLET_RECONSTRUCTED: DomainTopic.BUSINESS_TWIN,
    EventType.LEAKAGE_SIGNAL_PUBLISHED: DomainTopic.BUSINESS_TWIN,
    EventType.ACTION_PORTFOLIO_SELECTED: DomainTopic.DECISION,
    EventType.EVIDENCE_ACQUISITION_APPROVED: DomainTopic.CLIENT_LEARNING,
    EventType.DECISION_BRIEF_COMPILED: DomainTopic.DECISION,
}

#: Optional decision-object correlation fields added to *existing* events.
#: They are optional so V2/V3 consumers remain schema compatible.
DECISION_CORRELATION_FIELDS: Tuple[str, ...] = (
    "conversation_id",
    "problem_id",
    "solution_bundle_id",
)


class V31EventEnvelope(StrictModel):
    """Envelope for the twelve new V3.1 event types."""

    event_id: str
    event_type: V31EventType
    topic: DomainTopic
    schema_version: str = "3.1.1"
    occurred_at: Optional[str] = None
    entity_id: Optional[str] = None
    as_of: Optional[date] = None
    conversation_id: Optional[str] = None
    problem_id: Optional[str] = None
    solution_bundle_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    reason_codes: list[str] = []
    artifacts: Optional[ArtifactReference] = None
    entitlement_context: Optional[EntitlementContext] = None
    payload: Dict[str, Any] = {}


def new_event_id() -> str:
    return str(uuid.uuid4())


def build_v31_event(
    event_type: V31EventType,
    *,
    entity_id: Optional[str] = None,
    as_of: Optional[date] = None,
    conversation_id: Optional[str] = None,
    problem_id: Optional[str] = None,
    solution_bundle_id: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    reason_codes: Optional[list[str]] = None,
    artifacts: Optional[ArtifactReference] = None,
    entitlement_context: Optional[EntitlementContext] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> V31EventEnvelope:
    return V31EventEnvelope(
        event_id=new_event_id(),
        event_type=event_type,
        topic=TOPIC_ROUTING[event_type],
        entity_id=entity_id,
        as_of=as_of,
        conversation_id=conversation_id,
        problem_id=problem_id,
        solution_bundle_id=solution_bundle_id,
        snapshot_id=snapshot_id,
        idempotency_key=idempotency_key,
        reason_codes=list(reason_codes or []),
        artifacts=artifacts,
        entitlement_context=entitlement_context,
        payload=dict(payload or {}),
    )


def correlate_legacy_event(
    event: EventEnvelope,
    *,
    conversation_id: Optional[str] = None,
    problem_id: Optional[str] = None,
    solution_bundle_id: Optional[str] = None,
) -> EventEnvelope:
    """Attach V3.1 decision-object correlation to an existing V2/V3 event.

    The fields land in ``payload`` so the frozen ``EventEnvelope`` schema is
    unchanged and existing consumers keep deserializing.
    """
    payload = dict(event.payload)
    for key, value in (
        ("conversation_id", conversation_id),
        ("problem_id", problem_id),
        ("solution_bundle_id", solution_bundle_id),
    ):
        if value is not None:
            payload[key] = value
    return event.model_copy(update={"payload": payload})


def topic_for(event_type: V31EventType | EventType) -> DomainTopic:
    if isinstance(event_type, V31EventType):
        return TOPIC_ROUTING[event_type]
    return LEGACY_TOPIC_ROUTING[event_type]


class V31EventStore:
    """In-memory, idempotency-aware sink; MSK is the production adapter."""

    def __init__(self) -> None:
        self._events: list[V31EventEnvelope] = []
        self._idempotency: dict[str, str] = {}

    def append(self, event: V31EventEnvelope) -> V31EventEnvelope:
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
        topic: Optional[DomainTopic] = None,
        event_type: Optional[V31EventType] = None,
        entity_id: Optional[str] = None,
    ) -> list[V31EventEnvelope]:
        events = list(self._events)
        if topic is not None:
            events = [item for item in events if item.topic is topic]
        if event_type is not None:
            events = [item for item in events if item.event_type is event_type]
        if entity_id is not None:
            events = [item for item in events if item.entity_id == entity_id]
        return events

    def counts_by_topic(self) -> Dict[str, int]:
        counts: Dict[str, int] = {topic.value: 0 for topic in DomainTopic}
        for event in self._events:
            counts[event.topic.value] += 1
        return counts

    def __len__(self) -> int:
        return len(self._events)
