from __future__ import annotations

import hashlib
import threading
import uuid
from datetime import date
from typing import Iterable, List, Optional

from .contracts import ArtifactReference, EntitlementContext, EventEnvelope, EventType


class EventStore:
    """Thread-safe local event sink; MSK is the production adapter."""

    def __init__(self) -> None:
        self._events: List[EventEnvelope] = []
        self._lock = threading.RLock()

    def append(self, event: EventEnvelope) -> EventEnvelope:
        if event.event_type == EventType.RECOMMENDATION_ASSIGNED and event.assignment_probability is None:
            raise ValueError("assignment probability is required for recommendation assignment")
        with self._lock:
            if any(existing.event_id == event.event_id for existing in self._events):
                raise ValueError(f"duplicate event_id: {event.event_id}")
            self._events.append(event)
        return event

    def list(self, *, recommendation_id: Optional[str] = None) -> List[EventEnvelope]:
        with self._lock:
            events = list(self._events)
        if recommendation_id is not None:
            events = [event for event in events if event.recommendation_id == recommendation_id]
        return events


class ClusterRandomizedEncouragement:
    version = "cluster-encouragement-1.0.0"

    def __init__(self, treatment_probability: float = 0.5, salt: str = "wallet-shadow-v2") -> None:
        if not 0 < treatment_probability < 1:
            raise ValueError("treatment_probability must be in (0, 1)")
        self.treatment_probability = treatment_probability
        self.salt = salt

    def assign(
        self,
        *,
        cluster_id: str,
        recommendation_id: str,
        entity_id: str,
        product: str,
        as_of: date,
        artifacts: ArtifactReference,
        entitlement_context: EntitlementContext,
    ) -> EventEnvelope:
        digest = hashlib.sha256(f"{self.salt}|{cluster_id}".encode("utf-8")).digest()
        value = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
        arm = "ENCOURAGEMENT" if value < self.treatment_probability else "CONTROL"
        probability = self.treatment_probability if arm == "ENCOURAGEMENT" else 1.0 - self.treatment_probability
        return EventEnvelope(
            event_id=str(uuid.uuid4()),
            event_type=EventType.RECOMMENDATION_ASSIGNED,
            entity_id=entity_id,
            product=product,
            recommendation_id=recommendation_id,
            team_id=cluster_id,
            as_of=as_of,
            assignment_arm=arm,
            assignment_probability=probability,
            artifacts=artifacts,
            entitlement_context=entitlement_context,
            payload={"cluster_randomized": True, "assignment_policy_version": self.version},
        )


def new_event_id() -> str:
    return str(uuid.uuid4())
