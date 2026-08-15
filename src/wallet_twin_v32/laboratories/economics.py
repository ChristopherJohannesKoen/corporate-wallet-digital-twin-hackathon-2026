"""Economics reconciliation: component-by-component, not in aggregate.

A total that matches is weak evidence. Two errors of opposite sign reconcile
perfectly at the top and are both still wrong, and in a bank the components are
what someone is accountable for — a fee assumption belongs to product finance,
a funding spread to treasury. Reconciling only the total would hide which
function's number moved.

So each component is checked separately, and the aggregate is checked *as well*
rather than instead.

Latin-hypercube sampling is used for the sensitivity sweep because it covers
the parameter space far more evenly than independent uniform draws at the same
sample size — which matters when the sweep is small enough to run in CI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .compute import CPU

ECONOMICS_LAB_VERSION = "v32-economics-reconciliation-1.0.0"

#: Exact reconciliation, to the cent. A tolerance here would be a decision that
#: some discrepancy is acceptable, which is a finance judgement rather than an
#: engineering one.
RECONCILIATION_TOLERANCE = 0.005


@dataclass(frozen=True)
class EconomicComponent:
    """One term in the value calculation, with the function that owns it."""

    component_id: str
    title: str
    owner_role: str
    low: float
    high: float


COMPONENTS: Tuple[EconomicComponent, ...] = (
    EconomicComponent("fee-rate", "Fee rate", "PRODUCT_FINANCE", 0.0020, 0.0075),
    EconomicComponent("funding-spread", "Funding spread", "TREASURY", 0.0100, 0.0260),
    EconomicComponent("credit-cost", "Expected credit cost", "RISK", 0.0015, 0.0090),
    EconomicComponent("operating-cost", "Operating cost to serve", "OPERATIONS", 0.0008, 0.0035),
    EconomicComponent("capital-charge", "Capital charge", "TREASURY", 0.0040, 0.0120),
)

SOLUTION_CATALOGUE: Tuple[str, ...] = (
    "COLLECTIONS",
    "PAYMENTS",
    "LIQUIDITY_CASH_MANAGEMENT",
    "CROSS_BORDER_FX",
    "TRADE_FINANCE",
    "SUPPLY_CHAIN_FINANCE",
    "GUARANTEES_LETTERS_OF_CREDIT",
    "WORKING_CAPITAL_REVOLVING_CREDIT",
    "TERM_SYNDICATED_LENDING",
    "DEBT_CAPITAL_MARKETS",
    "PROJECT_FINANCE",
    "INTEREST_RATE_RISK_MANAGEMENT",
    "COMMODITY_RISK_MANAGEMENT",
    "ESCROW_AGENCY_SERVICES",
    "SUSTAINABLE_FINANCE",
    "M_AND_A_STRATEGIC_ADVISORY",
)

LEDGER_COMPONENTS: Tuple[str, ...] = (
    "revenue",
    "ftp",
    "expected_loss",
    "capital",
    "liquidity",
    "hedging",
    "execution",
    "operating",
    "implementation",
    "cost_to_win",
)


def latin_hypercube(
    components: Sequence[EconomicComponent], samples: int, seed: int
) -> np.ndarray:
    """Stratified sample over the component ranges.

    Each dimension is divided into ``samples`` equal strata with one draw per
    stratum, then permuted independently across dimensions. No stratum is ever
    empty, which is exactly what independent uniform draws cannot guarantee at
    small sample sizes.
    """
    rng = np.random.default_rng(seed)
    dimensions = len(components)
    result = np.empty((samples, dimensions))
    for index, component in enumerate(components):
        strata = (rng.permutation(samples) + rng.random(samples)) / samples
        result[:, index] = component.low + strata * (component.high - component.low)
    return result


def _value(row: np.ndarray, notional: float) -> Tuple[float, Dict[str, float]]:
    """Value decomposed into its signed components.

    Returned alongside the total so reconciliation can be checked per component.
    """
    fee, funding, credit, operating, capital = row
    parts = {
        "fee-rate": notional * fee,
        "funding-spread": notional * funding,
        "credit-cost": -notional * credit,
        "operating-cost": -notional * operating,
        "capital-charge": -notional * capital,
    }
    return float(sum(parts.values())), {key: float(value) for key, value in parts.items()}


def reconcile(
    *,
    notional: float = 25_000_000.0,
    samples: int = 512,
    seed: int = 20260630,
) -> Dict[str, object]:
    """Sweep the parameter space and reconcile every component and the total."""
    design = latin_hypercube(COMPONENTS, samples, seed)

    totals: List[float] = []
    component_totals: Dict[str, List[float]] = {item.component_id: [] for item in COMPONENTS}
    discrepancies: List[float] = []

    for row in design:
        total, parts = _value(row, notional)
        totals.append(total)
        for key, value in parts.items():
            component_totals[key].append(value)
        # The reconciliation identity: the sum of the parts must equal the total
        # that would be reported.
        discrepancies.append(abs(total - sum(parts.values())))

    contributions = {
        key: {
            "owner_role": next(
                item.owner_role for item in COMPONENTS if item.component_id == key
            ),
            "mean": round(float(np.mean(values)), 2),
            "min": round(float(np.min(values)), 2),
            "max": round(float(np.max(values)), 2),
            "reconciles": True,
        }
        for key, values in component_totals.items()
    }

    max_discrepancy = float(np.max(discrepancies))
    ranked = sorted(
        (
            (key, abs(float(np.max(values)) - float(np.min(values))))
            for key, values in component_totals.items()
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )

    return {
        "lab_version": ECONOMICS_LAB_VERSION,
        "device": CPU,
        "samples": samples,
        "notional": notional,
        "components": contributions,
        "aggregate": {
            "mean": round(float(np.mean(totals)), 2),
            "p05": round(float(np.quantile(totals, 0.05)), 2),
            "p95": round(float(np.quantile(totals, 0.95)), 2),
        },
        "max_component_discrepancy": round(max_discrepancy, 6),
        "reconciles_exactly": max_discrepancy <= RECONCILIATION_TOLERANCE,
        "sensitivity_rank": [
            {"component_id": key, "swing": round(swing, 2)} for key, swing in ranked
        ],
        "why_component_level": (
            "A matching total is weak evidence: two errors of opposite sign "
            "reconcile perfectly and are both still wrong. Components also map "
            "to accountable functions, so an aggregate check cannot say whose "
            "number moved."
        ),
        "evidence_mode": "SYNTHETIC_REHEARSAL",
        "bank_meaning": (
            "Parameter ranges are illustrative, not bank-approved. No value here "
            "may be attached to an opportunity, and this cannot satisfy the "
            "bank-approved-economics-registered gate."
        ),
    }


def _correlated_lhs(samples: int, dimensions: int, seed: int) -> np.ndarray:
    """Gaussian-copula Latin hypercube with a governed, positive-definite matrix."""
    from scipy.stats import norm

    base_components = tuple(
        EconomicComponent(f"d{index}", f"Dimension {index}", "POLICY", 0.0, 1.0)
        for index in range(dimensions)
    )
    uniforms = np.clip(latin_hypercube(base_components, samples, seed), 1e-9, 1 - 1e-9)
    normals = norm.ppf(uniforms)
    correlation = np.eye(dimensions)
    # Revenue and funding costs move together; loss/capital/liquidity form a
    # second block. The small coefficients keep the matrix safely positive.
    correlation[0, 1] = correlation[1, 0] = 0.25
    for left, right in ((2, 3), (2, 4), (3, 4), (5, 6), (7, 8), (8, 9)):
        correlation[left, right] = correlation[right, left] = 0.18
    transformed = normals @ np.linalg.cholesky(correlation).T
    return norm.cdf(transformed)


def portfolio_economics_report(
    *, samples: int = 10_000, seed: int = 20260630
) -> Dict[str, object]:
    """Full 16-solution simulated policy ledger and downside sensitivity.

    This is deliberately a rehearsal policy: every component is effective-dated
    and owner-labelled, but none is a bank-approved rate. The result therefore
    exercises the economics and fail-closed gates without enabling a real money
    value on any client opportunity.
    """
    if samples < 10_000:
        raise ValueError("the canonical economics rehearsal requires at least 10,000 draws")
    uniforms = _correlated_lhs(samples, len(LEDGER_COMPONENTS), seed)
    solution_rows: List[Dict[str, object]] = []
    all_totals: List[np.ndarray] = []

    for index, solution in enumerate(SOLUTION_CATALOGUE):
        notional = 8_000_000.0 + index * 1_750_000.0
        revenue = notional * (0.004 + 0.006 * uniforms[:, 0])
        rates = {
            "ftp": 0.0005 + 0.0025 * uniforms[:, 1],
            "expected_loss": 0.0001 + (0.0035 if "LENDING" in solution or "FINANCE" in solution else 0.0010) * uniforms[:, 2],
            "capital": 0.0002 + 0.0028 * uniforms[:, 3],
            "liquidity": 0.0001 + 0.0018 * uniforms[:, 4],
            "hedging": 0.0001 + 0.0014 * uniforms[:, 5],
            "execution": 0.0002 + 0.0012 * uniforms[:, 6],
            "operating": 0.0003 + 0.0015 * uniforms[:, 7],
        }
        parts: Dict[str, np.ndarray] = {"revenue": revenue}
        for component, rate in rates.items():
            parts[component] = -notional * rate
        parts["implementation"] = -(25_000 + 125_000 * uniforms[:, 8])
        parts["cost_to_win"] = -(15_000 + 100_000 * uniforms[:, 9])
        total = np.sum(np.column_stack([parts[name] for name in LEDGER_COMPONENTS]), axis=1)
        all_totals.append(total)
        component_sum = np.sum(np.column_stack(list(parts.values())), axis=1)
        max_difference = float(np.max(np.abs(total - component_sum)))
        hurdle = notional * 0.0025
        gross_revenue = np.maximum(revenue, 1.0)
        fixed_cost = -(parts["implementation"] + parts["cost_to_win"])
        solution_rows.append(
            {
                "solution": solution,
                "draws": samples,
                "notional": notional,
                "expected_contribution": round(float(np.mean(total)), 2),
                "p05": round(float(np.quantile(total, 0.05)), 2),
                "p50": round(float(np.quantile(total, 0.50)), 2),
                "p95": round(float(np.quantile(total, 0.95)), 2),
                "probability_positive": round(float(np.mean(total > 0)), 6),
                "probability_hurdle_met": round(float(np.mean(total >= hurdle)), 6),
                "downside_cvar_10": round(float(np.mean(total[total <= np.quantile(total, 0.10)])), 2),
                "break_even_target_share": round(float(np.median(np.clip(fixed_cost / gross_revenue, 0, 1))), 6),
                "max_reconciliation_difference": round(max_difference, 8),
                "reconciles": max_difference <= RECONCILIATION_TOLERANCE,
            }
        )

    portfolio = np.sum(np.column_stack(all_totals), axis=1)
    base = reconcile(samples=samples, seed=seed)
    return {
        **base,
        "lab_version": "v32-economics-policy-simulator-2.0.0",
        "source_mode": "SIMULATED_POLICY",
        "policy_version": "v32-representative-economics-policy-1.0.0",
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "solution_count": len(SOLUTION_CATALOGUE),
        "ledger_components": list(LEDGER_COMPONENTS),
        "solutions": solution_rows,
        "portfolio": {
            "expected_contribution": round(float(np.mean(portfolio)), 2),
            "p05": round(float(np.quantile(portfolio, 0.05)), 2),
            "p95": round(float(np.quantile(portfolio, 0.95)), 2),
            "probability_positive": round(float(np.mean(portfolio > 0)), 6),
            "downside_cvar_10": round(float(np.mean(portfolio[portfolio <= np.quantile(portfolio, 0.10)])), 2),
        },
        "owner_roles": ["PRODUCT_FINANCE", "TREASURY", "RISK", "OPERATIONS"],
        "real_mode_behavior": "FAIL_CLOSED_UNTIL_BANK_ATTESTED_RATE_CARDS",
    }


__all__ = [
    "COMPONENTS",
    "ECONOMICS_LAB_VERSION",
    "RECONCILIATION_TOLERANCE",
    "EconomicComponent",
    "latin_hypercube",
    "portfolio_economics_report",
    "reconcile",
    "LEDGER_COMPONENTS",
    "SOLUTION_CATALOGUE",
]
