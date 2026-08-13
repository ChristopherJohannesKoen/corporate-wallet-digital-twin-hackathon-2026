"""The seven simulation laboratories.

The tests that matter here are the ones about what a laboratory *cannot*
establish: that a simulated RM session can never satisfy the adoption gate,
that a sweep which failed to converge never returns a recommendation, and that
no laboratory output can support a real-track verdict.
"""

from __future__ import annotations

from datetime import date

import pytest

from wallet_twin_v32 import DecisionTrack, GateEvaluation, GateOutcome, PromotionEvidenceMode
from wallet_twin_v32.contracts import NOT_DETERMINED_UP_TO_150
from wallet_twin_v32.laboratories import (
    LABORATORY_VERSIONS,
    compute_report,
    evaluate_splits,
    gpu_available,
    map_replications,
    operating_characteristics,
    persona_report,
    plan_e3_sample_size,
    real_sessions,
    run_all,
    simulate_sessions,
    sweep_feasibility_injections,
    weak_instrument_behaviour,
    wilson_interval,
    worker_count,
)
from wallet_twin_v32.laboratories.causal_operating_characteristics import (
    ADEQUATE_POWER,
    NOMINAL_ALPHA,
    TARGET_EFFECT,
)
from wallet_twin_v32.laboratories.compute import CANONICAL_TIERS, NIGHTLY_TIERS
from wallet_twin_v32.laboratories.rm_personas import PERSONAS, REAL_PARTICIPANT, TASKS

AS_OF = date(2026, 6, 30)
SEED = 20260630


@pytest.fixture(scope="module")
def report() -> dict:
    return run_all(as_of=AS_OF, replications=120, seed=SEED)


# --------------------------------------------------------------------------
# There are seven, and each says what it does not establish
# --------------------------------------------------------------------------


def test_there_are_seven_laboratories(report: dict) -> None:
    assert len(LABORATORY_VERSIONS) == 7
    for name in LABORATORY_VERSIONS:
        assert name in report, name


def test_every_laboratory_states_what_it_does_not_establish(report: dict) -> None:
    """A number without its limits is how a rehearsal becomes evidence."""
    for name in ("calibration", "sample_size", "economics", "timing",
                 "causal_operating_characteristics"):
        assert "bank_meaning" in report[name], name
        assert len(report[name]["bank_meaning"]) > 60, name


def test_the_run_declares_the_four_open_gaps(report: dict) -> None:
    joined = " ".join(report["what_none_of_this_establishes"]).lower()
    for term in ("e3", "economics", "adoption", "causal", "synthetic_rehearsal"):
        assert term in joined


def test_all_laboratory_evidence_is_synthetic(report: dict) -> None:
    for name in ("calibration", "sample_size", "economics", "timing",
                 "causal_operating_characteristics"):
        block = report[name]
        mode = block.get("evidence_mode") or block["plan"]["mode"]
        assert mode == "SYNTHETIC_REHEARSAL", name


def test_no_laboratory_output_can_support_a_real_verdict() -> None:
    """The mode algebra refuses it; this proves the refusal reaches the labs."""
    with pytest.raises(Exception, match="synthetic evidence cannot support"):
        GateEvaluation(
            gate_id="interval-coverage-90",
            transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
            track=DecisionTrack.REAL,
            outcome=GateOutcome.PASS,
            evidence_mode=PromotionEvidenceMode.SYNTHETIC_REHEARSAL,
            evidence_ids=["ev-lab"],
        )


# --------------------------------------------------------------------------
# E3 sample-size planner: never manufacture a recommendation
# --------------------------------------------------------------------------


def test_the_sweep_reports_undetermined_rather_than_the_largest_n_tried(
    report: dict,
) -> None:
    """A real finding, not a contrived one: at 150 clients the posterior
    half-width is still above the 0.05 target, so the planner declines to
    recommend. Returning 150 would tell the bank to buy a data contract this
    analysis says would not work."""
    plan = report["sample_size"]["plan"]
    assert plan["determination"] == NOT_DETERMINED_UP_TO_150
    assert plan["recommended_n"] is None
    assert 150 in plan["tested_sample_sizes"]


