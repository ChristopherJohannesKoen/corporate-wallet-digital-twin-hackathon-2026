"""E3 sample-size planner: how many multibank-observed clients would be needed.

The bank's most consequential open question is what it would cost to make
competitor share *measurable* rather than merely bounded. This plans it: sweep
n from 20 to 150, estimate interval coverage at each, and report the smallest n
that reaches the target with acceptable precision.

**The important behaviour is the failure case.** If no tested n reaches the
target, the planner returns ``recommended_n = None`` with the determination
``NOT_DETERMINED_UP_TO_150``. It never returns the largest n tried. "150 was
not enough" and "150 is the recommendation" are opposite findings, and a
planner that renders them the same way would tell the bank to buy a data
contract that its own analysis says would not work.

Every estimate carries a Wilson score interval. A coverage estimate from 500
replications is itself uncertain, and a point estimate of 0.902 against a
target of 0.90 is not evidence of anything without knowing whether the interval
straddles it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Sequence, Tuple

import numpy as np

from wallet_twin_v2.canonical import artifact_timestamp

from ..contracts import NOT_DETERMINED_UP_TO_150, E3SampleSizePlan
from ..modes import PromotionEvidenceMode

SAMPLE_SIZE_LAB_VERSION = "v32-e3-sample-size-planner-1.0.0"

#: The sweep. Stops at 150 because beyond it the question stops being "how many
#: clients" and becomes "is this data contract viable at all", which is a
#: commercial decision rather than a statistical one.
DEFAULT_SAMPLE_SIZES: Tuple[int, ...] = (
    20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150,
)

#: z for a two-sided 95% Wilson interval.
WILSON_Z = 1.959963984540054


def wilson_interval(successes: int, trials: int, z: float = WILSON_Z) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Chosen over the normal approximation because coverage estimates sit near
    0.9, where the Wald interval is badly behaved and can even exceed 1.0 — an
    interval that reports impossible coverage would discredit the whole
    analysis.
    """
    if trials <= 0:
        raise ValueError("trials must be positive")
    phat = successes / trials
    denominator = 1.0 + z * z / trials
    centre = phat + z * z / (2 * trials)
    margin = z * math.sqrt(phat * (1 - phat) / trials + z * z / (4 * trials * trials))
    return (
        max(0.0, (centre - margin) / denominator),
        min(1.0, (centre + margin) / denominator),
    )


@dataclass(frozen=True)
class SampleSizePoint:
    """One n in the sweep."""

    n: int
    covered: int
    replications: int
    coverage: float
    wilson_lower: float
    wilson_upper: float
    half_width: float
    meets_target: bool

    def as_row(self) -> List[float]:
        return [float(self.n), self.wilson_lower, self.wilson_upper]


def _simulate_coverage_at_n(
    n: int,
    replications: int,
    *,
    target_coverage: float,
    seed: int,
) -> Tuple[int, float]:
    """Estimate interval coverage and mean half-width with n observed clients.

    The generative model is deliberately simple and stated rather than tuned: a
    Beta-Binomial share observed on n clients, with the posterior credible
    interval computed from the conjugate update. The point is the *relationship*
    between n and attainable precision, which this captures honestly; a more
    elaborate model would add parameters nobody has calibrated and would make
    the answer look more authoritative than the evidence supports.
    """
    rng = np.random.default_rng(seed)
    prior_a, prior_b = 2.0, 5.0
    tail = (1.0 - target_coverage) / 2.0

    truths = rng.beta(prior_a, prior_b, size=replications)
    successes = rng.binomial(n, truths)

    post_a = prior_a + successes
    post_b = prior_b + (n - successes)

    from scipy.stats import beta as beta_dist

    lower = beta_dist.ppf(tail, post_a, post_b)
    upper = beta_dist.ppf(1.0 - tail, post_a, post_b)

    covered = int(np.sum((truths >= lower) & (truths <= upper)))
    half_width = float(np.mean((upper - lower) / 2.0))
    return covered, half_width


