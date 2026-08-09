from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Protocol

from .contracts import (
    ApprovalStatus,
    CuratedMetadata,
    EvidenceFact,
    EvidenceTier,
    ExtractionCandidate,
    FactReviewRequest,
    QualityStatus,
)


@dataclass
class CandidateState:
    candidate: ExtractionCandidate
    submitted_by: str
    reviews: List[FactReviewRequest] = field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING_REVIEW


class EvidenceValidationError(ValueError):
    pass


class ManifestSigner(Protocol):
    def sign(self, payload: bytes) -> dict: ...


class EvidenceRegistry:
    """Candidate-to-approved-fact workflow with deterministic validation."""

    version = "evidence-workflow-2.0.0"
    _currency_pattern = re.compile(r"^[A-Z]{3}$")

    def __init__(self) -> None:
        self._candidates: Dict[str, CandidateState] = {}
        self._facts: Dict[str, EvidenceFact] = {}
        self._lock = threading.RLock()

    @classmethod
    def validate_candidate(cls, candidate: ExtractionCandidate, as_of: Optional[date] = None) -> List[str]:
        errors = []
        if not cls._currency_pattern.match(candidate.currency.upper()):
            errors.append("INVALID_CURRENCY")
        if candidate.sign == 0 and candidate.source_value != 0:
            errors.append("SIGN_VALUE_MISMATCH")
        if candidate.period_end < candidate.period_start:
            errors.append("INVALID_REPORTING_PERIOD")
        if candidate.available_date < candidate.period_end:
            errors.append("AVAILABLE_DATE_PRECEDES_PERIOD_END")
        if as_of is not None and candidate.available_date > as_of:
            errors.append("FUTURE_DATED_EVIDENCE")
        if not candidate.supporting_text.strip():
            errors.append("SUPPORTING_TEXT_MISSING")
        if len(candidate.bounding_box) != 4 or any(value < 0 for value in candidate.bounding_box):
            errors.append("INVALID_BOUNDING_BOX")
        expected_hash = hashlib.sha256(candidate.supporting_text.encode("utf-8")).hexdigest()
        if len(candidate.document_hash) < 16 or candidate.document_hash == expected_hash[:8]:
            errors.append("DOCUMENT_HASH_INVALID")
        return errors

    def submit(self, candidate: ExtractionCandidate, submitted_by: str, as_of: Optional[date] = None) -> CandidateState:
        errors = self.validate_candidate(candidate, as_of)
        if errors:
            raise EvidenceValidationError(";".join(errors))
        with self._lock:
            if candidate.candidate_id in self._candidates or candidate.candidate_id in self._facts:
                raise EvidenceValidationError("DUPLICATE_CANDIDATE_ID")
            state = CandidateState(candidate=candidate, submitted_by=submitted_by)
            self._candidates[candidate.candidate_id] = state
        return state

    def review(self, candidate_id: str, request: FactReviewRequest) -> CandidateState:
        if request.decision not in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
            raise EvidenceValidationError("review decision must be APPROVED or REJECTED")
        with self._lock:
            state = self._candidates[candidate_id]
            if request.reviewer_id == state.submitted_by:
                raise EvidenceValidationError("FOUR_EYES_SUBMITTER_CANNOT_REVIEW")
            if request.reviewer_role not in {"FINANCE_SME", "EVIDENCE_REVIEWER"}:
                raise EvidenceValidationError("REVIEWER_ROLE_NOT_AUTHORIZED")
            if any(review.reviewer_id == request.reviewer_id for review in state.reviews):
                raise EvidenceValidationError("DUPLICATE_REVIEWER")
            state.reviews.append(request)
            if request.decision == ApprovalStatus.REJECTED:
                state.status = ApprovalStatus.REJECTED
                return state
            approvals = [review for review in state.reviews if review.decision == ApprovalStatus.APPROVED]
            roles = {review.reviewer_role for review in approvals}
            role_separation_passed = {"FINANCE_SME", "EVIDENCE_REVIEWER"}.issubset(roles)
            if (state.candidate.material and role_separation_passed) or (not state.candidate.material and approvals):
                state.status = ApprovalStatus.APPROVED
                self._facts[candidate_id] = self._publish(state)
            return state

    def _publish(self, state: CandidateState) -> EvidenceFact:
        candidate = state.candidate
        now = candidate.available_date
        metadata = CuratedMetadata(
            business_key=candidate.candidate_id,
            source_system_key=candidate.document_hash,
            event_time=f"{now.isoformat()}T00:00:00Z",
            valid_from=f"{now.isoformat()}T00:00:00Z",
            source_hash=candidate.document_hash,
            transformation_version=self.version,
            quality_status=QualityStatus.VALID,
            data_owner="Evidence Office",
            entitlement_domain=f"client:{candidate.entity_id}",
        )
        return EvidenceFact(
            fact_id=candidate.candidate_id,
            entity_id=candidate.entity_id,
            concept=candidate.concept,
            source_value=candidate.source_value,
            currency=candidate.currency,
            unit=candidate.unit,
            sign=candidate.sign,
            period_start=candidate.period_start,
            period_end=candidate.period_end,
            source_date=candidate.source_date,
            available_date=candidate.available_date,
            source_title=candidate.source_title,
            source_url=candidate.source_url,
            document_hash=candidate.document_hash,
            page=candidate.page,
            bounding_box=candidate.bounding_box,
            supporting_text=candidate.supporting_text,
            extraction_method=candidate.extraction_method,
            extraction_model_version=candidate.extraction_model_version,
            tier=EvidenceTier.E1,
            approval_status=ApprovalStatus.APPROVED,
            material=candidate.material,
            metadata=metadata,
        )

    def fact(self, fact_id: str) -> EvidenceFact:
        return self._facts[fact_id]

    def approved_facts(self) -> List[EvidenceFact]:
        return list(self._facts.values())

    def approval_manifest(self, signer: Optional[ManifestSigner] = None) -> dict:
        with self._lock:
            facts = []
            for candidate_id in sorted(self._candidates):
                state = self._candidates[candidate_id]
                facts.append({
                    "fact_id": candidate_id,
                    "entity_id": state.candidate.entity_id,
                    "document_hash": state.candidate.document_hash,
                    "candidate_sha256": hashlib.sha256(
                        json.dumps(state.candidate.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest(),
                    "submitted_by": state.submitted_by,
                    "material": state.candidate.material,
                    "status": state.status.value,
                    "reviews": [
                        {
                            "reviewer_id": review.reviewer_id,
                            "reviewer_role": review.reviewer_role,
                            "decision": review.decision.value,
                            "reviewed_at": review.reviewed_at.isoformat(),
                            "notes_sha256": hashlib.sha256(review.notes.encode()).hexdigest(),
                        }
                        for review in state.reviews
                    ],
                })
            body = {
                "manifest_version": "evidence-approval-manifest-1.0.0",
                "workflow_version": self.version,
                "facts": facts,
                "resolved": sum(item["status"] in {"APPROVED", "REJECTED"} for item in facts),
                "pending": sum(item["status"] == "PENDING_REVIEW" for item in facts),
            }
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            result = {
                **body,
                "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
                "signature": None,
                "signature_status": "UNSIGNED",
                "production_approval_claim_allowed": False,
            }
            if signer is not None:
                result["signature"] = signer.sign(canonical)
                result["signature_status"] = "SIGNED"
                result["production_approval_claim_allowed"] = result["pending"] == 0
            return result


def normalize_source_value(value: str, unit: str) -> Decimal:
    cleaned = value.strip().replace(",", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    amount = Decimal(cleaned)
    if negative:
        amount = -amount
    multiplier = {"unit": 1, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}.get(unit.lower())
    if multiplier is None:
        raise EvidenceValidationError("UNSUPPORTED_UNIT")
    return amount * multiplier
