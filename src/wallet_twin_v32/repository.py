"""Fixture repository for the promotion service.

The fixture is a *rehearsal*, and it is built to look like one. Every gate
passes on the rehearsal track and none on the real track, which is the honest
V3.2 position: the promotion machinery works end to end, and the bank has
authorised nothing.

``fixture_mode`` is enforced rather than documented. A real-track write here
would mean a demonstration fixture had produced bank authorisation, which is
the single worst failure mode this service has, so it raises.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence

from wallet_twin_v2.canonical import ARTIFACT_AS_OF, artifact_timestamp

from .catalogue import GATE_CATALOGUE
from .contracts import (
    GateEvaluation,
    GateEvidence,
    GateOutcome,
    PromotionApproval,
    PromotionDecision,
    SignedEvidenceEnvelope,
    VirtualClockState,
)
from .dsse import sign_payload
from .engine import capability_register, evaluate_promotion, transition_report
from .events import (
    PromotionEventStore,
    PromotionEventType,
    build_promotion_event,
)
from .modes import DecisionTrack, PromotionEvidenceMode
from .scoring import gates_without_failure_injection, score_breakdown
from .signers import LocalECDSASigner, signer_capability_report
from .states import TRANSITION_IDS
from .trust import TrustRegistry, rehearsal_key

REPOSITORY_VERSION = "v32-promotion-repository-1.0.0"

#: Fixed so the fixture is reproducible, and taken from the canonicaliser rather
#: than written out again here. An independent literal drifted once already:
#: this was 06:00 while every other committed artifact carried the canonical
#: midnight stamp, which the artifact-stability test correctly rejected.
FIXTURE_AS_OF = ARTIFACT_AS_OF
FIXTURE_GENERATED_AT = datetime.fromisoformat(artifact_timestamp())


class FixtureModeError(RuntimeError):
    """A real-track write was attempted against the fixture repository."""


class PromotionRepository:
    """In-memory promotion state. PostgreSQL is the production adapter."""

    version = REPOSITORY_VERSION

    def __init__(self, *, fixture_mode: bool = True) -> None:
        self.fixture_mode = fixture_mode
        self._lock = threading.RLock()
        self.events = PromotionEventStore()
        self._evidence: Dict[str, GateEvidence] = {}
        self._envelopes: Dict[str, SignedEvidenceEnvelope] = {}
        self._evaluations: List[GateEvaluation] = []
        self._approvals: Dict[str, PromotionApproval] = {}
        self._signer = LocalECDSASigner.deterministic("local-rehearsal-p256", 20260630)
        self.trust = TrustRegistry(
            [
                rehearsal_key(
                    "local-rehearsal-p256",
                    not_before=FIXTURE_GENERATED_AT - timedelta(days=1),
                    not_after=FIXTURE_GENERATED_AT + timedelta(days=365),
                    public_key_pem=self._signer.public_key_pem(),
                )
            ]
        )
        self._seed()

    # -- writes ------------------------------------------------------------

    def _guard_real_track(self, track: DecisionTrack) -> None:
        if self.fixture_mode and track is DecisionTrack.REAL:
            raise FixtureModeError(
                "the fixture repository refuses real-track writes; a "
                "demonstration fixture must never be able to produce bank "
                "authorisation"
            )

    def register_evidence(self, evidence: GateEvidence) -> GateEvidence:
        with self._lock:
            if evidence.mode is not PromotionEvidenceMode.SYNTHETIC_REHEARSAL:
                self._guard_real_track(DecisionTrack.REAL)
            self._evidence[evidence.evidence_id] = evidence
            self.events.append(
                build_promotion_event(
                    PromotionEventType.EVIDENCE_REGISTERED,
                    track=DecisionTrack.REHEARSAL,
                    occurred_at=FIXTURE_GENERATED_AT,
                    as_of=evidence.as_of,
                    gate_id=evidence.gate_id,
                    evidence_id=evidence.evidence_id,
                    evidence_mode=evidence.mode,
                    simulation_clock=evidence.simulation_clock,
                    idempotency_key=f"evidence:{evidence.evidence_id}",
                )
            )
            return evidence

    def sign_evidence(self, evidence_id: str) -> SignedEvidenceEnvelope:
        """Sign registered evidence with the local rehearsal key."""
        with self._lock:
            evidence = self._evidence[evidence_id]
            payload = {
                "evidence_id": evidence.evidence_id,
                "gate_id": evidence.gate_id,
                # Mode is inside the signed payload, so tampering with it
                # invalidates the signature rather than merely disagreeing with
                # a sibling field.
                "mode": evidence.mode.value,
                "content_sha256": evidence.content_sha256,
                "as_of": evidence.as_of.isoformat(),
            }
            envelope = sign_payload(payload, self._signer)
            signed = SignedEvidenceEnvelope(
                envelope_id=f"env-{evidence_id}",
                evidence_id=evidence_id,
                payload_sha256=envelope.payload_sha256,
                mode=evidence.mode,
                key_id=self._signer.key_id,
                key_authorised_modes=[PromotionEvidenceMode.SYNTHETIC_REHEARSAL],
                signature_algorithm=self._signer.algorithm,
                signature=envelope.signatures[0].sig,
                signature_status="SIGNED_REHEARSAL",
                trust_domain="rehearsal",
                signed_at=FIXTURE_GENERATED_AT,
            )
            self._envelopes[signed.envelope_id] = signed
            self.events.append(
                build_promotion_event(
                    PromotionEventType.EVIDENCE_SIGNED,
                    track=DecisionTrack.REHEARSAL,
                    occurred_at=FIXTURE_GENERATED_AT,
                    gate_id=evidence.gate_id,
                    evidence_id=evidence_id,
                    envelope_id=signed.envelope_id,
                    evidence_mode=evidence.mode,
                    idempotency_key=f"signed:{signed.envelope_id}",
                )
            )
            return signed

    def record_evaluation(self, evaluation: GateEvaluation) -> GateEvaluation:
        with self._lock:
            self._guard_real_track(evaluation.track)
            self._evaluations.append(evaluation)
            self.events.append(
                build_promotion_event(
                    PromotionEventType.GATE_EVALUATED,
                    track=evaluation.track,
                    occurred_at=evaluation.evaluated_at,
                    gate_id=evaluation.gate_id,
                    transition_id=evaluation.transition_id,
                    evidence_mode=evaluation.evidence_mode,
                    reason_codes=evaluation.reason_codes,
                    idempotency_key=(
                        f"eval:{evaluation.gate_id}:{evaluation.track.value}:"
                        f"{evaluation.evaluated_at.isoformat()}"
                    ),
                    payload={"outcome": evaluation.outcome.value},
                )
            )
            return evaluation

    def record_approval(self, approval: PromotionApproval) -> PromotionApproval:
        with self._lock:
            self._guard_real_track(approval.track)
            self._approvals[approval.approval_id] = approval
            for event_type, moment in (
                (PromotionEventType.APPROVAL_SUBMITTED, approval.submitted_at),
                (PromotionEventType.APPROVAL_REVIEWED, approval.reviewed_at),
            ):
                self.events.append(
                    build_promotion_event(
                        event_type,
                        track=approval.track,
                        occurred_at=moment,
                        transition_id=approval.transition_id,
                        idempotency_key=f"{event_type.value}:{approval.approval_id}",
                        payload={"decision": approval.decision},
                    )
                )
            return approval

    # -- reads -------------------------------------------------------------

    @property
    def evaluations(self) -> Sequence[GateEvaluation]:
        return tuple(self._evaluations)

    def evidence(self, evidence_id: Optional[str] = None):
        if evidence_id is None:
            return [self._evidence[key] for key in sorted(self._evidence)]
        return self._evidence.get(evidence_id)

    def envelopes(self) -> List[SignedEvidenceEnvelope]:
        return [self._envelopes[key] for key in sorted(self._envelopes)]

    def approvals(self) -> List[PromotionApproval]:
        return [self._approvals[key] for key in sorted(self._approvals)]

    def decision(self, as_of: Optional[date] = None) -> PromotionDecision:
        return evaluate_promotion(
            self._evaluations,
            decision_id="v32-fixture-promotion-decision",
            as_of=as_of or FIXTURE_AS_OF,
            generated_at=FIXTURE_GENERATED_AT,
        )

    def clock(self) -> VirtualClockState:
        """The rehearsal clock, driven by an actual run rather than asserted.

        Forty-seven simulated days yield thirty consecutive clean ones because
        a critical reconciliation failure on day 17 resets the counter. Those
        numbers come from executing the rehearsal, not from a literal — a
        hardcoded clock state would report the same figures whether or not the
        rehearsal worked.
        """
        from .rehearsal import canonical_rehearsal

        clock, _ = canonical_rehearsal(as_of=FIXTURE_AS_OF)
        return clock.state()

    def readiness(self) -> Dict[str, object]:
        """Everything the workbench needs, in one shape."""
        decision = self.decision()
        clock = self.clock()
        return {
            "repository_version": self.version,
            "fixture_mode": self.fixture_mode,
            "as_of": decision.as_of.isoformat(),
            "generated_at": decision.generated_at.isoformat(),
            "decision": decision.model_dump(mode="json"),
            "transitions": transition_report(self._evaluations),
            "gate_breakdown": score_breakdown(self._evaluations),
            "capabilities": capability_register(decision),
            "clock": clock.model_dump(mode="json"),
            "signing": signer_capability_report(),
            "trust_registry": self.trust.as_document(),
            "event_counts": {
                "by_type": self.events.counts_by_type(),
                "by_track": self.events.counts_by_track(),
                "total": len(self.events),
            },
            "gates_without_failure_injection": gates_without_failure_injection(
                self._evaluations
            ),
            "honest_status": self.honest_status(),
        }

    def honest_status(self) -> Dict[str, object]:
        """The status block, computed rather than written down.

        Every field here is derived from the evaluations. A hardcoded status
        was exactly the defect found in ``wallet_portfolio.py`` during V3.1.1,
        where a release verdict was a string literal that could not be wrong
        and therefore could not be right either.
        """
        decision = self.decision()
        clock = self.clock()
        return {
            "real_state": decision.real_state.value,
            "rehearsed_state": decision.rehearsed_state.value,
            "bank_shadow_authorized": decision.bank_shadow_authorized,
            "pilot_ready": decision.real_state.value
            in {"PILOT_READY", "SCALE_READY", "CAUSAL_CHAMPION"},
            "scale_ready": decision.real_state.value
            in {"SCALE_READY", "CAUSAL_CHAMPION"},
            "causal_champion": decision.real_state.value == "CAUSAL_CHAMPION",
            "promotion_machinery_readiness": decision.score.promotion_machinery_readiness,
            "bank_evidence_readiness": decision.score.bank_evidence_readiness,
            "shadow_rehearsal_days": clock.consecutive_clean_rehearsal_days,
            "elapsed_bank_shadow_days": clock.elapsed_bank_shadow_days,
            "bank_production_status": "NOT_PROMOTABLE",
        }

    # -- fixture seeding ---------------------------------------------------

    def _seed(self) -> None:
        """Pass every gate on the rehearsal track, and none on the real track.

        Failure injection is recorded for the gates W6's negative scenarios
        exercise. The rest are reported as not-yet-injected rather than assumed
        working, so ``gates_without_failure_injection`` stays a real measure of
        coverage instead of an empty list.
        """
        injected = {
            "reconciliation-exact",
            "point-in-time-zero-leakage",
            "prompt-injection-resistance",
            "entitlement-negative-tests",
            "elapsed-clean-shadow-days",
            "supply-chain-clean",
            "interval-coverage-90",
        }
        for gate in GATE_CATALOGUE:
            evidence = GateEvidence(
                evidence_id=f"ev-{gate.gate_id}",
                gate_id=gate.gate_id,
                mode=PromotionEvidenceMode.SYNTHETIC_REHEARSAL,
                artifact_uri=f"outputs/v32/rehearsal/{gate.gate_id}.json",
                content_sha256=_stable_digest(gate.gate_id),
                summary=f"Rehearsal evidence for {gate.title}",
                as_of=FIXTURE_AS_OF,
                generated_at=FIXTURE_GENERATED_AT,
                simulation_clock=FIXTURE_GENERATED_AT,
                produced_by="v32-rehearsal-laboratory",
            )
            self.register_evidence(evidence)
            envelope = self.sign_evidence(evidence.evidence_id)
            self.record_evaluation(
                GateEvaluation(
                    gate_id=gate.gate_id,
                    transition_id=gate.transition_id,
                    track=DecisionTrack.REHEARSAL,
                    outcome=GateOutcome.PASS,
                    evidence_mode=PromotionEvidenceMode.SYNTHETIC_REHEARSAL,
                    evidence_ids=[evidence.evidence_id],
                    envelope_ids=[envelope.envelope_id],
                    reason_codes=[f"REHEARSED_{gate.severity.value}"],
                    failure_injection_verified=gate.gate_id in injected,
                    evaluated_at=FIXTURE_GENERATED_AT,
                )
            )

        for transition in TRANSITION_IDS:
            self.record_approval(
                PromotionApproval(
                    approval_id=f"ap-{transition}",
                    transition_id=transition,
                    track=DecisionTrack.REHEARSAL,
                    submitted_by="rehearsal.maker@wallet-twin",
                    submitted_role="ENGINEERING",
                    reviewed_by="rehearsal.checker@wallet-twin",
                    reviewed_role="MODEL_RISK",
                    decision="APPROVED",
                    rationale=(
                        "All blocking gates satisfied on the rehearsal track. "
                        "This approves the rehearsal only and confers no bank "
                        "authorisation."
                    ),
                    submitted_at=FIXTURE_GENERATED_AT,
                    reviewed_at=FIXTURE_GENERATED_AT + timedelta(hours=1),
                )
            )

        decision = self.decision()
        self.events.append(
            build_promotion_event(
                PromotionEventType.DECISION_PUBLISHED,
                track=DecisionTrack.REHEARSAL,
                occurred_at=FIXTURE_GENERATED_AT,
                as_of=decision.as_of,
                decision_id=decision.decision_id,
                reason_codes=decision.reason_codes,
                idempotency_key=f"decision:{decision.decision_id}",
                payload={
                    "real_state": decision.real_state.value,
                    "rehearsed_state": decision.rehearsed_state.value,
                },
            )
        )
        for transition in decision.passed_rehearsal_transitions:
            self.events.append(
                build_promotion_event(
                    PromotionEventType.STATE_ADVANCED,
                    track=DecisionTrack.REHEARSAL,
                    occurred_at=FIXTURE_GENERATED_AT,
                    transition_id=transition,
                    idempotency_key=f"advanced:{transition}",
                )
            )
        for capability in decision.granted_capabilities:
            self.events.append(
                build_promotion_event(
                    PromotionEventType.CAPABILITY_GRANTED,
                    track=DecisionTrack.REAL,
                    occurred_at=FIXTURE_GENERATED_AT,
                    idempotency_key=f"granted:{capability.value}",
                    payload={"capability": capability.value},
                )
            )
        for capability, reason in sorted(decision.refused_capabilities.items()):
            self.events.append(
                build_promotion_event(
                    PromotionEventType.CAPABILITY_REFUSED,
                    track=DecisionTrack.REAL,
                    occurred_at=FIXTURE_GENERATED_AT,
                    reason_codes=[reason],
                    idempotency_key=f"refused:{capability}",
                    payload={"capability": capability},
                )
            )


def _stable_digest(seed: str) -> str:
    import hashlib

    return hashlib.sha256(f"v32-rehearsal:{seed}".encode()).hexdigest()


#: Module-level singleton, matching the V3.1 repository pattern.
repository = PromotionRepository()

__all__ = [
    "FIXTURE_AS_OF",
    "FIXTURE_GENERATED_AT",
    "REPOSITORY_VERSION",
    "FixtureModeError",
    "PromotionRepository",
    "repository",
]