def test_a_reachable_target_does_produce_a_recommendation() -> None:
    """The positive case, so the sentinel is not simply always returned."""
    plan, points = plan_e3_sample_size(
        as_of=AS_OF, target_half_width=0.25, replications=200, seed=SEED
    )
    assert plan.recommended_n is not None
    assert plan.determination != NOT_DETERMINED_UP_TO_150
    assert plan.recommended_n in plan.tested_sample_sizes
    assert any(point.meets_target for point in points)


def test_the_recommendation_is_the_smallest_qualifying_n() -> None:
    plan, points = plan_e3_sample_size(
        as_of=AS_OF, target_half_width=0.25, replications=200, seed=SEED
    )
    qualifying = [point.n for point in points if point.meets_target]
    assert plan.recommended_n == min(qualifying)


def test_calibration_alone_does_not_qualify_a_sample_size() -> None:
    """An interval spanning the unit range is perfectly calibrated and useless."""
    plan, points = plan_e3_sample_size(
        as_of=AS_OF, target_half_width=0.0001, replications=200, seed=SEED
    )
    assert plan.recommended_n is None
    assert not any(point.meets_target for point in points)


def test_every_swept_point_carries_a_wilson_interval(report: dict) -> None:
    for row in report["sample_size"]["sweep"]:
        assert row["wilson_lower"] <= row["coverage"] <= row["wilson_upper"]


def test_wilson_intervals_stay_inside_the_unit_range() -> None:
    """Why Wilson and not Wald: the normal approximation can exceed 1.0 near
    the boundary, and an interval reporting impossible coverage would discredit
    the analysis it appears in."""
    for successes, trials in ((0, 50), (50, 50), (49, 50), (1, 500)):
        low, high = wilson_interval(successes, trials)
        assert 0.0 <= low <= high <= 1.0


def test_wilson_rejects_a_nonpositive_trial_count() -> None:
    with pytest.raises(ValueError, match="trials must be positive"):
        wilson_interval(0, 0)


# --------------------------------------------------------------------------
# RM personas: a simulation can never satisfy the adoption gate
# --------------------------------------------------------------------------


def test_every_simulated_session_is_marked_not_real() -> None:
    sessions = simulate_sessions(as_of=AS_OF, seed=SEED)
    assert sessions
    assert all(item.real_participant is False for item in sessions)


def test_real_participant_is_not_settable_from_outside() -> None:
    """A parameter that could be flipped to True is one that eventually is."""
    sessions = simulate_sessions(as_of=AS_OF, seed=SEED)
    with pytest.raises(TypeError):
        type(sessions[0])(
            session_id="x",
            persona_id="y",
            task_id="z",
            started_at=sessions[0].started_at,
            steps_taken=1,
            completed=True,
            opened_evidence=True,
            abandoned=False,
            real_participant=True,
        )
    assert REAL_PARTICIPANT is False


def test_no_simulated_session_counts_toward_adoption(report: dict) -> None:
    sessions = simulate_sessions(as_of=AS_OF, seed=SEED)
    assert real_sessions(sessions) == []
    assert report["rm_personas"]["real_participant_sessions"] == 0
    assert (
        report["rm_personas"]["adoption_gate_effect"][
            "counts_toward_supervised_pilot_gate"
        ]
        is False
    )


def test_the_persona_lab_covers_five_personas_and_eight_tasks() -> None:
    assert len(PERSONAS) == 5
    assert len(TASKS) == 8
    sessions = simulate_sessions(as_of=AS_OF, repetitions=3, seed=SEED)
    assert len(sessions) == 5 * 8 * 3


def test_the_persona_report_surfaces_friction_not_only_success() -> None:
    """A simulator that only counted completions would say the interface works
    everywhere, which is never true."""
    result = persona_report(simulate_sessions(as_of=AS_OF, seed=SEED))
    assert result["highest_friction_task"]["step_overhead"] > 0
    assert any(
        row["abandonment_rate"] > 0 for row in result["by_persona"].values()
    )


