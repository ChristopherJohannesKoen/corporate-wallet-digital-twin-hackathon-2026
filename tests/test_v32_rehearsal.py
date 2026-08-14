"""The accelerated shadow rehearsal.

The point of these tests is that the rehearsal can *fail*. The implementation
it replaces set every day to passed, so its only possible outcome was success —
which made it a constant rather than a test. Half of what follows checks that
things break when they should.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from wallet_twin_v32.contracts import GateSeverity, IncidentInjection, VirtualClockState
from wallet_twin_v32.modes import DecisionTrack
from wallet_twin_v32.rehearsal import (
    CANONICAL_INCIDENT_DAY,
    CANONICAL_TOTAL_DAYS,
    DAILY_SEQUENCE,
    NEGATIVE_SCENARIOS,
    REQUIRED_CLEAN_DAYS,
    SCENARIO_STEP,
    VirtualClock,
    rehearsal_report,
    run_day,
)

AS_OF = date(2026, 6, 30)
START = datetime(2026, 6, 30, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def report() -> dict:
    return rehearsal_report(as_of=AS_OF)


# --------------------------------------------------------------------------
# The canonical run reaches thirty by recovering, not by counting
# --------------------------------------------------------------------------


def test_forty_seven_simulated_days_yield_thirty_clean_ones(report: dict) -> None:
    run = report["canonical_run"]
    assert run["simulated_days"] == CANONICAL_TOTAL_DAYS == 47
    assert run["consecutive_clean_days"] == REQUIRED_CLEAN_DAYS == 30
    assert run["reached_required_clean_days"] is True


def test_the_counter_was_actually_reset(report: dict) -> None:
    """The part that distinguishes a control from a loop bound. Without the
    reset, the run would have counted straight to thirty and shown nothing."""
    run = report["canonical_run"]
    assert run["counter_was_reset"] is True
    assert run["incident_day"] == CANONICAL_INCIDENT_DAY == 17
    assert run["incident_gate"] == "reconciliation-exact"
    assert "RECONCILIATION" in run["reset_reason"]


def test_the_incident_day_is_not_clean_and_zeroes_the_streak(report: dict) -> None:
    days = {item["day"]: item for item in report["canonical_run"]["days"]}
    assert days[16]["clean"] is True
    assert days[16]["consecutive_clean_after"] == 16
    assert days[17]["clean"] is False
    assert days[17]["consecutive_clean_after"] == 0
    assert days[18]["clean"] is True
    assert days[18]["consecutive_clean_after"] == 1


def test_the_run_only_reaches_thirty_after_the_reset(report: dict) -> None:
    days = report["canonical_run"]["days"]
    reaching = [item["day"] for item in days if item["consecutive_clean_after"] >= 30]
    assert reaching == [47]


def test_a_failed_day_stops_the_pipeline_rather_than_working_around_it(
    report: dict,
) -> None:
    """Matching real operation: a failed reconciliation stops the run."""
    days = {item["day"]: item for item in report["canonical_run"]["days"]}
    assert days[17]["steps_completed"] < len(DAILY_SEQUENCE)
    assert days[17]["failed_step_id"] == "reconciliation"
    assert days[16]["steps_completed"] == len(DAILY_SEQUENCE) == 10


def test_a_run_without_an_incident_reaches_thirty_in_thirty_days() -> None:
    """Control case: the 47 is caused by the incident, not by the arithmetic."""
    clock = VirtualClock(start=START)
    for _ in range(30):
        run_day(clock)
    assert clock.day == 30
    assert clock.consecutive_clean == 30
    assert clock.last_reset_reason is None


# --------------------------------------------------------------------------
# Simulated time is not bank time
# --------------------------------------------------------------------------


def test_both_day_counts_are_published_together(report: dict) -> None:
    assert report["shadow_rehearsal_days"] == 30
    assert report["elapsed_bank_shadow_days"] == 0


def test_the_bank_gate_is_reported_unsatisfied_with_its_reason(report: dict) -> None:
    gate = report["bank_gate_status"]
    assert gate["gate_id"] == "elapsed-clean-shadow-days"
    assert gate["satisfied"] is False
    assert "elapsed" in gate["reason"]


def test_the_clock_cannot_record_an_elapsed_bank_day(report: dict) -> None:
    assert report["clock"]["elapsed_bank_shadow_days"] == 0
    with pytest.raises(ValidationError, match="elapsed_bank_shadow_days must be 0"):
        VirtualClockState(
            clock_id="forged",
            simulation_clock=START,
            rehearsal_days_elapsed=47,
            consecutive_clean_rehearsal_days=30,
            elapsed_bank_shadow_days=30,
        )


def test_the_virtual_clock_has_no_way_to_advance_bank_time() -> None:
    """Not merely validated: there is no field, method or parameter for it."""
    clock = VirtualClock(start=START)
    assert not hasattr(clock, "elapsed_bank_shadow_days")
    for _ in range(100):
        run_day(clock)
    assert clock.state().elapsed_bank_shadow_days == 0
    assert clock.day == 100


def test_the_rehearsal_clock_cannot_run_on_the_real_track() -> None:
    clock = VirtualClock(start=START)
    run_day(clock)
    assert clock.state().track is DecisionTrack.REHEARSAL


# --------------------------------------------------------------------------
# The ten-step daily sequence
# --------------------------------------------------------------------------


def test_the_daily_sequence_has_ten_ordered_steps(report: dict) -> None:
    steps = report["daily_sequence"]
    assert len(steps) == 10
    assert [item["step"] for item in steps] == list(range(1, 11))


def test_reconciliation_follows_scoring_and_attestation_is_last() -> None:
    """The order is load-bearing: an attestation that ran first would attest to
    steps that had not happened."""
    order = {step.step_id: step.step for step in DAILY_SEQUENCE}
    assert order["model-scoring"] < order["reconciliation"]
    assert order["narrative-generation"] < order["injection-screen"]
    assert order["daily-attestation"] == 10


def test_step_ids_are_unique() -> None:
    ids = [step.step_id for step in DAILY_SEQUENCE]
    assert len(ids) == len(set(ids))


def test_most_steps_produce_evidence_for_a_real_catalogue_gate() -> None:
    from wallet_twin_v32.catalogue import GATES_BY_ID

    bound = [step for step in DAILY_SEQUENCE if step.gate_id]
    assert len(bound) >= 7
    for step in bound:
        assert step.gate_id in GATES_BY_ID, step.step_id


# --------------------------------------------------------------------------
# Seven isolated negative scenarios
# --------------------------------------------------------------------------


def test_there_are_seven_negative_scenarios(report: dict) -> None:
    assert len(NEGATIVE_SCENARIOS) == 7
    assert len(report["negative_scenarios"]) == 7


def test_every_scenario_breaks_its_own_gate(report: dict) -> None:
    """A scenario that failed some other gate would 'pass' while proving
    nothing about the gate it names."""
    assert report["all_scenarios_broke_their_own_gate"] is True
    for scenario in report["negative_scenarios"]:
        assert scenario["observed_gate_failure"] == scenario["targeted_gate_id"]


def test_every_scenario_expects_failure(report: dict) -> None:
    for scenario in NEGATIVE_SCENARIOS:
        assert scenario.is_negative_scenario is True
        assert scenario.expected_outcome.value == "FAIL"


def test_scenarios_break_at_different_steps(report: dict) -> None:
    """Distinct failure modes, not one failure mode relabelled seven times."""
    steps = {item["failed_at_step"] for item in report["negative_scenarios"]}
    assert len(steps) >= 5


def test_each_scenario_is_run_in_isolation(report: dict) -> None:
    """Run together, failures would still appear while leaving it unclear which
    scenario caused which."""
    for scenario in report["negative_scenarios"]:
        assert scenario["clean_days_before"] == 3
        assert scenario["counter_reset"] is True
        assert scenario["clean_days_after"] == 0


def test_no_negative_scenario_records_a_bank_day(report: dict) -> None:
    for scenario in report["negative_scenarios"]:
        assert scenario["elapsed_bank_shadow_days"] == 0


def test_every_scenario_maps_to_a_daily_step() -> None:
    step_ids = {step.step_id for step in DAILY_SEQUENCE}
    assert set(SCENARIO_STEP) == {item.scenario_id for item in NEGATIVE_SCENARIOS}
    for scenario_id, (step_id, severity) in SCENARIO_STEP.items():
        assert step_id in step_ids, scenario_id
        assert isinstance(severity, GateSeverity)


# --------------------------------------------------------------------------
# Incidents are isolated to the rehearsal
# --------------------------------------------------------------------------


def test_an_incident_cannot_be_declared_to_affect_the_real_track() -> None:
    with pytest.raises(ValidationError, match="cannot .*affect the real track"):
        IncidentInjection(
            incident_id="inc-x",
            scenario_id="reconciliation-break",
            injected_on_rehearsal_day=17,
            severity=GateSeverity.CRITICAL,
            description="attempt to reach the real track",
            expected_failing_gate_id="reconciliation-exact",
            affects_real_track=True,
            simulation_clock=START,
        )


def test_any_non_clean_day_breaks_the_streak_whatever_its_severity() -> None:
    """Arithmetic, not policy: thirty *consecutive* clean days is not satisfied
    by twenty-nine clean days around a failure."""
    clock = VirtualClock(start=START)
    for _ in range(5):
        run_day(clock)
    assert clock.consecutive_clean == 5

    run_day(
        clock,
        incident=IncidentInjection(
            incident_id="inc-minor",
            scenario_id="late-refresh",
            injected_on_rehearsal_day=6,
            severity=GateSeverity.STANDARD,
            description="a late refresh, not a control breakdown",
            expected_failing_gate_id="refresh-by-0600-sast",
            resets_rehearsal_counter=False,
            simulation_clock=START + timedelta(days=6),
        ),
    )
    assert clock.consecutive_clean == 0
    # ...but it is not recorded as a formal control breakdown.
    assert clock.last_reset_reason is None


def test_a_critical_incident_is_recorded_as_a_control_breakdown() -> None:
    clock = VirtualClock(start=START)
    run_day(
        clock,
        incident=IncidentInjection(
            incident_id="inc-major",
            scenario_id="reconciliation-break",
            injected_on_rehearsal_day=1,
            severity=GateSeverity.CRITICAL,
            description="reconciliation failure",
            expected_failing_gate_id="reconciliation-exact",
            simulation_clock=START + timedelta(days=1),
        ),
    )
    assert clock.consecutive_clean == 0
    assert clock.last_reset_reason is not None
    assert clock.incidents == 1


def test_a_critical_incident_must_reset_the_counter() -> None:
    with pytest.raises(ValidationError, match="would let a broken run count as clean"):
        IncidentInjection(
            incident_id="inc-y",
            scenario_id="reconciliation-break",
            injected_on_rehearsal_day=17,
            severity=GateSeverity.CRITICAL,
            description="critical failure that does not reset",
            expected_failing_gate_id="reconciliation-exact",
            resets_rehearsal_counter=False,
            simulation_clock=START,
        )


# --------------------------------------------------------------------------
# The superseded V2 loop
# --------------------------------------------------------------------------


def test_the_v2_constant_loop_now_delegates_and_says_so() -> None:
    """It set every day to passed, so its only possible outcome was success."""
    from wallet_twin_v2.operational_validation import thirty_day_shadow_rehearsal

    result = thirty_day_shadow_rehearsal()
    assert result["status"] == "SUPERSEDED_BY_V32_ACCELERATED_REHEARSAL"
    assert result["days"] == 47
    assert result["clean_days"] == 30
    assert result["counter_was_reset"] is True
    assert result["superseded_by"] == "wallet_twin_v32.rehearsal.rehearsal_report"


def test_the_v2_shim_still_refuses_the_production_gate() -> None:
    from wallet_twin_v2.operational_validation import thirty_day_shadow_rehearsal

    result = thirty_day_shadow_rehearsal()
    assert result["production_consecutive_shadow_days"] == 0
    assert result["production_gate_passed"] is False


def test_the_repository_clock_comes_from_an_actual_run() -> None:
    """A hardcoded clock state would report the same figures whether or not the
    rehearsal worked."""
    from wallet_twin_v32.repository import repository

    state = repository.clock()
    assert state.rehearsal_days_elapsed == 47
    assert state.consecutive_clean_rehearsal_days == 30
    assert state.elapsed_bank_shadow_days == 0
    assert state.incidents_injected == 1


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


def test_the_rehearsal_is_reproducible() -> None:
    assert rehearsal_report(as_of=AS_OF) == rehearsal_report(as_of=AS_OF)


def test_the_rehearsal_carries_no_wall_clock_stamp(report: dict) -> None:
    """Every timestamp derives from as_of, so the artifact is committable."""
    assert report["clock"]["simulation_clock"].startswith("2026-")
    for day in report["canonical_run"]["days"]:
        assert day["simulation_clock"].startswith("2026-")


def test_a_later_as_of_shifts_the_clock_but_not_the_counts() -> None:
    later = rehearsal_report(as_of=date(2026, 9, 30))
    assert later["shadow_rehearsal_days"] == 30
    assert later["elapsed_bank_shadow_days"] == 0
    assert later["clock"]["simulation_clock"] != report_clock()


def report_clock() -> str:
    return rehearsal_report(as_of=AS_OF)["clock"]["simulation_clock"]
