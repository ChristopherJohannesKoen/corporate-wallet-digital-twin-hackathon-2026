from __future__ import annotations

from datetime import date

from wallet_twin_v2.contracts import DeploymentEnvironment
from wallet_twin_v2.demo_data import (
    CLIENT_DEMO_WATERMARK,
    build_client_demo_data,
    generate_representative_multibank_analog,
    validate_external_registry,
)
from wallet_twin_v2.economics import EconomicsService
from wallet_twin_v2.fixtures import synthetic_rate_card
from wallet_twin_v2.genai_eval import generated_stress_suite
from wallet_twin_v2.live_provider_eval import run_live_provider_evaluation
from wallet_twin_v2.production_target import validate_production_target


def test_external_registry_is_pinned_and_preserves_e3_boundary() -> None:
    result = validate_external_registry()
    assert result["passed"] is True
    assert result["datasets"] == 5
    assert result["production_e3_claim_allowed"] is False


def test_representative_panel_is_stratified_known_truth_not_e3() -> None:
    panel = generate_representative_multibank_analog(relationship_count=40, seed=7)
    assert len(panel) == 40 * 5
    assert set(panel["product"]) == {
        "Collections",
        "Payments",
        "Liquidity",
        "Cross-border FX",
        "Trade finance",
    }
    assert panel["selection_weight"].gt(0).all()
    assert panel["known_truth_share"].between(0, 1, inclusive="neither").all()
    assert panel["evidence_tier"].isna().all()
    assert not panel["production_e3_eligible"].any()
    assert not panel["measured_share_label_allowed"].any()


def test_client_demo_data_estate_is_reproducible_and_claim_safe(tmp_path) -> None:
    first = build_client_demo_data(tmp_path / "first", relationship_count=30, seed=13)
    second = build_client_demo_data(tmp_path / "second", relationship_count=30, seed=13)
    assert first["status"] == "CLIENT_DEMO_DATA_READY"
    assert first["watermark"] == CLIENT_DEMO_WATERMARK
    assert first["artifacts"]["panel"]["sha256"] == second["artifacts"]["panel"]["sha256"]
    assert first["artifacts"]["outcomes"]["sha256"] == second["artifacts"]["outcomes"]["sha256"]
    assert first["claim_boundary"] == {
        "client_demo_ready": True,
        "bank_production_ready": False,
        "measured_share_label_allowed": False,
        "causal_uplift_label_allowed": False,
        "financial_decision_use_allowed": False,
    }


def test_client_demo_allows_watermarked_scenario_but_production_blocks_it() -> None:
    as_of = date(2026, 6, 30)
    card = synthetic_rate_card("Trade finance", 12.0, as_of)
    service = EconomicsService()
    demo = service.evaluate(
        as_of=as_of,
        environment=DeploymentEnvironment.CLIENT_DEMO,
        rate_card=card,
        observed_activity=100.0,
        wallet_median=400.0,
        current_share=0.25,
        target_share=0.40,
    )
    production = service.evaluate(
        as_of=as_of,
        environment=DeploymentEnvironment.PRODUCTION,
        rate_card=card,
        observed_activity=100.0,
        wallet_median=400.0,
        current_share=0.25,
        target_share=0.40,
    )
    assert demo.status.value == "SIMULATED"
    assert "CLIENT-DEMO SCENARIO ECONOMICS" in (demo.watermark or "")
    assert production.status.value == "BLOCKED"
    assert "SYNTHETIC_RATE_BLOCKED_IN_CONTROLLED_ENVIRONMENT" in production.reason_codes


def test_production_target_definitions_are_complete_but_environment_is_not_fabricated() -> None:
    report = validate_production_target()
    assert report["implementation_definitions_ready"] is True
    assert report["controls_passed"] == report["controls_total"]
    assert report["environment_state"]["aws_account_provisioned"] is False
    assert report["environment_state"]["databricks_workspace_provisioned"] is False
    assert report["apply_allowed"] is False
    assert report["bank_production_release_allowed"] is False


def test_generated_genai_stress_suite_supports_zero_failure_bound() -> None:
    result = generated_stress_suite()
    assert result["cases"] == 640
    assert result["failures"] == 0
    assert result["below_half_percent_bound"] is True
    assert result["scope"].startswith("deterministic")


def test_live_provider_eval_is_disabled_without_explicit_public_only_ack(monkeypatch) -> None:
    monkeypatch.delenv("LIVE_PROVIDER_EVAL_ACK_PUBLIC_ONLY", raising=False)
    try:
        run_live_provider_evaluation("openai", 1)
    except RuntimeError as exc:
        assert str(exc) == "LIVE_PROVIDER_EVAL_PUBLIC_ONLY_ACK_REQUIRED"
    else:
        raise AssertionError("live provider evaluation must fail closed")
