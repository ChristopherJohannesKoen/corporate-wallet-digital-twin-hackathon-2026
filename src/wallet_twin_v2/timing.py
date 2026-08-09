from __future__ import annotations

import math
from datetime import date, datetime
from typing import Iterable, List, Optional

from .contracts import StartStopInterval, TimingPrediction


class TimingService:
    baseline_version = "seasonal-hazard-baseline-2.0.0"

    @staticmethod
    def promotion_gate(eligible_events: int, outcome_events: int, effective_degrees_of_freedom: int) -> dict:
        required_outcomes = max(1, 10 * effective_degrees_of_freedom)
        passed = eligible_events >= 200 and outcome_events >= required_outcomes
        return {
            "passed": passed,
            "eligible_events": eligible_events,
            "minimum_eligible_events": 200,
            "outcome_events": outcome_events,
            "minimum_outcome_events": required_outcomes,
            "decision": "COX_ELIGIBLE" if passed else "RETAIN_SEASONAL_BASELINE",
        }

    def predict_baseline(
        self,
        *,
        as_of: date,
        event_name: str,
        seasonal_ratio: float,
        maturity_days: Optional[int] = None,
        recurrence: float = 0.5,
    ) -> TimingPrediction:
        seasonal_ratio = max(0.25, min(3.0, seasonal_ratio))
        recurrence = max(0.0, min(1.0, recurrence))
        daily_hazard = 0.0025 * seasonal_ratio * (0.6 + 0.8 * recurrence)
        if maturity_days is not None and 0 <= maturity_days <= 90:
            daily_hazard *= 1.0 + 1.5 * (1.0 - maturity_days / 90.0)

        def cumulative(days: int) -> float:
            return 1.0 - math.exp(-daily_hazard * days)

        return TimingPrediction(
            event_name=event_name,
            probability_30d=cumulative(30),
            probability_60d=cumulative(60),
            probability_90d=cumulative(90),
            method=self.baseline_version,
            calibration_status="TRANSPARENT_BASELINE_NOT_EVENT_CALIBRATED",
            as_of=as_of,
        )

    @staticmethod
    def build_start_stop_intervals(
        *,
        opportunity_id: str,
        entity_id: str,
        product: str,
        eligibility_at: datetime,
        censor_at: datetime,
        events: Iterable[tuple[datetime, str]],
        covariates: Optional[dict] = None,
    ) -> List[StartStopInterval]:
        ordered = sorted((when, code) for when, code in events if eligibility_at < when <= censor_at)
        intervals: List[StartStopInterval] = []
        start = eligibility_at
        for when, code in ordered:
            intervals.append(
                StartStopInterval(
                    opportunity_id=opportunity_id,
                    entity_id=entity_id,
                    product=product,
                    start_at=start,
                    stop_at=when,
                    event_code=code,
                    censored=False,
                    covariates=covariates or {},
                )
            )
            start = when
        if start < censor_at:
            intervals.append(
                StartStopInterval(
                    opportunity_id=opportunity_id,
                    entity_id=entity_id,
                    product=product,
                    start_at=start,
                    stop_at=censor_at,
                    event_code=None,
                    censored=True,
                    covariates=covariates or {},
                )
            )
        return intervals
