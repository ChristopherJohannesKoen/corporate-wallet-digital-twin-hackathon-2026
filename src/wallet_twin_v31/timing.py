"""Engagement windows and "why now".

The window is calculated backwards from a dated trigger and the solution's
required preparation lead time.  If no supported trigger exists the system says
so and returns a low, flat probability: it does not manufacture urgency out of
a model score.

Signals combined:

* the existing V2/V3 30/60/90-day timing probabilities;
* BOCPD change-point signals from V3;
* debt and instrument maturities;
* publication-timed business events;
* seasonal transaction patterns observed in the bank's own flows;
* the governed preparation lead time for the solution.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Optional, Sequence, Tuple

from wallet_twin_v2.contracts import ClaimClass

from .contracts import BusinessEvent, EngagementWindow, ProblemHypothesis
from .taxonomy import (
    BankingSolution,
    SOLUTION_LEAD_TIME_DAYS,
)

TIMING_POLICY_VERSION = "v31-engagement-window-3.1.1"

NO_TRIGGER_STATEMENT = (
    "No dated, supported trigger event is established for this client and problem. There "
    "is no time-critical reason to act this week; the window below reflects background "
    "likelihood only."
)
SCENARIO_CALIBRATION = (
    "GOVERNED_SCENARIO_NOT_RM_OUTCOME_CALIBRATED â€” horizon probabilities combine a dated "
    "trigger with governed lead times and are not calibrated against qualified RM actions"
)

#: How strongly each event type justifies acting now.
EVENT_URGENCY: Mapping[str, float] = {
    "DEBT_MATURITY_WINDOW": 0.80,
    "DEBT_MATURITY_WINDOW_ELAPSED": 0.65,
    "TRADE_EVENT_PIPELINE": 0.60,
    "CHANGE_POINT_DETECTED": 0.55,
    "OBSERVED_FLOW_SHIFT": 0.40,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class EngagementWindowEngine:
    version = TIMING_POLICY_VERSION

    def __init__(self, as_of: date) -> None:
        self.as_of = as_of

    def _select_trigger(
        self,
        problem: ProblemHypothesis,
        events: Sequence[BusinessEvent],
    ) -> Optional[BusinessEvent]:
        candidates = [
            event
            for event in events
            if problem.problem in event.implied_problems
            and event.available_date <= self.as_of
            and event.evidence_claim_ids
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda event: (
                EVENT_URGENCY.get(event.event_type, 0.3),
                -abs((event.event_date - self.as_of).days),
            ),
        )

    def build(
        self,
        entity_id: str,
        problem: ProblemHypothesis,
        solution: BankingSolution,
        events: Sequence[BusinessEvent],
        *,
        legacy_timing: Optional[Tuple[float, float, float]] = None,
        change_signal: Optional[Any] = None,
    ) -> EngagementWindow:
        lead_time = SOLUTION_LEAD_TIME_DAYS[solution]
        trigger = self._select_trigger(problem, events)
        window_id = (
            f"window:{entity_id}:{problem.problem.value.lower()}:{solution.value.lower()}"
        )

        if trigger is None:
            base = min(0.25, (problem.probability or 0.0) * 0.35)
            if legacy_timing is not None:
                base = min(base, legacy_timing[0])
            return EngagementWindow(
                window_id=window_id,
                trigger_name="NO_SUPPORTED_TRIGGER",
                trigger_supported=False,
                lead_time_days=lead_time,
                probability_30d=base * 0.5,
                probability_60d=base * 0.75,
                probability_90d=base,
                why_now=NO_TRIGGER_STATEMENT,
                claim_class=ClaimClass.SCENARIO,
                calibration_status=SCENARIO_CALIBRATION,
            )

        # The conversation has to start early enough for the bank to deliver.
        start = trigger.event_date - timedelta(days=lead_time)
        if start < self.as_of:
            start = self.as_of
        end = max(start, trigger.event_date)
        days_to_event = (trigger.event_date - self.as_of).days
        urgency = EVENT_URGENCY.get(trigger.event_type, 0.3)

        if days_to_event <= 0:
            # The trigger has already passed; urgency comes from the fact that
            # the position is now unconfirmed, not from a future date.
            horizon_weight = 0.85
        else:
            slack = days_to_event - lead_time
            horizon_weight = _clamp(1.0 - slack / max(lead_time, 1) * 0.5, 0.35, 1.0)

        base = _clamp(urgency * horizon_weight * (0.4 + 0.6 * (problem.probability or 0.0)))
        if change_signal is not None:
            base = _clamp(
                max(base, 0.5 * base + 0.5 * float(change_signal.probability_90d))
            )
        if legacy_timing is not None:
            base = _clamp(0.6 * base + 0.4 * legacy_timing[2])

        p90 = base
        p60 = base * 0.78
        p30 = base * 0.52

        if days_to_event <= 0:
            why_now = (
                f"{trigger.label}. Preparation for {solution.value.replace('_', ' ').lower()} "
                f"takes about {lead_time} days, so the position needs confirming now."
            )
        else:
            why_now = (
                f"{trigger.label}. The event is dated {trigger.event_date.isoformat()} "
                f"({days_to_event} days away) and preparation takes about {lead_time} days, "
                f"so the conversation window opens {start.isoformat()}."
            )

        return EngagementWindow(
            window_id=window_id,
            trigger_name=trigger.event_type,
            trigger_supported=True,
            trigger_event_key=trigger.event_key,
            trigger_date=trigger.event_date,
            start_date=start,
            end_date=end,
            lead_time_days=lead_time,
            probability_30d=p30,
            probability_60d=p60,
            probability_90d=p90,
            why_now=why_now,
            claim_class=ClaimClass.SCENARIO,
            calibration_status=SCENARIO_CALIBRATION,
        )
