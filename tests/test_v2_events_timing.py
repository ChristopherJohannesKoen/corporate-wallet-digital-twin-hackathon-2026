from datetime import date, datetime, timedelta, timezone

import pytest

from wallet_twin_v2.contracts import (
    ArtifactReference,
    DeploymentEnvironment,
    EntitlementContext,
    EventEnvelope,
    EventType,
)
from wallet_twin_v2.events import ClusterRandomizedEncouragement, EventStore
from wallet_twin_v2.timing import TimingService


def _artifacts() -> ArtifactReference:
    return ArtifactReference(
        model_version="wallet-2",
        dataset_version="snapshot-1",
        prior_version="prior-1",
        transformation_version="features-1",
    )


def _entitlements() -> EntitlementContext:
    return EntitlementContext(
        user_id="rm-1",
        roles=["SHADOW_VALIDATOR"],
        team="team-a",
        regions=["ZA"],
        client_ids=["E01"],
        products=["Trade Finance"],
        environment=DeploymentEnvironment.SHADOW,
    )


def test_cluster_assignment_is_stable_with_valid_probability():
    randomizer = ClusterRandomizedEncouragement(treatment_probability=0.4, salt="sealed")
    kwargs = dict(
        cluster_id="team-a",
        recommendation_id="rec-1",
        entity_id="E01",
        product="Trade Finance",
        as_of=date(2026, 8, 8),
        artifacts=_artifacts(),
        entitlement_context=_entitlements(),
    )
    first = randomizer.assign(**kwargs)
    second = randomizer.assign(**kwargs)
    assert first.assignment_arm == second.assignment_arm
    assert first.assignment_probability in {0.4, 0.6}


def test_assignment_event_without_probability_is_rejected():
    store = EventStore()
    event = EventEnvelope(
        event_id="bad-assignment",
        event_type=EventType.RECOMMENDATION_ASSIGNED,
        assignment_arm="CONTROL",
    )
    with pytest.raises(ValueError, match="assignment probability"):
        store.append(event)


def test_start_stop_table_and_probabilities_are_well_formed():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first_event = start + timedelta(days=20)
    censor = start + timedelta(days=90)
    intervals = TimingService.build_start_stop_intervals(
        opportunity_id="E01-TRADE",
        entity_id="E01",
        product="Trade Finance",
        eligibility_at=start,
        censor_at=censor,
        events=[(first_event, "BANKER_ACTION")],
        covariates={"seasonal_ratio": 1.2},
    )
    assert len(intervals) == 2
    assert intervals[0].event_code == "BANKER_ACTION"
    assert intervals[1].censored is True

    prediction = TimingService().predict_baseline(
        as_of=date(2026, 8, 8),
        event_name="qualified_rm_action",
        seasonal_ratio=1.2,
        maturity_days=45,
    )
    assert 0 < prediction.probability_30d < prediction.probability_60d < prediction.probability_90d < 1


def test_cox_gate_enforces_both_event_thresholds():
    assert TimingService.promotion_gate(199, 100, 5)["passed"] is False
    assert TimingService.promotion_gate(200, 49, 5)["passed"] is False
    assert TimingService.promotion_gate(200, 50, 5)["passed"] is True
