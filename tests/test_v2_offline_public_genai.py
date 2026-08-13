from __future__ import annotations

import json
from datetime import date

from fastapi.testclient import TestClient

from wallet_twin_v2.fixtures import build_fixture
from wallet_twin_v2.genai_eval import evaluate_golden_set
from wallet_twin_v2.genai_gateway import (
    AnthropicMessagesProvider,
    GoogleGeminiProvider,
    OpenAIResponsesProvider,
    ProviderGateway,
)
from wallet_twin_v2.mock_integrations import app as mock_app
from wallet_twin_v2.offline_lab import synthetic_calibration_lab
from wallet_twin_v2.public_evidence import PublicEvidenceRegistry


def test_expanded_public_register_is_point_in_time_and_complete():
    registry = PublicEvidenceRegistry(date(2026, 6, 30))
    assert len(registry.facts) == 82
    assert len(registry.by_entity) == 20
    assert min(len(registry.facts_for(entity_id)) for entity_id in registry.by_entity) >= 3
    assert all(fact.available_date <= registry.as_of for fact in registry.facts)
    assert all(fact.page > 0 and fact.source_url.startswith("https://") for fact in registry.facts)


def test_anchor_activation_requires_approved_public_facts():
    """Only approved evidence may move a published number.

    Asserted as an invariant derived from fact state, never as a hard-coded
    count: when a finance SME approves pending facts, the affected anchors
    activate on the next run and this test must still pass unchanged.
    """
    registry = PublicEvidenceRegistry(date(2026, 6, 30))
    approved_entities = {
        fact.entity_id for fact in registry.facts if fact.approval_status == "APPROVED"
    }
    fixture = build_fixture()
    opportunities = fixture["opportunities"]
    assert len(opportunities) == 100

    anchored = [item for item in opportunities if item.evidence_tier.value == "E1"]
    prior_led = [item for item in opportunities if item.evidence_tier.value == "E0"]
    assert len(anchored) + len(prior_led) == 100

    # Tier follows activation, and activation follows approval.
    assert {item.entity_id for item in anchored} == approved_entities
    assert all(item.anchor_activation.value == "ACTIVATED" for item in anchored)
    assert all(item.calibration_status.value == "PUBLICLY_ANCHORED" for item in anchored)
    assert all(item.calibration_status.value == "PRIOR_LED" for item in prior_led)

    # A withheld cell cites nothing and says why.
    assert all(not item.evidence_fact_ids for item in prior_led)
    assert all(item.evidence_fact_ids for item in anchored)
    assert all(
        item.activation_reason_code == "ANCHOR_WITHHELD_PENDING_SME_APPROVAL"
        for item in prior_led
    )
    assert all(
        "ANCHOR_WITHHELD_PENDING_SME_APPROVAL" in item.eligibility.reason_codes
        for item in prior_led
    )

    # No pending fact may appear in an active anchor path anywhere.
    pending_ids = {
        fact.fact_id for fact in registry.facts if fact.approval_status != "APPROVED"
    }
    cited = {fact_id for item in opportunities for fact_id in item.evidence_fact_ids}
    assert cited.isdisjoint(pending_ids)

    # The client cards must agree with their own cells.
    assert fixture["evidence_coverage"]["e1_clients"] == len(approved_entities)
    assert fixture["release"]["status"] == "CLIENT_DEMO_READY_BANK_PRODUCTION_NOT_PROMOTABLE"
    assert fixture["release"]["client_demo_status"] == "READY"
    assert fixture["release"]["bank_production_status"] == "NOT_PROMOTABLE"


def test_pre_signoff_evidence_snapshot():
    """Records today's approval state. Expected to change when the SME signs off.

    This is a snapshot, not a contract: if it fails because facts were approved,
    update it. The invariant above is what must never break.
    """
    fixture = build_fixture()
    coverage = fixture["evidence_coverage"]
    assert coverage["approved_e1_facts"] == 31
    assert coverage["pending_sme_facts"] == 51
    assert coverage["e1_clients"] == 3
    tiers = [item.evidence_tier.value for item in fixture["opportunities"]]
    assert tiers.count("E1") == 15
    assert tiers.count("E0") == 85


def test_known_truth_lab_reports_narrowing_only_when_coverage_is_preserved():
    report = synthetic_calibration_lab(entity_count=70, seed=17)
    comparison = report["comparisons"]
    assert report["production_claim_allowed"] is False
    assert comparison["e1_anchor_median_wallet_interval_narrowing"] > 0
    assert comparison["e1_anchor_coverage_preserved"] is True


def test_sealed_golden_set_has_zero_injection_successes():
    result = evaluate_golden_set()
    sealed = result["splits"]["sealed_test"]
    assert result["dataset_cases"] == 36
    assert sealed["critical_fact_exact_match"] == 1.0
    assert sealed["prompt_injection_successes"] == 0
    assert result["release_gate"]["production_release_allowed"] is False


def test_external_providers_fail_closed_without_all_three_controls(monkeypatch):
    for key in (
        "OPENAI_API_KEY", "OPENAI_MODEL_SNAPSHOT", "OPENAI_PROVIDER_APPROVED",
        "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL_SNAPSHOT", "ANTHROPIC_PROVIDER_APPROVED",
        "GOOGLE_API_KEY", "GOOGLE_MODEL_SNAPSHOT", "GOOGLE_PROVIDER_APPROVED",
    ):
        monkeypatch.delenv(key, raising=False)
    assert OpenAIResponsesProvider().enabled is False
    assert AnthropicMessagesProvider().enabled is False
    assert GoogleGeminiProvider().enabled is False


def test_provider_status_never_returns_secret_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-that-must-not-appear")
    monkeypatch.setenv("OPENAI_MODEL_SNAPSHOT", "approved-snapshot")
    monkeypatch.setenv("OPENAI_PROVIDER_APPROVED", "true")
    gateway = ProviderGateway()
    serialized = json.dumps(gateway.status())
    assert "test-secret-that-must-not-appear" not in serialized
    assert gateway.status()["providers"]["openai"]["credential_configured"] is True


def test_local_identity_and_crm_double_enforce_authentication():
    client = TestClient(mock_app)
    denied = client.get("/mock/crm/events")
    allowed = client.get("/mock/crm/events", headers={"authorization": "Bearer local-owner-token"})
    assert denied.status_code == 401
    assert allowed.status_code == 200
