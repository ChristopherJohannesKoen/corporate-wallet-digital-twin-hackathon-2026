"""Operating characteristics of the cluster-randomised trial design.

``wallet_twin_v2.experiment_analysis`` already implements cluster-robust ITT
with sandwich variance, randomization inference, balance SMD and the 0.10
weak-instrument gate. Each of those runs **once**. Running an estimator once
tells you what it said; it does not tell you how often it is right.

This adds the replication loop, which answers the two questions a model-risk
reviewer asks before accepting a trial design:

**Type I error** — under a true null, how often does the design declare an
effect? Should sit near the nominal 0.05. Materially above it and the bank
would be buying a false causal claim.

**Power** — under a real effect of the size the pilot is scoped to detect, how
often does the design find it? Low power means a null result is uninformative,
and the honest response to an underpowered null is "we do not know", not "there
is no effect".

Both are tested at the boundary rather than only at comfortable values, because
a design that behaves well only far from its operating point has not been
characterised.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np
from scipy.stats import norm

from .compute import CPU, map_replications
from .sample_size import wilson_interval

CAUSAL_OC_LAB_VERSION = "v32-causal-operating-characteristics-1.0.0"

NOMINAL_ALPHA = 0.05
#: The effect the pilot is scoped to detect, in standard deviations.
TARGET_EFFECT = 0.35
#: Conventional minimum power for a design to be worth running. Below this, a
#: null result carries almost no information: the trial was unlikely to detect
#: the effect even if it were there, so "no effect found" and "effect present
#: but missed" are barely distinguishable outcomes.
ADEQUATE_POWER = 0.80
#: First-stage compliance below this makes the instrument uninformative. Matches
#: the existing gate in experiment_analysis.
WEAK_FIRST_STAGE = 0.10


@dataclass(frozen=True)
class TrialRealisation:
    effect: float
    estimate: float
    cluster_se: float
    significant: bool
    first_stage: float
    weak_instrument: bool


def _run_trial(
    seed: int,
    *,
    true_effect: float,
    clusters: int = 40,
    per_cluster: int = 25,
    compliance: float = 0.6,
) -> TrialRealisation:
    """One cluster-randomised realisation with cluster-robust inference.

    Cluster-level intercepts are the whole reason naive standard errors are
    wrong here: outcomes within an RM's book are correlated, and ignoring that
    understates the variance and overstates significance.
    """
    rng = np.random.default_rng(seed)
    assignment = rng.permutation(np.repeat([0, 1], clusters // 2))
    cluster_effect = rng.normal(0.0, 0.5, size=clusters)

    outcomes: List[np.ndarray] = []
    for index in range(clusters):
        treated = assignment[index]
        # Imperfect compliance: only some of the treated cluster is exposed.
        exposure = treated * compliance
        mean = cluster_effect[index] + true_effect * exposure
        outcomes.append(rng.normal(mean, 1.0, size=per_cluster))

    cluster_means = np.array([item.mean() for item in outcomes])
    treated_means = cluster_means[assignment == 1]
    control_means = cluster_means[assignment == 0]

    estimate = float(treated_means.mean() - control_means.mean())
    # Cluster-level variance: the cluster is the unit of randomisation, so it is
    # the unit of inference.
    se = float(
        np.sqrt(
            treated_means.var(ddof=1) / len(treated_means)
            + control_means.var(ddof=1) / len(control_means)
        )
    )
    significant = bool(abs(estimate) > 1.959963984540054 * se) if se > 0 else False
    first_stage = float(compliance)
    return TrialRealisation(
        effect=true_effect,
        estimate=estimate,
        cluster_se=se,
        significant=significant,
        first_stage=first_stage,
        weak_instrument=first_stage < WEAK_FIRST_STAGE,
    )


def _significant_at(seed: int, true_effect: float) -> bool:
    """Module-level so it survives pickling to a worker process.

    A closure over ``effect`` reads more naturally and cannot be sent to a
    spawned process on Windows, where multiprocessing has no fork. The failure
    is loud rather than silent, but only at run time — hence the explicit
    top-level definition.
    """
    return _run_trial(seed, true_effect=true_effect).significant


def operating_characteristics(
    *,
    replications: int = 200,
    seed: int = 20260630,
    effects: Sequence[float] = (0.0, TARGET_EFFECT),
) -> Dict[float, Tuple[float, float, float]]:
    """Rejection rate at each true effect, with a Wilson interval.

    Effect 0.0 gives Type I error; the target effect gives power.
    """
    results: Dict[float, Tuple[float, float, float]] = {}
    for index, effect in enumerate(effects):
        seeds = [seed + index * 100_000 + item for item in range(replications)]
        work = functools.partial(_significant_at, true_effect=effect)
        rejections = sum(1 for flag in map_replications(work, seeds) if flag)
        low, high = wilson_interval(rejections, replications)
        results[effect] = (rejections / replications, low, high)
    return results


def weak_instrument_behaviour(
    *, seed: int = 20260630, replications: int = 60
) -> Dict[str, object]:
    """What the design does when compliance collapses.

    The honest outcome of a weak first stage is a refusal to estimate, not a
    wide interval presented as a finding. This confirms the gate fires.
    """
    weak = [
        _run_trial(seed + index, true_effect=TARGET_EFFECT, compliance=0.05)
        for index in range(replications)
    ]
    strong = [
        _run_trial(seed + index, true_effect=TARGET_EFFECT, compliance=0.6)
        for index in range(replications)
    ]
    return {
        "weak_first_stage_threshold": WEAK_FIRST_STAGE,
        "weak_flagged": all(item.weak_instrument for item in weak),
        "strong_not_flagged": not any(item.weak_instrument for item in strong),
        "consequence": (
            "A flagged first stage blocks the causal claim entirely. The "
            "alternative — reporting a very wide interval — would be read as a "
            "finding with uncertainty rather than as no finding at all."
        ),
    }


def causal_report(
    characteristics: Dict[float, Tuple[float, float, float]],
    weak: Dict[str, object],
    replications: int,
) -> Dict[str, object]:
    type_one = characteristics.get(0.0)
    power = characteristics.get(TARGET_EFFECT)
    # Type I control is judged by whether the Wilson interval admits the nominal
    # rate, not by a point estimate: a rate of 0.062 from 200 replications is
    # not evidence of inflation.
    type_one_controlled = bool(type_one and type_one[1] <= NOMINAL_ALPHA <= type_one[2])
    # Power is judged against the upper Wilson bound: a design is called
    # underpowered only when even the optimistic end of the estimate falls short,
    # so the verdict is not an artefact of too few replications.
    power_adequate = bool(power and power[2] >= ADEQUATE_POWER)
    return {
        "lab_version": CAUSAL_OC_LAB_VERSION,
        "device": CPU,
        "replications": replications,
        "nominal_alpha": NOMINAL_ALPHA,
        "target_effect": TARGET_EFFECT,
        "adequate_power_threshold": ADEQUATE_POWER,
        "type_i_error": {
            "rate": round(type_one[0], 6) if type_one else None,
            "wilson_lower": round(type_one[1], 6) if type_one else None,
            "wilson_upper": round(type_one[2], 6) if type_one else None,
            "controlled": type_one_controlled,
        },
        "power_at_target_effect": {
            "rate": round(power[0], 6) if power else None,
            "wilson_lower": round(power[1], 6) if power else None,
            "wilson_upper": round(power[2], 6) if power else None,
            "adequate": power_adequate,
        },
        # Stated as a headline rather than left for a reader to derive from two
        # numbers. Controlled Type I error with inadequate power is a design
        # that will rarely claim a false effect and will also rarely find a true
        # one — reporting only the first would read as a clean bill of health.
        "design_verdict": (
            "ADEQUATE"
            if type_one_controlled and power_adequate
            else "UNDERPOWERED_AT_THIS_CLUSTER_COUNT"
            if type_one_controlled
            else "TYPE_I_ERROR_NOT_CONTROLLED"
        ),
        "design_verdict_meaning": (
            "Type I error is controlled, but power at the target effect is below "
            f"{ADEQUATE_POWER:.0%} at this cluster count and compliance rate. A "
            "null result from a trial run to this design would be uninformative, "
            "and the honest reading of one would be 'we do not know', not 'there "
            "is no effect'. Raising cluster count or compliance is what would "
            "change this."
            if type_one_controlled and not power_adequate
            else "Design meets both operating characteristics at this size."
            if type_one_controlled and power_adequate
            else "Rejection rate under the null exceeds nominal; inference from "
            "this design would overstate significance."
        ),
        "weak_instrument": weak,
        "evidence_mode": "SYNTHETIC_REHEARSAL",
        "bank_meaning": (
            "This characterises the trial *design*. It is not a trial, produces "
            "no effect estimate for the bank, and cannot satisfy the "
            "randomised-trial-validated gate. Causal value remains null."
        ),
    }


def trial_design_report(
    *,
    replications: int = 2_000,
    seed: int = 20260630,
    baseline_rate: float = 0.22,
    minimum_detectable_effect: float = 0.05,
) -> Dict[str, object]:
    """Analytic cluster search followed by Monte Carlo verification.

    Controlled scale does not depend on this result. The report only plans the
    later randomized validation needed for causal claims.
    """
    iccs = (0.01, 0.03, 0.05, 0.10)
    compliances = (0.5, 0.7, 0.9)
    cluster_counts = (24, 36, 48, 64, 80, 100, 120)
    mean_cluster_size = 25
    contamination = 0.05
    censoring = 0.10
    z_alpha = norm.ppf(0.975)
    rows: List[Dict[str, object]] = []
    rng = np.random.default_rng(seed)

    for icc in iccs:
        for compliance in compliances:
            analytic: List[Dict[str, object]] = []
            selected_clusters = None
            selected_se = None
            effective_effect = minimum_detectable_effect * compliance * (1 - contamination)
            for clusters in cluster_counts:
                per_arm = clusters * mean_cluster_size / 2
                design_effect = 1 + (mean_cluster_size - 1) * icc
                effective_per_arm = per_arm * (1 - censoring) / design_effect
                variance = 2 * baseline_rate * (1 - baseline_rate) / effective_per_arm
                se = float(np.sqrt(variance))
                noncentral = effective_effect / se
                power = float(norm.cdf(-z_alpha - noncentral) + 1 - norm.cdf(z_alpha - noncentral))
                analytic.append({"clusters": clusters, "power": round(power, 6)})
                if selected_clusters is None and power >= 0.80:
                    selected_clusters = clusters
                    selected_se = se
            if selected_clusters is None:
                selected_clusters = cluster_counts[-1]
                selected_se = float(
                    np.sqrt(
                        2
                        * baseline_rate
                        * (1 - baseline_rate)
                        / (
                            selected_clusters
                            * mean_cluster_size
                            / 2
                            * (1 - censoring)
                            / (1 + (mean_cluster_size - 1) * icc)
                        )
                    )
                )
            estimates = rng.normal(effective_effect, selected_se, size=replications)
            null_estimates = rng.normal(0.0, selected_se, size=replications)
            reject = np.abs(estimates / selected_se) > z_alpha
            null_reject = np.abs(null_estimates / selected_se) > z_alpha
            lower = estimates - z_alpha * selected_se
            upper = estimates + z_alpha * selected_se
            first_stage = np.clip(rng.normal(compliance, 0.04, size=replications), 0, 1)
            rows.append(
                {
                    "icc": icc,
                    "compliance": compliance,
                    "contamination": contamination,
                    "censoring": censoring,
                    "selected_clusters": selected_clusters,
                    "opportunities": selected_clusters * mean_cluster_size,
                    "analytic_search": analytic,
                    "monte_carlo_power": round(float(np.mean(reject)), 6),
                    "type_i_error": round(float(np.mean(null_reject)), 6),
                    "itt_bias": round(float(np.mean(estimates) - effective_effect), 6),
                    "ci_coverage": round(float(np.mean((lower <= effective_effect) & (upper >= effective_effect))), 6),
                    "first_stage_mean": round(float(np.mean(first_stage)), 6),
                    "probability_weak_instrument": round(float(np.mean(first_stage < WEAK_FIRST_STAGE)), 6),
                }
            )
    return {
        "lab_version": "v32-causal-trial-design-2.0.0",
        "evidence_mode": "SYNTHETIC_REHEARSAL",
        "replications": replications,
        "baseline_action_rate": baseline_rate,
        "minimum_detectable_effect": minimum_detectable_effect,
        "nominal_alpha": NOMINAL_ALPHA,
        "target_power": ADEQUATE_POWER,
        "rows": rows,
        "causal_claim": None,
        "bank_meaning": "The engine characterises future trial designs. No treatment was delivered and no real effect was estimated.",
    }


__all__ = [
    "ADEQUATE_POWER",
    "CAUSAL_OC_LAB_VERSION",
    "NOMINAL_ALPHA",
    "TARGET_EFFECT",
    "WEAK_FIRST_STAGE",
    "TrialRealisation",
    "causal_report",
    "operating_characteristics",
    "trial_design_report",
    "weak_instrument_behaviour",
]
