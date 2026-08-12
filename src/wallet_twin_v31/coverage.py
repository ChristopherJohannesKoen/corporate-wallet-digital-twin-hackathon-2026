"""Weekly coverage optimization under a mixed-integer CVaR objective.

The banker has capacity for eight conversations a week.  The optimizer chooses
which eight, maximising

    0.45 * E[AdjustedBenefit] + 0.55 * CVaR_10%(AdjustedBenefit)

subject to concentration, exclusivity and feasibility constraints.  The heavy
CVaR weight is the point: a plan that looks good on average but collapses in
the worst 10% of scenarios is not a plan a banker should be handed.

CVaR is linearised in the standard Rockafellar-Uryasev form, so the problem is
a genuine MILP solved by ``scipy.optimize.milp`` (HiGHS).  If the solver fails
or is unavailable the greedy fallback runs and the plan is labelled
``DEGRADED_FALLBACK`` — never silently substituted.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .taxonomy import BankingSolution, SolutionFamily, mutually_exclusive

COVERAGE_POLICY_VERSION = "v31-coverage-cvar-3.1.0"
WEIGHTS_VERSION = "v31-policy-weights-3.1.0"

#: Governed benefit weights.  They sum to one and are versioned; changing them
#: is a policy change that must be re-approved, not a tuning exercise.
BENEFIT_WEIGHTS: Mapping[str, float] = {
    "need": 0.25,
    "client_value": 0.20,
    "bank_value": 0.20,
    "timing": 0.15,
    "relationship_value": 0.10,
    "strategic_value": 0.10,
}
RISK_PENALTY = 0.50
FRICTION_PENALTY = 0.35
EXPECTATION_WEIGHT = 0.45
CVAR_WEIGHT = 0.55
CVAR_ALPHA = 0.10

DEFAULT_CONSTRAINTS: Mapping[str, int] = {
    "capacity": 8,
    "max_per_client": 2,
    "max_per_client_role": 1,
    "max_per_solution_family": 3,
    "max_per_sector": 3,
}

if abs(sum(BENEFIT_WEIGHTS.values()) - 1.0) > 1e-9:
    raise RuntimeError("governed benefit weights must sum to one")


@dataclass(frozen=True)
class CoverageCandidate:
    candidate_id: str
    entity_id: str
    sector: str
    stakeholder_role: str
    family: SolutionFamily
    solutions: Tuple[BankingSolution, ...]
    feasibility: float
    risk: float
    friction: float
    blocked: bool
    discovery_only: bool


def benefit_draws(axis_draws: Mapping[str, np.ndarray]) -> np.ndarray:
    total = np.zeros_like(next(iter(axis_draws.values())))
    for axis, weight in BENEFIT_WEIGHTS.items():
        total = total + weight * axis_draws[axis]
    return total


def adjusted_benefit_draws(
    axis_draws: Mapping[str, np.ndarray], candidate: CoverageCandidate
) -> np.ndarray:
    benefit = benefit_draws(axis_draws)
    return (
        benefit
        * candidate.feasibility
        * (1.0 - RISK_PENALTY * axis_draws["risk"])
        * (1.0 - FRICTION_PENALTY * axis_draws["friction"])
    )


def cvar(values: np.ndarray, alpha: float = CVAR_ALPHA) -> float:
    tail = max(1, int(round(len(values) * alpha)))
    return float(np.sort(values)[:tail].mean())


class CoverageOptimizer:
    version = COVERAGE_POLICY_VERSION

    def __init__(
        self,
        constraints: Optional[Mapping[str, int]] = None,
        *,
        alpha: float = CVAR_ALPHA,
    ) -> None:
        self.constraints = dict(DEFAULT_CONSTRAINTS)
        if constraints:
            self.constraints.update(constraints)
        self.alpha = alpha

    # -- feasible set ------------------------------------------------------
    def _eligible(self, candidates: Sequence[CoverageCandidate]) -> List[CoverageCandidate]:
        return [
            candidate
            for candidate in candidates
            if not candidate.blocked
            and not mutually_exclusive(candidate.solutions)
        ]

    # -- MILP --------------------------------------------------------------
    def _solve_milp(
        self,
        candidates: Sequence[CoverageCandidate],
        utilities: np.ndarray,
    ) -> Tuple[Optional[List[int]], str]:
        """Rockafellar-Uryasev CVaR MILP.

        Variables: x_i in {0,1} for each candidate, eta (VaR level, free) and
        u_s >= 0 slack per scenario.  Objective (maximised):

            0.45 * mean_s(sum_i U[i,s] x_i)
          + 0.55 * (eta - 1/(alpha S) * sum_s u_s)

        with  u_s >= eta - sum_i U[i,s] x_i.
        """
        try:
            from scipy.optimize import LinearConstraint, milp, Bounds
        except ImportError:  # pragma: no cover - scipy is a hard dependency
            return None, "SOLVER_UNAVAILABLE"

        n = len(candidates)
        scenarios = utilities.shape[1]
        # variable order: x (n) | eta (1) | u (S)
        total_vars = n + 1 + scenarios

        expectation = utilities.mean(axis=1)  # per candidate
        objective = np.zeros(total_vars)
        objective[:n] = -EXPECTATION_WEIGHT * expectation  # milp minimises
        objective[n] = -CVAR_WEIGHT
        objective[n + 1 :] = CVAR_WEIGHT / (self.alpha * scenarios)

        integrality = np.zeros(total_vars)
        integrality[:n] = 1
        lower = np.concatenate([np.zeros(n), [-np.inf], np.zeros(scenarios)])
        upper = np.concatenate([np.ones(n), [np.inf], np.full(scenarios, np.inf)])

        constraints = []

        # u_s + sum_i U[i,s] x_i - eta >= 0
        tail = np.zeros((scenarios, total_vars))
        tail[:, :n] = utilities.T
        tail[:, n] = -1.0
        tail[:, n + 1 :] = np.eye(scenarios)
        constraints.append(LinearConstraint(tail, lb=0.0, ub=np.inf))

        def group_constraint(keys: Sequence[str], limit: int) -> None:
            unique = sorted(set(keys))
            if not unique:
                return
            matrix = np.zeros((len(unique), total_vars))
            for row, key in enumerate(unique):
                for column, candidate_key in enumerate(keys):
                    if candidate_key == key:
                        matrix[row, column] = 1.0
            constraints.append(LinearConstraint(matrix, lb=0.0, ub=float(limit)))

        capacity = np.zeros((1, total_vars))
        capacity[0, :n] = 1.0
        constraints.append(
            LinearConstraint(capacity, lb=0.0, ub=float(self.constraints["capacity"]))
        )
        group_constraint(
            [candidate.entity_id for candidate in candidates],
            self.constraints["max_per_client"],
        )
        group_constraint(
            [
                f"{candidate.entity_id}|{candidate.stakeholder_role}"
                for candidate in candidates
            ],
            self.constraints["max_per_client_role"],
        )
        group_constraint(
            [candidate.family.value for candidate in candidates],
            self.constraints["max_per_solution_family"],
        )
        group_constraint(
            [candidate.sector for candidate in candidates],
            self.constraints["max_per_sector"],
        )

        result = milp(
            c=objective,
            constraints=constraints,
            integrality=integrality,
            bounds=Bounds(lower, upper),
        )
        if not result.success or result.x is None:
            return None, f"SOLVER_FAILED:{getattr(result, 'status', 'unknown')}"
        chosen = [index for index in range(n) if result.x[index] > 0.5]
        return chosen, "OPTIMAL"

    # -- greedy fallback ---------------------------------------------------
    def _solve_greedy(
        self,
        candidates: Sequence[CoverageCandidate],
        utilities: np.ndarray,
    ) -> List[int]:
        scores = [
            EXPECTATION_WEIGHT * float(utilities[index].mean())
            + CVAR_WEIGHT * cvar(utilities[index], self.alpha)
            for index in range(len(candidates))
        ]
        order = sorted(
            range(len(candidates)),
            key=lambda index: (-scores[index], candidates[index].candidate_id),
        )
        chosen: List[int] = []
        clients: Counter = Counter()
        roles: Counter = Counter()
        families: Counter = Counter()
        sectors: Counter = Counter()
        for index in order:
            if len(chosen) >= self.constraints["capacity"]:
                break
            candidate = candidates[index]
            role_key = f"{candidate.entity_id}|{candidate.stakeholder_role}"
            if clients[candidate.entity_id] >= self.constraints["max_per_client"]:
                continue
            if roles[role_key] >= self.constraints["max_per_client_role"]:
                continue
            if families[candidate.family.value] >= self.constraints["max_per_solution_family"]:
                continue
            if sectors[candidate.sector] >= self.constraints["max_per_sector"]:
                continue
            chosen.append(index)
            clients[candidate.entity_id] += 1
            roles[role_key] += 1
            families[candidate.family.value] += 1
            sectors[candidate.sector] += 1
        return chosen

    # -- public ------------------------------------------------------------
    def optimize(
        self,
        candidates: Sequence[CoverageCandidate],
        axis_draws: Mapping[str, Mapping[str, np.ndarray]],
    ) -> Dict[str, object]:
        eligible = self._eligible(candidates)
        if not eligible:
            return {
                "selected": [],
                "solver_status": "NO_ELIGIBLE_CANDIDATES",
                "degraded_fallback": False,
                "objective_value": 0.0,
                "expected": 0.0,
                "cvar": 0.0,
                "utilities": {},
                "scenario_draws": 0,
            }

        utilities = np.vstack(
            [
                adjusted_benefit_draws(axis_draws[candidate.candidate_id], candidate)
                for candidate in eligible
            ]
        )
        chosen, status = self._solve_milp(eligible, utilities)
        degraded = False
        if chosen is None:
            chosen = self._solve_greedy(eligible, utilities)
            status = "DEGRADED_FALLBACK"
            degraded = True

        # Deterministic tie-breaking: rank by robust utility then candidate id.
        ranked = sorted(
            chosen,
            key=lambda index: (
                -(
                    EXPECTATION_WEIGHT * float(utilities[index].mean())
                    + CVAR_WEIGHT * cvar(utilities[index], self.alpha)
                ),
                eligible[index].candidate_id,
            ),
        )
        selected = [eligible[index] for index in ranked]
        portfolio = utilities[ranked].sum(axis=0) if ranked else np.zeros(
            utilities.shape[1]
        )
        expected = float(portfolio.mean())
        tail = cvar(portfolio, self.alpha)
        objective = EXPECTATION_WEIGHT * expected + CVAR_WEIGHT * tail

        return {
            "selected": selected,
            "selected_indices": ranked,
            "solver_status": status,
            "degraded_fallback": degraded,
            "objective_value": objective,
            "expected": expected,
            "cvar": tail,
            "utilities": {
                eligible[index].candidate_id: utilities[index] for index in range(len(eligible))
            },
            "scenario_draws": int(utilities.shape[1]),
            "eligible_count": len(eligible),
            "constraint_report": self._constraint_report(selected),
        }

    def _constraint_report(
        self, selected: Sequence[CoverageCandidate]
    ) -> Dict[str, Dict[str, int]]:
        return {
            "per_client": dict(Counter(item.entity_id for item in selected)),
            "per_client_role": dict(
                Counter(f"{item.entity_id}|{item.stakeholder_role}" for item in selected)
            ),
            "per_solution_family": dict(
                Counter(item.family.value for item in selected)
            ),
            "per_sector": dict(Counter(item.sector for item in selected)),
        }


def selection_stability(
    candidate_id: str,
    utilities: Mapping[str, np.ndarray],
    optimizer: CoverageOptimizer,
    candidates: Sequence[CoverageCandidate],
    *,
    bootstrap: int = 24,
) -> float:
    """Share of scenario resamples in which this candidate stays selected.

    This is the number the workbench shows instead of an opaque confidence
    percentage: it answers "would the plan still contain this conversation if
    the world turned out differently?"
    """
    if candidate_id not in utilities:
        return 0.0
    eligible = [item for item in candidates if item.candidate_id in utilities]
    if not eligible:
        return 0.0
    matrix = np.vstack([utilities[item.candidate_id] for item in eligible])
    scenarios = matrix.shape[1]
    rng = np.random.default_rng(1_031)
    hits = 0
    index_of = {item.candidate_id: index for index, item in enumerate(eligible)}
    for _ in range(bootstrap):
        sample = rng.choice(scenarios, size=scenarios, replace=True)
        resampled = matrix[:, sample]
        chosen = optimizer._solve_greedy(eligible, resampled)
        if index_of[candidate_id] in chosen:
            hits += 1
    return hits / bootstrap
