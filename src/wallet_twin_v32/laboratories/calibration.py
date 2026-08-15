"""Multi-level interval calibration audit.

``wallet_twin_v2.offline_lab`` already audits 90% coverage. This adds 50% and
80%, which the V2 model could not report because ``wallet_model._interval``
hardcoded the 5th/50th/95th quantiles.

The addition matters more than it sounds. A model can be well calibrated at 90%
and badly calibrated in the middle of its distribution — the tails are wide
enough to absorb error that a central interval exposes. Auditing one nominal
level cannot distinguish "calibrated" from "calibrated where we happened to
look", and the 90% interval is precisely the one a banker is least likely to
act on: they act on the median.

``empirical_interval_coverage`` in ``wallet_model`` was defined and never
called. It is called here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Sequence, Tuple

import numpy as np

from wallet_twin_v2.wallet_model import empirical_interval_coverage

from .compute import CPU, map_replications
from .sample_size import wilson_interval

CALIBRATION_LAB_VERSION = "v32-multi-level-calibration-1.0.0"

#: The nominal levels audited. 0.50 and 0.80 are the additions; 0.90 is retained
#: so the V3.2 result can be compared against the V2 figure directly.
NOMINAL_LEVELS: Tuple[float, ...] = (0.50, 0.80, 0.90)

#: Acceptable absolute deviation from nominal. Matches the existing
#: interval-coverage-90 gate band of 0.85-0.95 at the 90% level.
COVERAGE_TOLERANCE = 0.05


@dataclass(frozen=True)
class CoverageResult:
    nominal: float
    empirical: float
    wilson_lower: float
    wilson_upper: float
    entities: int
    within_tolerance: bool

    @property
    def deviation(self) -> float:
        return self.empirical - self.nominal


def _realisation(seed: int) -> Tuple[np.ndarray, np.ndarray]:
    """One synthetic panel: truths and posterior draws.

    Kept deliberately simple and declared rather than tuned — a Beta truth with
    a conjugate posterior. The audit is of the *interval construction*, not of
    the wallet model's domain assumptions, which V2's laboratory already covers.
    """
    rng = np.random.default_rng(seed)
    entities = 120
    truths = rng.beta(2.0, 5.0, size=entities)
    observations = rng.binomial(40, truths)
    post_a = 2.0 + observations
    post_b = 5.0 + (40 - observations)
    draws = rng.beta(
        post_a[:, None] * np.ones((1, 400)),
        post_b[:, None] * np.ones((1, 400)),
    )
    return truths, draws


def audit_coverage(
    *,
    as_of: date,
    replications: int = 240,
    seed: int = 20260630,
    levels: Sequence[float] = NOMINAL_LEVELS,
) -> List[CoverageResult]:
    """Empirical coverage at each nominal level.

    Replications run through ``map_replications``, which parallelises across
    cores while returning results in seed order — so the parallel result is
    byte-identical to the serial one.
    """
    seeds = [seed + index for index in range(replications)]
    realisations = map_replications(_realisation, seeds)

    truths = np.concatenate([item[0] for item in realisations])
    draws = np.concatenate([item[1] for item in realisations])

    results: List[CoverageResult] = []
    for nominal in levels:
        tail = (1.0 - nominal) / 2.0
        lower = np.quantile(draws, tail, axis=1)
        upper = np.quantile(draws, 1.0 - tail, axis=1)
        empirical = empirical_interval_coverage(truths, lower, upper)
        covered = int(round(empirical * len(truths)))
        low, high = wilson_interval(covered, len(truths))
        results.append(
            CoverageResult(
                nominal=nominal,
                empirical=empirical,
                wilson_lower=low,
                wilson_upper=high,
                entities=len(truths),
                within_tolerance=abs(empirical - nominal) <= COVERAGE_TOLERANCE,
            )
        )
    return results


def calibration_report(results: Sequence[CoverageResult]) -> Dict[str, object]:
    failing = [item for item in results if not item.within_tolerance]
    return {
        "lab_version": CALIBRATION_LAB_VERSION,
        "device": CPU,
        "nominal_levels": list(NOMINAL_LEVELS),
        "tolerance": COVERAGE_TOLERANCE,
        "results": [
            {
                "nominal": item.nominal,
                "empirical": round(item.empirical, 6),
                "deviation": round(item.deviation, 6),
                "wilson_lower": round(item.wilson_lower, 6),
                "wilson_upper": round(item.wilson_upper, 6),
                "entities": item.entities,
                "within_tolerance": item.within_tolerance,
            }
            for item in results
        ],
        "all_levels_calibrated": not failing,
        "levels_outside_tolerance": [item.nominal for item in failing],
        "why_multiple_levels": (
            "A model can be calibrated at 90% and miscalibrated at 50%, because "
            "wide tails absorb error a central interval exposes. The 90% band is "
            "also the one a banker is least likely to act on — they act on the "
            "median."
        ),
        "evidence_mode": "SYNTHETIC_REHEARSAL",
        "bank_meaning": (
            "Coverage measured on synthetic outcomes. The interval-coverage-90 "
            "gate requires the same measurement on held-out real bank outcomes "
            "and is unaffected by this result."
        ),
    }


__all__ = [
    "CALIBRATION_LAB_VERSION",
    "COVERAGE_TOLERANCE",
    "NOMINAL_LEVELS",
    "CoverageResult",
    "audit_coverage",
    "calibration_report",
]
