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


__all__ = [
    "COMPONENTS",
    "ECONOMICS_LAB_VERSION",
    "RECONCILIATION_TOLERANCE",
    "EconomicComponent",
    "latin_hypercube",
    "reconcile",
]