def test_personas_differ_in_how_they_use_the_workbench() -> None:
    result = persona_report(simulate_sessions(as_of=AS_OF, seed=SEED))
    rates = [row["evidence_open_rate"] for row in result["by_persona"].values()]
    assert max(rates) - min(rates) > 0.3, "personas are not meaningfully distinct"


# --------------------------------------------------------------------------
# Calibration at three nominal levels
# --------------------------------------------------------------------------


def test_coverage_is_audited_at_fifty_eighty_and_ninety(report: dict) -> None:
    """The V2 laboratory could only report 90% because wallet_model._interval
    hardcoded the 5th/50th/95th quantiles."""
    assert tuple(report["calibration"]["nominal_levels"]) == (0.50, 0.80, 0.90)
    assert len(report["calibration"]["results"]) == 3


def test_the_interval_helper_is_now_parameterised() -> None:
    import numpy as np

    from wallet_twin_v2.contracts import ClaimClass
    from wallet_twin_v2.wallet_model import _interval

    values = np.linspace(0.0, 1.0, 1001)
    narrow = _interval(values, AS_OF, "v", ClaimClass.POSTERIOR, nominal_coverage=0.50)
    wide = _interval(values, AS_OF, "v", ClaimClass.POSTERIOR, nominal_coverage=0.90)
    assert (narrow.upper - narrow.lower) < (wide.upper - wide.lower)
    assert narrow.nominal_coverage == 0.50


def test_the_interval_helper_still_defaults_to_ninety_percent() -> None:
    """Every committed artifact uses 0.90, so the default must not have moved."""
    import numpy as np

    from wallet_twin_v2.contracts import ClaimClass
    from wallet_twin_v2.wallet_model import _interval

    values = np.linspace(0.0, 1.0, 1001)
    assert _interval(values, AS_OF, "v", ClaimClass.POSTERIOR).nominal_coverage == 0.90


def test_an_impossible_nominal_coverage_is_refused() -> None:
    import numpy as np

    from wallet_twin_v2.contracts import ClaimClass
    from wallet_twin_v2.wallet_model import _interval

    for bad in (0.0, 1.0, -0.5, 1.5):
        with pytest.raises(ValueError, match="must lie in"):
            _interval(
                np.array([0.1, 0.5]), AS_OF, "v", ClaimClass.POSTERIOR,
                nominal_coverage=bad,
            )


def test_calibration_uses_the_previously_dead_coverage_helper() -> None:
    """empirical_interval_coverage was defined in V2 and never called."""
    import numpy as np

    from wallet_twin_v2.wallet_model import empirical_interval_coverage

    truth = np.array([0.2, 0.5, 0.9])
    assert empirical_interval_coverage(
        truth, np.array([0.0, 0.0, 0.0]), np.array([1.0, 1.0, 1.0])
    ) == 1.0
    assert empirical_interval_coverage(
        truth, np.array([0.3, 0.0, 0.0]), np.array([1.0, 1.0, 0.5])
    ) == pytest.approx(1 / 3)


def test_mismatched_coverage_arrays_are_refused() -> None:
    import numpy as np

    from wallet_twin_v2.wallet_model import empirical_interval_coverage

    with pytest.raises(ValueError, match="identical shapes"):
        empirical_interval_coverage(
            np.array([0.1]), np.array([0.0, 0.0]), np.array([1.0, 1.0])
        )


# --------------------------------------------------------------------------
# Causal operating characteristics
# --------------------------------------------------------------------------


def test_type_one_error_is_controlled_at_the_nominal_rate(report: dict) -> None:
    block = report["causal_operating_characteristics"]["type_i_error"]
    assert block["controlled"] is True
    assert block["wilson_lower"] <= NOMINAL_ALPHA <= block["wilson_upper"]


def test_the_design_is_reported_underpowered_rather_than_merely_valid(
    report: dict,
) -> None:
    """The finding this laboratory actually produced. Reporting controlled Type
    I error alone would read as a clean bill of health for a design that would
    rarely detect the effect it is scoped to find."""
    block = report["causal_operating_characteristics"]
    assert block["power_at_target_effect"]["adequate"] is False
    assert block["design_verdict"] == "UNDERPOWERED_AT_THIS_CLUSTER_COUNT"
    assert "we do not know" in block["design_verdict_meaning"]


