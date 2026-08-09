from datetime import date, datetime, timezone

from wallet_twin_v2.contracts import (
    CalibrationObservation,
    ClaimClass,
    CuratedMetadata,
    EvidenceTier,
)
from wallet_twin_v2.wallet_model import HierarchicalWalletModel


def metadata(key: str):
    now = datetime(2026, 6, 30, tzinfo=timezone.utc)
    return CuratedMetadata(
        business_key=key,
        source_system_key=key,
        event_time=now,
        valid_from=now,
        source_hash="a" * 64,
        transformation_version="test",
        data_owner="test",
        entitlement_domain="test",
    )


def test_e3_observation_materially_updates_share_and_marks_it_measured():
    observation = CalibrationObservation(
        observation_id="obs-1",
        entity_id="E99",
        product="Payments",
        sector="consumer",
        measured_share=0.55,
        total_wallet=1_000,
        tier=EvidenceTier.E3,
        selection_weight=1.0,
        as_of=date(2026, 6, 30),
        metadata=metadata("obs-1"),
    )
    model = HierarchicalWalletModel([observation], draws=2_000)
    estimate, _, _ = model.estimate(
        opportunity_id="E99-payments",
        entity_id="E99",
        product="Payments",
        sector="consumer",
        observed_activity=500,
        as_of=date(2026, 6, 30),
        evidence_tier=EvidenceTier.E3,
        direct_share=0.55,
    )
    assert estimate.share_claim == ClaimClass.OBSERVED
    assert 0.50 < estimate.share_interval.median < 0.60
    assert estimate.diagnostics["calibration_observations"] == 1


def test_public_anchor_is_noisy_and_does_not_become_observed_truth():
    estimate, _, _ = HierarchicalWalletModel(draws=2_000).estimate(
        opportunity_id="E99-fx",
        entity_id="E99",
        product="Cross-border FX",
        sector="mining",
        observed_activity=100,
        as_of=date(2026, 6, 30),
        evidence_tier=EvidenceTier.E1,
        anchor_range=(300, 400, 700),
        fact_ids=("FACT-1",),
    )
    assert estimate.share_claim == ClaimClass.POSTERIOR
    assert estimate.diagnostics["anchor_weight"] < 0.5
    assert estimate.identification_bounds.lower == 300
    assert estimate.identification_bounds.upper == 700
