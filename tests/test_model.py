import numpy as np
from dataclasses import replace

from wallet_twin.model import OpportunityInput, estimate_opportunity, seasonal_naive_backtest, synthetic_recovery


def sample_input() -> OpportunityInput:
    return OpportunityInput(
        entity_id="E99",
        product="Trade finance",
        observed_activity=1_000_000_000,
        recurrence=1.0,
        relationship_breadth=0.8,
        scale_percentile=0.7,
        trend=0.05,
        data_quality=0.98,
        evidence_coverage=0.70,
        fit=0.95,
        timing=0.75,
        share_prior_mean=0.26,
        share_prior_concentration=8,
        economic_rate_bps=(20, 45, 85),
        target_share=(0.30, 0.40, 0.50),
    )


def test_wallet_identity_and_bounds_are_coherent():
    result, samples = estimate_opportunity(sample_input(), draws=2_000)
    assert result["observed_activity_zar"] <= result["total_wallet_zar"]["p10"]
    assert 0 < result["current_share"]["p10"] <= result["current_share"]["p90"] < 1
    assert result["partial_identification_zar"]["lower"] <= result["partial_identification_zar"]["upper"]
    assert np.all(samples >= 0)


def test_model_is_reproducible():
    first, first_samples = estimate_opportunity(sample_input(), draws=500)
    second, second_samples = estimate_opportunity(sample_input(), draws=500)
    assert first == second
    assert np.array_equal(first_samples, second_samples)


def test_audited_anchor_narrows_relative_interval_and_raises_confidence():
    baseline, _ = estimate_opportunity(sample_input(), draws=2_000)
    anchored_input = replace(
        sample_input(),
        anchor_low=4_000_000_000,
        anchor_base=5_000_000_000,
        anchor_high=6_000_000_000,
        anchor_weight=0.84,
        anchor_name="Audited test anchor",
        anchor_fact_ids=("FACT-1",),
        evidence_coverage=0.90,
        evidence_coverage_before_anchor=0.70,
    )
    anchored, _ = estimate_opportunity(anchored_input, draws=2_000)
    assert anchored["anchor_impact"]["active"] is True
    assert anchored["anchor_impact"]["relative_interval_width_reduction"] > 0
    assert anchored["confidence"] > anchored["anchor_impact"]["confidence_before"]
    assert anchored["anchor_impact"]["prior_only_total_wallet_zar"] == baseline["total_wallet_zar"]


def test_seasonal_naive_is_exact_on_repeating_series():
    series = list(range(1, 13)) * 3
    result = seasonal_naive_backtest(series)
    assert result["wape"] == 0
    assert result["rmse"] == 0


def test_synthetic_interval_is_calibrated_to_its_declared_dgp():
    result = synthetic_recovery(n=1_000)
    assert 0.74 <= result["p10_p90_coverage"] <= 0.86
    assert result["rank_correlation"] > 0.80