def test_power_rises_with_a_larger_effect() -> None:
    """Confirms the design responds to effect size at all — without this, low
    power could equally be a broken estimator."""
    characteristics = operating_characteristics(
        replications=120, seed=SEED, effects=(0.0, TARGET_EFFECT, 1.2)
    )
    assert characteristics[1.2][0] > characteristics[TARGET_EFFECT][0]
    assert characteristics[TARGET_EFFECT][0] > characteristics[0.0][0]


def test_a_weak_first_stage_is_flagged_and_a_strong_one_is_not() -> None:
    result = weak_instrument_behaviour(seed=SEED, replications=40)
    assert result["weak_flagged"] is True
    assert result["strong_not_flagged"] is True


def test_the_causal_lab_cannot_satisfy_the_trial_gate(report: dict) -> None:
    meaning = report["causal_operating_characteristics"]["bank_meaning"]
    assert "not a trial" in meaning
    assert "causal value remains null" in meaning.lower()


def test_adequate_power_threshold_is_the_conventional_eighty_percent() -> None:
    assert ADEQUATE_POWER == 0.80


# --------------------------------------------------------------------------
# Economics
# --------------------------------------------------------------------------


def test_economics_reconciles_component_by_component(report: dict) -> None:
    block = report["economics"]
    assert block["reconciles_exactly"] is True
    assert len(block["components"]) == 5
    for component in block["components"].values():
        assert component["reconciles"] is True
        assert component["owner_role"]


def test_each_economic_component_names_an_accountable_function(report: dict) -> None:
    """An aggregate check cannot say whose number moved."""
    owners = {row["owner_role"] for row in report["economics"]["components"].values()}
    assert owners >= {"PRODUCT_FINANCE", "TREASURY", "RISK"}


def test_the_latin_hypercube_fills_every_stratum() -> None:
    """The property that makes LHS worth using at small sample sizes."""
    import numpy as np

    from wallet_twin_v32.laboratories.economics import COMPONENTS, latin_hypercube

    samples = 64
    design = latin_hypercube(COMPONENTS, samples, SEED)
    assert design.shape == (samples, len(COMPONENTS))
    for index, component in enumerate(COMPONENTS):
        scaled = (design[:, index] - component.low) / (component.high - component.low)
        counts = np.histogram(scaled, bins=samples, range=(0.0, 1.0))[0]
        assert counts.min() == 1, f"{component.component_id} left a stratum empty"


def test_economics_declares_its_parameters_are_not_bank_approved(report: dict) -> None:
    assert "not bank-approved" in report["economics"]["bank_meaning"]


def test_the_sensitivity_ranking_is_ordered(report: dict) -> None:
    swings = [row["swing"] for row in report["economics"]["sensitivity_rank"]]
    assert swings == sorted(swings, reverse=True)


# --------------------------------------------------------------------------
# Timing
# --------------------------------------------------------------------------


def test_the_governed_split_holds_out_clients_and_time(report: dict) -> None:
    assert report["timing"]["governed_split"] == "client-held-out-temporal"
    assert len(report["timing"]["splits"]) == 3


def test_a_random_split_looks_better_than_it_is(report: dict) -> None:
    """Quantifies the leakage rather than merely asserting it exists."""
    assert report["timing"]["optimism_of_a_random_split_months"] > 0


def test_a_temporal_split_alone_is_still_optimistic() -> None:
    splits = {item.split: item for item in evaluate_splits(seed=SEED)}
    assert splits["temporal-only"].mae_months <= splits["client-held-out-temporal"].mae_months
    assert "memorisation" in splits["temporal-only"].description


# --------------------------------------------------------------------------
# Feasibility injection
# --------------------------------------------------------------------------


def test_every_feasibility_gate_bites_when_failed(report: dict) -> None:
    assert report["feasibility_sweep"]["all_gates_bite"] is True
    assert report["feasibility_sweep"]["deviations"] == []


