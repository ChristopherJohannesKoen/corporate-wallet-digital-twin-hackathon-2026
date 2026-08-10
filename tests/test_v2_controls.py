from datetime import date
from decimal import Decimal

import pytest

from wallet_twin_v2.contracts import (
    ApprovalStatus,
    DeploymentEnvironment,
    EntitlementContext,
    ExtractionCandidate,
    FactReviewRequest,
)
from wallet_twin_v2.entitlements import EntitlementService
from wallet_twin_v2.evidence import EvidenceRegistry, EvidenceValidationError


def context(role: str, clients=None):
    return EntitlementContext(
        user_id="user-1",
        roles=[role],
        team="team-1",
        regions=["ZA"],
        client_ids=clients or ["E01"],
        products=["Payments"],
        environment=DeploymentEnvironment.SHADOW,
    )


def test_abac_denies_cross_client_and_rm_shadow_access():
    service = EntitlementService()
    denied = service.authorize(
        context=context("RM"),
        action="client-twin:read",
        resource_type="client",
        resource_id="E02",
        client_id="E02",
    )
    assert denied.allowed is False
    assert "SHADOW_ROLE_REQUIRED" in denied.reason_codes
    assert "CLIENT_NOT_ENTITLED" in denied.reason_codes


def candidate(material=True):
    return ExtractionCandidate(
        candidate_id="FACT-X",
        entity_id="E01",
        concept="revenue",
        source_value=Decimal("100"),
        currency="USD",
        unit="million",
        sign=1,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
        source_date=date(2026, 2, 1),
        available_date=date(2026, 2, 1),
        source_title="Audited report",
        source_url="https://example.test/report.pdf",
        document_hash="b" * 64,
        page=10,
        bounding_box=[0.1, 0.2, 0.3, 0.4],
        supporting_text="Revenue 100",
        extraction_method="structured-output",
        extraction_model_version="approved-snapshot",
        material=material,
    )


def test_material_fact_requires_independent_four_eyes_reviews():
    registry = EvidenceRegistry()
    registry.submit(candidate(), submitted_by="submitter", as_of=date(2026, 6, 30))
    first = registry.review(
        "FACT-X",
        FactReviewRequest(
            reviewer_id="reviewer-1",
            reviewer_role="FINANCE_SME",
            decision=ApprovalStatus.APPROVED,
            notes="ties to source",
        ),
    )
    assert first.status == ApprovalStatus.PENDING_REVIEW
    second = registry.review(
        "FACT-X",
        FactReviewRequest(
            reviewer_id="reviewer-2",
            reviewer_role="EVIDENCE_REVIEWER",
            decision=ApprovalStatus.APPROVED,
            notes="independently verified",
        ),
    )
    assert second.status == ApprovalStatus.APPROVED
    assert registry.fact("FACT-X").approval_status == ApprovalStatus.APPROVED


def test_submitter_cannot_review_own_fact():
    registry = EvidenceRegistry()
    registry.submit(candidate(material=False), submitted_by="submitter")
    with pytest.raises(EvidenceValidationError):
        registry.review(
            "FACT-X",
            FactReviewRequest(
                reviewer_id="submitter",
                reviewer_role="FINANCE_SME",
                decision=ApprovalStatus.APPROVED,
                notes="invalid self review",
            ),
        )


def test_material_fact_requires_role_separation_and_manifest_signature():
    class Signer:
        def sign(self, payload: bytes) -> dict:
            return {"algorithm": "TEST", "message_bytes": len(payload)}

    registry = EvidenceRegistry()
    registry.submit(candidate(), submitted_by="submitter")
    registry.review(
        "FACT-X",
        FactReviewRequest(
            reviewer_id="finance-1",
            reviewer_role="FINANCE_SME",
            decision=ApprovalStatus.APPROVED,
            notes="first review",
        ),
    )
    duplicate_role = registry.review(
        "FACT-X",
        FactReviewRequest(
            reviewer_id="finance-2",
            reviewer_role="FINANCE_SME",
            decision=ApprovalStatus.APPROVED,
            notes="second finance review",
        ),
    )
    assert duplicate_role.status == ApprovalStatus.PENDING_REVIEW
    registry.review(
        "FACT-X",
        FactReviewRequest(
            reviewer_id="governance-1",
            reviewer_role="EVIDENCE_REVIEWER",
            decision=ApprovalStatus.APPROVED,
            notes="independent approval",
        ),
    )
    manifest = registry.approval_manifest(Signer())
    assert manifest["pending"] == 0
    assert manifest["signature_status"] == "SIGNED"
    assert manifest["production_approval_claim_allowed"] is True
    assert len(manifest["canonical_sha256"]) == 64
