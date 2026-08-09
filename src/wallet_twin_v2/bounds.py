from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from .contracts import ClaimClass, IntervalEstimate


@dataclass(frozen=True)
class BoundEvidence:
    lower: Optional[float] = None
    upper: Optional[float] = None
    capacity: Optional[float] = None
    minimum_share: Optional[float] = None
    basis: str = "observed activity lower bound"


class DeterministicBoundsEngine:
    """Computes an identified set without using posterior probability draws."""

    version = "bounds-2.0.0"

    def calculate(
        self,
        observed_activity: float,
        as_of: date,
        evidence: BoundEvidence,
    ) -> IntervalEstimate:
        if observed_activity < 0:
            raise ValueError("observed_activity must be non-negative")

        lower = max(observed_activity, evidence.lower or 0.0)
        upper_candidates = [value for value in (evidence.upper, evidence.capacity) if value is not None]
        if upper_candidates:
            upper = min(upper_candidates)
        elif evidence.minimum_share is not None:
            if not 0 < evidence.minimum_share <= 1:
                raise ValueError("minimum_share must be in (0, 1]")
            upper = observed_activity / evidence.minimum_share if observed_activity else 0.0
        else:
            upper = lower
        upper = max(lower, upper)
        median = lower + (upper - lower) / 2.0
        return IntervalEstimate(
            lower=lower,
            median=median,
            upper=upper,
            nominal_coverage=0.999,
            model_version=self.version,
            as_of=as_of,
            claim_class=ClaimClass.IDENTIFIED_BOUND,
        )
