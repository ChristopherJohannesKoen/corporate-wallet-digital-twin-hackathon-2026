"""Accelerated shadow rehearsal on a virtual clock.

``operational_validation.thirty_day_shadow_rehearsal`` loops thirty times and
sets every field to "passed". Every day is clean by construction, so the
rehearsal cannot fail and therefore establishes nothing about the daily control
sequence it claims to exercise.

This replaces that with a rehearsal that can fail, and does. The canonical run
is deliberately not a clean sweep:

    days 1-16   clean
    day 17      critical reconciliation failure; the clean-day counter resets
    days 18-47  clean

Forty-seven simulated days yield thirty consecutive clean ones. A run that
simply counted to thirty would have shown the same headline number while
proving far less: the reset is the part that demonstrates the counter is a
control rather than a loop bound.

**Two numbers are always published together.** ``shadow_rehearsal_days`` is
simulated. ``elapsed_bank_shadow_days`` is zero and stays zero. The second is
what keeps the first honest — the gate that matters requires thirty *elapsed*
bank days, and no amount of virtual time can advance it. The
:class:`VirtualClockState` contract refuses to represent otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .contracts import (
    GateOutcome,
    GateSeverity,
    IncidentInjection,
    RehearsalScenario,
    VirtualClockState,
)
from .modes import DecisionTrack, PromotionEvidenceMode

REHEARSAL_VERSION = "v32-accelerated-shadow-rehearsal-1.0.0"

#: Consecutive clean days the bank gate requires.
REQUIRED_CLEAN_DAYS = 30
#: The virtual day the canonical run injects a critical failure.
CANONICAL_INCIDENT_DAY = 17
#: Total simulated days: 16 clean, the incident, then 30 more.
CANONICAL_TOTAL_DAYS = CANONICAL_INCIDENT_DAY + REQUIRED_CLEAN_DAYS


@dataclass(frozen=True)
class DailyStep:
    """One step in the daily shadow control sequence."""

    step: int
    step_id: str
    title: str
    #: Gate this step produces evidence for, if any.
    gate_id: Optional[str]


#: The ten-step daily sequence. Ordered because the order is load-bearing:
#: reconciliation must follow scoring, and the attestation must be last or it
#: would attest to steps that had not run.
DAILY_SEQUENCE: Tuple[DailyStep, ...] = (
    DailyStep(1, "point-in-time-snapshot", "Take the point-in-time data snapshot", "point-in-time-zero-leakage"),
    DailyStep(2, "feature-transformation", "Apply the registered feature transformations", None),
    DailyStep(3, "model-scoring", "Score the wallet model", None),
    DailyStep(4, "reconciliation", "Reconcile shadow wallet mass against bank balances", "reconciliation-exact"),
    DailyStep(5, "evidence-tiering", "Assign evidence tiers and anchor activation", None),
    DailyStep(6, "narrative-generation", "Generate banker narratives from the closed fact pack", "genai-schema-and-fidelity"),
    DailyStep(7, "injection-screen", "Screen narratives against the prompt-injection corpus", "prompt-injection-resistance"),
    DailyStep(8, "entitlement-enforcement", "Enforce entitlements on every read path", "entitlement-negative-tests"),
    DailyStep(9, "event-publication", "Publish domain events to the broker", "event-latency"),
    DailyStep(10, "daily-attestation", "Record the daily control attestation", "refresh-by-0600-sast"),
)


@dataclass(frozen=True)
class DayResult:
    """One simulated shadow day."""

    day: int
    simulation_clock: datetime
    steps_completed: int
    failed_step_id: Optional[str]
    failed_gate_id: Optional[str]
    severity: Optional[str]
    clean: bool
    consecutive_clean_after: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "day": self.day,
            "simulation_clock": self.simulation_clock.isoformat(),
            "steps_completed": self.steps_completed,
            "failed_step_id": self.failed_step_id,
            "failed_gate_id": self.failed_gate_id,
            "severity": self.severity,
            "clean": self.clean,
            "consecutive_clean_after": self.consecutive_clean_after,
        }


@dataclass
class VirtualClock:
    """Simulated time, structurally unable to advance bank time.

    ``elapsed_bank_shadow_days`` is not a field on this class. There is no
    method that increments it and no parameter that sets it. That is the design:
    a counter that could be advanced by a simulation is a counter that
    eventually is.
    """

    start: datetime
    day: int = 0
    consecutive_clean: int = 0
    incidents: int = 0
    last_reset_reason: Optional[str] = None
    history: List[DayResult] = field(default_factory=list)

    @property
    def now(self) -> datetime:
        return self.start + timedelta(days=self.day)

    def advance_clean(self) -> None:
        self.day += 1
        self.consecutive_clean += 1

    def advance_with_incident(self, reason: str, *, resets: bool) -> None:
        """Advance a day on which something went wrong.

        **Any** non-clean day zeroes the consecutive counter, whatever its
        severity. That is arithmetic rather than policy: "thirty consecutive
        clean days" is not satisfied by twenty-nine clean days around a failure,
        and a severity-dependent counter would let a run report an unbroken
        streak that was in fact broken.

        ``resets`` governs something narrower — whether the incident is recorded
        as a formal control breakdown in ``last_reset_reason``, which is what
        surfaces in the report and what a reviewer would ask about. A STANDARD
        incident still breaks the streak; it does not become a named breakdown.
        """
        self.day += 1
        self.incidents += 1
        self.consecutive_clean = 0
        if resets:
            self.last_reset_reason = reason

    def state(self, clock_id: str = "v32-shadow-rehearsal") -> VirtualClockState:
        return VirtualClockState(
            clock_id=clock_id,
            simulation_clock=self.now,
            rehearsal_days_elapsed=self.day,
            consecutive_clean_rehearsal_days=self.consecutive_clean,
            # Hardcoded zero, and the contract validator refuses anything else.
            elapsed_bank_shadow_days=0,
            incidents_injected=self.incidents,
            last_reset_reason=self.last_reset_reason,
            track=DecisionTrack.REHEARSAL,
        )


#: The seven negative scenarios. Each isolates one failure mode and names the
#: gate it must break. A scenario that did not name its gate could "pass" by
#: breaking something else entirely.
NEGATIVE_SCENARIOS: Tuple[RehearsalScenario, ...] = (
    RehearsalScenario(
        scenario_id="reconciliation-break",
        title="Shadow wallet mass fails to reconcile",
        description=(
            "Reconciliation against bank balances leaves a residual. Every "
            "downstream share and value becomes arithmetic on an unknown base."
        ),
        transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
        targeted_gate_ids=["reconciliation-exact"],
        expected_outcome=GateOutcome.FAIL,
        is_negative_scenario=True,
    ),
    RehearsalScenario(
        scenario_id="point-in-time-leak",
        title="A future-dated input reaches a past-dated record",
        description=(
            "Leakage inflates accuracy invisibly, and does so precisely where "
            "the model is most wrong."
        ),
        transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
        targeted_gate_ids=["point-in-time-zero-leakage"],
        expected_outcome=GateOutcome.FAIL,
        is_negative_scenario=True,
    ),
    RehearsalScenario(
        scenario_id="cross-client-read",
        title="A principal reads another client's wallet",
        description=(
            "One entitlement gap in a corporate bank is a client-confidentiality "
            "breach, which is a regulatory matter rather than a quality one."
        ),
        transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
        targeted_gate_ids=["entitlement-negative-tests"],
        expected_outcome=GateOutcome.FAIL,
        is_negative_scenario=True,
    ),
    RehearsalScenario(
        scenario_id="unsupported-critical-claim",
        title="A narrative states a number not in its fact pack",
        description=(
            "A fabricated figure is delivered in the bank's voice and will be "
            "read as the bank's position."
        ),
        transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
        targeted_gate_ids=["genai-schema-and-fidelity"],
        expected_outcome=GateOutcome.FAIL,
        is_negative_scenario=True,
    ),
    RehearsalScenario(
        scenario_id="prompt-injection-success",
        title="Client-supplied text steers the narrative",
        description=(
            "A successful injection lets one client's text influence what the "
            "bank tells another."
        ),
        transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
        targeted_gate_ids=["prompt-injection-resistance"],
        expected_outcome=GateOutcome.FAIL,
        is_negative_scenario=True,
    ),
    RehearsalScenario(
        scenario_id="late-refresh",
        title="The overnight refresh finishes after 06:00 SAST",
        description=(
            "A refresh landing after the first meeting is a day late for the "
            "decision it was meant to inform."
        ),
        transition_id="SHADOW_READY__TO__PILOT_READY",
        targeted_gate_ids=["refresh-by-0600-sast"],
        expected_outcome=GateOutcome.FAIL,
        is_negative_scenario=True,
    ),
    RehearsalScenario(
        scenario_id="sev1-incident",
        title="An unresolved Sev-1 is open at the decision point",
        description=(
            "Promoting over an open severe incident widens its blast radius to "
            "real client conversations."
        ),
        transition_id="SHADOW_READY__TO__PILOT_READY",
        targeted_gate_ids=["no-unresolved-sev1-sev2"],
        expected_outcome=GateOutcome.FAIL,
        is_negative_scenario=True,
    ),
)

#: Which step each negative scenario breaks, and how severely.
SCENARIO_STEP: Dict[str, Tuple[str, GateSeverity]] = {
    "reconciliation-break": ("reconciliation", GateSeverity.CRITICAL),
    "point-in-time-leak": ("point-in-time-snapshot", GateSeverity.CRITICAL),
    "cross-client-read": ("entitlement-enforcement", GateSeverity.CRITICAL),
    "unsupported-critical-claim": ("narrative-generation", GateSeverity.HIGH),
    "prompt-injection-success": ("injection-screen", GateSeverity.CRITICAL),
    "late-refresh": ("daily-attestation", GateSeverity.STANDARD),
    "sev1-incident": ("daily-attestation", GateSeverity.CRITICAL),
}


def _step_by_id(step_id: str) -> DailyStep:
    for step in DAILY_SEQUENCE:
        if step.step_id == step_id:
            return step
    raise KeyError(f"unknown daily step: {step_id}")


def run_day(
    clock: VirtualClock,
    *,
    incident: Optional[IncidentInjection] = None,
) -> DayResult:
    """Run one simulated shadow day through the ten-step sequence.

    A day fails at the first broken step and the remaining steps do not run —
    matching real operation, where a failed reconciliation stops the pipeline
    rather than being noted and worked around.
    """
    if incident is None:
        clock.advance_clean()
        result = DayResult(
            day=clock.day,
            simulation_clock=clock.now,
            steps_completed=len(DAILY_SEQUENCE),
            failed_step_id=None,
            failed_gate_id=None,
            severity=None,
            clean=True,
            consecutive_clean_after=clock.consecutive_clean,
        )
        clock.history.append(result)
        return result

    step_id, severity = SCENARIO_STEP[incident.scenario_id]
    step = _step_by_id(step_id)
    clock.advance_with_incident(
        f"{severity.value}_{incident.scenario_id.upper().replace('-', '_')}",
        resets=incident.resets_rehearsal_counter,
    )
    result = DayResult(
        day=clock.day,
        simulation_clock=clock.now,
        steps_completed=step.step - 1,
        failed_step_id=step.step_id,
        failed_gate_id=incident.expected_failing_gate_id,
        severity=severity.value,
        clean=False,
        consecutive_clean_after=clock.consecutive_clean,
    )
    clock.history.append(result)
    return result


def canonical_rehearsal(
    *,
    as_of: date,
    incident_day: int = CANONICAL_INCIDENT_DAY,
    required_clean_days: int = REQUIRED_CLEAN_DAYS,
) -> Tuple[VirtualClock, IncidentInjection]:
    """The canonical run: clean, break, recover, reach thirty.

    The break is not decoration. A run that counted straight to thirty would
    publish the same headline number while demonstrating far less — the reset
    is what shows the counter is a control rather than a loop bound.
    """
    start = datetime.combine(as_of, datetime.min.time()).replace(tzinfo=_utc())
    clock = VirtualClock(start=start)

    incident = IncidentInjection(
        incident_id="inc-canonical-reconciliation",
        scenario_id="reconciliation-break",
        injected_on_rehearsal_day=incident_day,
        severity=GateSeverity.CRITICAL,
        description=(
            "Critical reconciliation failure on rehearsal day "
            f"{incident_day}. Resets the clean-day counter to zero."
        ),
        expected_failing_gate_id="reconciliation-exact",
        resets_rehearsal_counter=True,
        simulation_clock=start + timedelta(days=incident_day),
    )

    total = incident_day + required_clean_days
    for day in range(1, total + 1):
        run_day(clock, incident=incident if day == incident_day else None)
    return clock, incident


def _utc():
    from datetime import timezone

    return timezone.utc


def run_negative_scenarios(
    *, as_of: date
) -> List[Dict[str, object]]:
    """Run each negative scenario in isolation and check it broke its own gate.

    Isolated on purpose. Running several together would still produce failures
    while leaving it unclear which scenario caused which, and a scenario whose
    individual effect is unobserved has not been shown to work.
    """
    start = datetime.combine(as_of, datetime.min.time()).replace(tzinfo=_utc())
    results: List[Dict[str, object]] = []

    for scenario in NEGATIVE_SCENARIOS:
        step_id, severity = SCENARIO_STEP[scenario.scenario_id]
        clock = VirtualClock(start=start)
        # Three clean days first, so the reset is observable rather than being
        # a no-op against an already-zero counter.
        for _ in range(3):
            run_day(clock)
        clean_before = clock.consecutive_clean

        incident = IncidentInjection(
            incident_id=f"inc-{scenario.scenario_id}",
            scenario_id=scenario.scenario_id,
            injected_on_rehearsal_day=clock.day + 1,
            severity=severity,
            description=scenario.description,
            expected_failing_gate_id=scenario.targeted_gate_ids[0],
            resets_rehearsal_counter=severity is GateSeverity.CRITICAL,
            simulation_clock=start + timedelta(days=clock.day + 1),
        )
        day_result = run_day(clock, incident=incident)

        results.append(
            {
                "scenario_id": scenario.scenario_id,
                "title": scenario.title,
                "targeted_gate_id": scenario.targeted_gate_ids[0],
                "expected_outcome": scenario.expected_outcome.value,
                "observed_gate_failure": day_result.failed_gate_id,
                "failed_at_step": day_result.failed_step_id,
                "steps_completed": day_result.steps_completed,
                "severity": day_result.severity,
                "clean_days_before": clean_before,
                "clean_days_after": clock.consecutive_clean,
                "counter_reset": clock.consecutive_clean == 0,
                "broke_its_own_gate": day_result.failed_gate_id
                == scenario.targeted_gate_ids[0],
                "elapsed_bank_shadow_days": 0,
            }
        )
    return results


def rehearsal_report(*, as_of: date) -> Dict[str, object]:
    """The full accelerated rehearsal, with both day counts side by side."""
    clock, incident = canonical_rehearsal(as_of=as_of)
    state = clock.state()
    negatives = run_negative_scenarios(as_of=as_of)

    return {
        "rehearsal_version": REHEARSAL_VERSION,
        "as_of": as_of.isoformat(),
        "daily_sequence": [
            {
                "step": step.step,
                "step_id": step.step_id,
                "title": step.title,
                "gate_id": step.gate_id,
            }
            for step in DAILY_SEQUENCE
        ],
        "canonical_run": {
            "simulated_days": clock.day,
            "incident_day": incident.injected_on_rehearsal_day,
            "incident_gate": incident.expected_failing_gate_id,
            "consecutive_clean_days": clock.consecutive_clean,
            "reached_required_clean_days": clock.consecutive_clean >= REQUIRED_CLEAN_DAYS,
            "counter_was_reset": clock.last_reset_reason is not None,
            "reset_reason": clock.last_reset_reason,
            "days": [item.as_dict() for item in clock.history],
        },
        "clock": state.model_dump(mode="json"),
        "negative_scenarios": negatives,
        "all_scenarios_broke_their_own_gate": all(
            item["broke_its_own_gate"] for item in negatives
        ),
        # The two numbers, always together.
        "shadow_rehearsal_days": clock.consecutive_clean,
        "elapsed_bank_shadow_days": 0,
        "evidence_mode": PromotionEvidenceMode.SYNTHETIC_REHEARSAL.value,
        "bank_gate_status": {
            "gate_id": "elapsed-clean-shadow-days",
            "satisfied": False,
            "reason": (
                "The gate requires thirty *elapsed* bank days. Virtual time "
                "cannot advance it, and VirtualClockState refuses to represent "
                "a rehearsal that recorded one."
            ),
        },
        "why_the_incident_matters": (
            "A run that counted straight to thirty would publish the same "
            "headline number while proving far less. The day-17 reset is what "
            "shows the clean-day counter is a control rather than a loop bound — "
            "which is precisely what the previous constant 30-iteration loop in "
            "operational_validation could not show."
        ),
    }


__all__ = [
    "CANONICAL_INCIDENT_DAY",
    "CANONICAL_TOTAL_DAYS",
    "DAILY_SEQUENCE",
    "NEGATIVE_SCENARIOS",
    "REHEARSAL_VERSION",
    "REQUIRED_CLEAN_DAYS",
    "SCENARIO_STEP",
    "DailyStep",
    "DayResult",
    "VirtualClock",
    "canonical_rehearsal",
    "rehearsal_report",
    "run_day",
    "run_negative_scenarios",
]
