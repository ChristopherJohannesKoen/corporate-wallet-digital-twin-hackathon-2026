"""Robust Pareto dominance over common scenario draws.

The legacy V3 ``decision_score`` is deliberately *not* used for V3.1 selection.
A single weighted score decides trade-offs on the banker's behalf and hides
them; a frontier shows which conversations are genuinely non-dominated and
which are only winning because of one weight choice.

Action A robustly dominates B when, in at least 80% of shared scenario draws, A
is no worse on client value, bank value, need and timing, and no worse on risk
and friction, with at least one strict improvement.  Draws are common across
candidates so the comparison is paired, not independent.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .contracts import ParetoStatus

PARETO_POLICY_VERSION = "v31-robust-dominance-3.1.1"
DEFAULT_DRAWS = 512
DOMINANCE_THRESHOLD = 0.80

#: Objectives where more is better.
BENEFIT_AXES = (
    "need",
    "client_value",
    "bank_value",
    "timing",
    "relationship_value",
    "strategic_value",
)
#: Objectives where less is better.
COST_AXES = ("risk", "friction")


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16) % (2**32)


@dataclass(frozen=True)
class CandidateAxes:
    """A candidate's point estimate on every decision axis, in 0-1 units."""

    candidate_id: str
    entity_id: str
    problem_id: str
    need: float
    client_value: float
    bank_value: float
    timing: float
    relationship_value: float
    strategic_value: float
    risk: float
    friction: float
    feasibility: float
    #: Dispersion applied when sampling; wider intervals get wider draws so an
    #: uncertain candidate cannot dominate a well-evidenced one by luck.
    dispersion: float = 0.25


class ScenarioSampler:
    """Generates common random draws shared by every candidate."""

    def __init__(self, draws: int = DEFAULT_DRAWS, salt: str = "v31-pareto") -> None:
        self.draws = draws
        self.salt = salt

    def sample(self, candidates: Sequence[CandidateAxes]) -> Dict[str, Dict[str, np.ndarray]]:
        # One shared uniform stream per axis keeps the comparison paired: the
        # same "state of the world" is applied to every candidate.
        rng = np.random.default_rng(_seed(self.salt))
        shared = {
            axis: rng.normal(0.0, 1.0, size=self.draws)
            for axis in BENEFIT_AXES + COST_AXES
        }
        result: Dict[str, Dict[str, np.ndarray]] = {}
        for candidate in candidates:
            local = np.random.default_rng(_seed(f"{self.salt}:{candidate.candidate_id}"))
            idiosyncratic = {
                axis: local.normal(0.0, 1.0, size=self.draws)
                for axis in BENEFIT_AXES + COST_AXES
            }
            draws: Dict[str, np.ndarray] = {}
            for axis in BENEFIT_AXES + COST_AXES:
                centre = float(getattr(candidate, axis))
                # 70% common factor, 30% idiosyncratic: candidates move together
                # with the macro scenario but retain their own uncertainty.
                shock = 0.7 * shared[axis] + 0.3 * idiosyncratic[axis]
                values = centre * np.exp(
                    candidate.dispersion * shock - 0.5 * candidate.dispersion**2
                )
                draws[axis] = np.clip(values, 0.0, 1.0)
            result[candidate.candidate_id] = draws
        return result


def robust_dominates(
    a: Dict[str, np.ndarray],
    b: Dict[str, np.ndarray],
    *,
    threshold: float = DOMINANCE_THRESHOLD,
) -> Tuple[bool, float]:
    """True when A robustly dominates B, plus the share of draws where it does."""
    core = ("client_value", "bank_value", "need", "timing")
    no_worse = np.ones_like(a["need"], dtype=bool)
    for axis in core:
        no_worse &= a[axis] >= b[axis] - 1e-9
    for axis in COST_AXES:
        no_worse &= a[axis] <= b[axis] + 1e-9
    strictly_better = np.zeros_like(no_worse, dtype=bool)
    for axis in core:
        strictly_better |= a[axis] > b[axis] + 1e-9
    for axis in COST_AXES:
        strictly_better |= a[axis] < b[axis] - 1e-9
    share = float(np.mean(no_worse & strictly_better))
    return share >= threshold, share


class ParetoEngine:
    version = PARETO_POLICY_VERSION

    def __init__(
        self, draws: int = DEFAULT_DRAWS, threshold: float = DOMINANCE_THRESHOLD
    ) -> None:
        self.draws = draws
        self.threshold = threshold
        self.sampler = ScenarioSampler(draws)

    def evaluate(
        self, candidates: Sequence[CandidateAxes]
    ) -> Tuple[Dict[str, ParetoStatus], Dict[str, Dict[str, np.ndarray]]]:
        if not candidates:
            return {}, {}
        draws = self.sampler.sample(candidates)
        by_client: Dict[str, List[CandidateAxes]] = {}
        for candidate in candidates:
            by_client.setdefault(candidate.entity_id, []).append(candidate)

        client_frontier: Dict[str, bool] = {}
        client_probability: Dict[str, float] = {}
        dominated_by: Dict[str, List[str]] = {}

        # Client frontier: eliminate inferior bundles for the same client and problem.
        for entity_id, group in by_client.items():
            for candidate in group:
                worst_share = 0.0
                dominators: List[str] = []
                for other in group:
                    if other.candidate_id == candidate.candidate_id:
                        continue
                    if other.problem_id != candidate.problem_id:
                        continue
                    dominates, share = robust_dominates(
                        draws[other.candidate_id],
                        draws[candidate.candidate_id],
                        threshold=self.threshold,
                    )
                    if dominates:
                        dominators.append(other.candidate_id)
                    worst_share = max(worst_share, share)
                client_frontier[candidate.candidate_id] = not dominators
                client_probability[candidate.candidate_id] = 1.0 - worst_share
                dominated_by[candidate.candidate_id] = sorted(dominators)

        # Portfolio frontier: non-dominated across the whole RM portfolio.
        portfolio_frontier: Dict[str, bool] = {}
        portfolio_probability: Dict[str, float] = {}
        for candidate in candidates:
            worst_share = 0.0
            dominated = False
            for other in candidates:
                if other.candidate_id == candidate.candidate_id:
                    continue
                dominates, share = robust_dominates(
                    draws[other.candidate_id],
                    draws[candidate.candidate_id],
                    threshold=self.threshold,
                )
                dominated = dominated or dominates
                worst_share = max(worst_share, share)
            portfolio_frontier[candidate.candidate_id] = not dominated
            portfolio_probability[candidate.candidate_id] = 1.0 - worst_share

        statuses = {
            candidate.candidate_id: ParetoStatus(
                client_frontier_member=client_frontier[candidate.candidate_id],
                portfolio_frontier_member=portfolio_frontier[candidate.candidate_id],
                client_frontier_probability=round(
                    client_probability[candidate.candidate_id], 6
                ),
                portfolio_frontier_probability=round(
                    portfolio_probability[candidate.candidate_id], 6
                ),
                dominated_by=dominated_by.get(candidate.candidate_id, []),
                dominance_threshold=self.threshold,
                scenario_draws=self.draws,
                policy_version=PARETO_POLICY_VERSION,
            )
            for candidate in candidates
        }
        return statuses, draws