def plan_e3_sample_size(
    *,
    as_of: date,
    target_coverage: float = 0.90,
    target_half_width: float = 0.05,
    sample_sizes: Sequence[int] = DEFAULT_SAMPLE_SIZES,
    replications: int = 500,
    seed: int = 20260630,
) -> Tuple[E3SampleSizePlan, List[SampleSizePoint]]:
    """Sweep n and report the smallest that meets both targets, or that none did.

    Two conditions must hold simultaneously: the Wilson interval for coverage
    must contain the target (the interval is calibrated) *and* the mean interval
    half-width must be at or below ``target_half_width`` (it is narrow enough to
    be useful). Calibration alone is insufficient — an interval spanning [0, 1]
    is perfectly calibrated and tells the bank nothing.
    """
    points: List[SampleSizePoint] = []
    for index, n in enumerate(sample_sizes):
        covered, half_width = _simulate_coverage_at_n(
            n,
            replications,
            target_coverage=target_coverage,
            # Vary the stream per n while staying reproducible.
            seed=seed + index * 1_000,
        )
        low, high = wilson_interval(covered, replications)
        calibrated = low <= target_coverage <= high
        precise = half_width <= target_half_width
        points.append(
            SampleSizePoint(
                n=n,
                covered=covered,
                replications=replications,
                coverage=covered / replications,
                wilson_lower=low,
                wilson_upper=high,
                half_width=half_width,
                meets_target=calibrated and precise,
            )
        )

    qualifying = [point for point in points if point.meets_target]
    if qualifying:
        recommended = min(point.n for point in qualifying)
        determination = f"TARGET_REACHED_AT_N_{recommended}"
    else:
        recommended = None
        determination = NOT_DETERMINED_UP_TO_150

    plan = E3SampleSizePlan(
        plan_id=f"e3-sample-size-{as_of.isoformat()}",
        as_of=as_of,
        target_coverage=target_coverage,
        target_half_width=target_half_width,
        tested_sample_sizes=list(sample_sizes),
        recommended_n=recommended,
        determination=determination,
        wilson_intervals=[point.as_row() for point in points],
        replications_per_n=replications,
        mode=PromotionEvidenceMode.SYNTHETIC_REHEARSAL,
        # The contract defaults this to wall-clock time, which is right for a
        # runtime record and wrong for a committed artifact: two identical runs
        # would differ, and the reproducibility gate would fail on a field that
        # says nothing about what the plan contains. artifact_timestamp() is the
        # same deterministic stamp every other committed artifact carries.
        generated_at=datetime.fromisoformat(artifact_timestamp()),
    )
    return plan, points


def plan_report(
    plan: E3SampleSizePlan, points: Sequence[SampleSizePoint]
) -> Dict[str, object]:
    """Publishable form, including the per-n detail behind the recommendation."""
    return {
        "lab_version": SAMPLE_SIZE_LAB_VERSION,
        "plan": plan.model_dump(mode="json"),
        "sweep": [
            {
                "n": point.n,
                "coverage": round(point.coverage, 6),
                "wilson_lower": round(point.wilson_lower, 6),
                "wilson_upper": round(point.wilson_upper, 6),
                "mean_half_width": round(point.half_width, 6),
                "meets_target": point.meets_target,
            }
            for point in points
        ],
        "criteria": {
            "calibrated": "Wilson interval for coverage contains the target",
            "precise": "mean posterior half-width <= target_half_width",
            "both_required": (
                "An interval spanning the whole unit range is perfectly "
                "calibrated and useless, so calibration alone cannot qualify an n."
            ),
        },
        "if_undetermined": (
            "recommended_n is null and determination is "
            f"{NOT_DETERMINED_UP_TO_150}. The largest n tried is deliberately "
            "not returned as a recommendation: it would tell the bank to buy a "
            "data contract this analysis says would not work."
        ),
        "evidence_mode": plan.mode.value,
        "bank_meaning": (
            "This plans what E3 acquisition would need to cost. It is not "
            "evidence that E3 exists, and it cannot satisfy the "
            "e3-multibank-observation-approved gate."
        ),
    }


__all__ = [
    "DEFAULT_SAMPLE_SIZES",
    "SAMPLE_SIZE_LAB_VERSION",
    "SampleSizePoint",
    "plan_e3_sample_size",
    "plan_report",
    "wilson_interval",
]
