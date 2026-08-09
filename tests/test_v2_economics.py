from datetime import date

from wallet_twin_v2.contracts import CommercialStatus, DeploymentEnvironment
from wallet_twin_v2.economics import EconomicsService
from wallet_twin_v2.fixtures import synthetic_rate_card


def test_production_blocks_synthetic_economics():
    result = EconomicsService().evaluate(
        as_of=date(2026, 6, 30),
        environment=DeploymentEnvironment.PRODUCTION,
        rate_card=synthetic_rate_card("Payments", 10, date(2026, 6, 30)),
        observed_activity=100,
        wallet_median=500,
        current_share=0.2,
        target_share=0.4,
    )
    assert result.status == CommercialStatus.BLOCKED
    assert "SYNTHETIC_RATE_BLOCKED_IN_CONTROLLED_ENVIRONMENT" in result.reason_codes


def test_fixture_economics_are_watermarked_and_not_causal():
    result = EconomicsService().evaluate(
        as_of=date(2026, 6, 30),
        environment=DeploymentEnvironment.FIXTURE,
        rate_card=synthetic_rate_card("Payments", 10, date(2026, 6, 30)),
        observed_activity=100,
        wallet_median=500,
        current_share=0.2,
        target_share=0.4,
        causal_uplift=0.2,
        causal_model_approved=False,
    )
    assert result.status == CommercialStatus.SIMULATED
    assert result.watermark == "SIMULATED NON-PRODUCTION ECONOMICS"
    assert result.causal_expected_incremental_value is None
    assert "CAUSAL_VALUE_WITHHELD_UNTIL_VALIDATION" in result.reason_codes