def test_failure_blocks_selection_and_unknown_yields_discovery_only() -> None:
    """Two different outcomes. Conflating them would either recommend something
    unexecutable or refuse something merely unexamined."""
    results = sweep_feasibility_injections()
    failed = [item for item in results if item.injected_status == "FAIL"]
    unknown = [item for item in results if item.injected_status == "UNKNOWN"]
    passed = [item for item in results if item.injected_status == "PASS"]

    assert failed and unknown and passed
    assert all(not item.selectable and not item.discovery_only for item in failed)
    assert all(not item.selectable and item.discovery_only for item in unknown)
    assert all(item.selectable and not item.discovery_only for item in passed)


def test_each_gate_is_injected_individually() -> None:
    """Injecting several at once still gives the right answer while leaving it
    unclear which gate produced it."""
    from wallet_twin_v31.taxonomy import FEASIBILITY_GATES

    results = sweep_feasibility_injections()
    assert len(results) == len(FEASIBILITY_GATES) * 3
    assert len({item.gate for item in results}) == len(FEASIBILITY_GATES)


# --------------------------------------------------------------------------
# Compute policy
# --------------------------------------------------------------------------


def test_no_canonical_tier_runs_on_the_gpu() -> None:
    """A GPU-produced canonical artifact would fail the byte-reproducibility
    gate on a CPU-only CI runner."""
    assert all(tier.device == "cpu" for tier in CANONICAL_TIERS)
    assert all(tier.committed for tier in CANONICAL_TIERS)


def test_no_nightly_tier_is_committed() -> None:
    assert all(not tier.committed for tier in NIGHTLY_TIERS)


def test_the_gpu_is_reported_absent_rather_than_worked_around() -> None:
    available, reason = gpu_available()
    assert available is False
    assert reason == "CUPY_NOT_INSTALLED"
    block = compute_report()
    assert block["gpu_available"] is False
    assert all(tier["status"] == "NOT_EXECUTED" for tier in block["nightly_tiers"])


def test_parallel_replication_preserves_seed_order() -> None:
    """What keeps a parallel run byte-identical to a serial one. Without it,
    parallelism becomes a source of non-determinism in a byte-gated artifact."""
    seeds = list(range(64))
    assert map_replications(_double, seeds) == [value * 2 for value in seeds]


def test_worker_count_leaves_headroom_and_never_falls_below_one() -> None:
    assert worker_count() >= 1
    assert worker_count(1) == 1
    import os

    assert worker_count() <= (os.cpu_count() or 2)


def test_the_compute_report_states_why_the_split_exists() -> None:
    policy = compute_report()["policy"]
    assert "byte-gated" in policy
    assert "No committed number depends on the GPU path." in policy


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


def test_the_full_run_is_reproducible() -> None:
    """Byte-stability is what lets these artifacts be committed at all."""
    first = run_all(as_of=AS_OF, replications=60, seed=SEED)
    second = run_all(as_of=AS_OF, replications=60, seed=SEED)
    assert first == second


def test_the_sample_size_plan_carries_no_wall_clock_stamp() -> None:
    """E3SampleSizePlan defaults generated_at to wall-clock time, which is right
    for a runtime record and wrong for a committed artifact: two identical runs
    would differ on a field that says nothing about what the plan contains."""
    from wallet_twin_v2.canonical import artifact_timestamp

    plan, _ = plan_e3_sample_size(as_of=AS_OF, replications=60, seed=SEED)
    assert plan.generated_at.isoformat() == artifact_timestamp()


def test_a_different_seed_changes_the_result() -> None:
    """Guards against a run that is reproducible because it ignores its seed.

    Compared on the timing panel, whose MAE is continuous. Discrete rejection
    counts can coincide across seeds at small replication counts, which would
    make this test flaky for a reason unrelated to what it checks.
    """
    first = run_all(as_of=AS_OF, replications=60, seed=SEED)
    second = run_all(as_of=AS_OF, replications=60, seed=SEED + 1)
    assert first["timing"]["governed_mae_months"] != second["timing"]["governed_mae_months"]
    assert first["calibration"]["results"] != second["calibration"]["results"]


def _double(value: int) -> int:
    """Module-level so it can be pickled to a worker process."""
    return value * 2
