from __future__ import annotations

import hashlib
import math
from collections import Counter
from datetime import date
from typing import Sequence

import numpy as np

from wallet_twin_v2.contracts import EvidenceTier, OpportunityView

from .contracts import (
    LeakageAlarm,
    PortfolioAction,
    ProductNeedEstimate,
    RobustActionPortfolio,
)


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16) % (2**32)


def _money(value: float) -> float:
    """Quantize commercial inputs/outputs to the published cent boundary."""

    return round(float(value), 2)


def _probability(value: float) -> float:
    """Remove solver/BLAS noise before it can parameterize random draws."""

    # Six decimals is far below any displayed or policy-sensitive precision,
    # while remaining safely above the observed cross-platform solver jitter.
    return round(float(value), 6)


def _mean(values: np.ndarray) -> float:
    """Portable mean: deterministic summation, independent of NumPy reduction."""

    return math.fsum(float(value) for value in values) / max(1, int(values.size))


class RobustPortfolioOptimizer:
    """Capacity-constrained greedy optimizer over common scenario draws.

    Candidate scores use lower-tail CVaR and therefore remain robust to wallet,
    price and conversion uncertainty.  The output is a commercial scenario, not
    a causal recommendation policy.
    """

    def __init__(
        self, draws: int = 512, alpha: float = 0.10, risk_aversion: float = 0.55
    ) -> None:
        self.draws = draws
        self.alpha = alpha
        self.risk_aversion = risk_aversion

    def optimize(
        self,
        opportunities: Sequence[OpportunityView],
        needs: dict[str, ProductNeedEstimate],
        leakages: dict[str, LeakageAlarm],
        as_of: date,
        capacity: int = 12,
        max_per_client: int = 1,
        max_per_product: int = 4,
        max_per_sector: int = 4,
    ) -> RobustActionPortfolio:
        candidates: list[tuple[PortfolioAction, np.ndarray]] = []
        for opportunity in opportunities:
            commercial = opportunity.commercial.contestable_scenario_contribution
            base_value = _money(
                float(commercial.normalized_amount) if commercial is not None else 0.0
            )
            need = needs[opportunity.opportunity_id]
            leakage = leakages[opportunity.opportunity_id]
            need_probability = _probability(need.product_need_probability)
            leakage_probability = _probability(leakage.alarm_probability)
            rng = np.random.default_rng(
                _seed(f"portfolio:{opportunity.opportunity_id}")
            )
            wallet_factor = rng.lognormal(
                mean=-0.5 * 0.30**2, sigma=0.30, size=self.draws
            )
            conversion = rng.beta(
                3.0 + 4.0 * need_probability, 4.0, size=self.draws
            )
            leakage_urgency = 1.0 + leakage_probability * rng.uniform(
                0.0, 0.25, size=self.draws
            )
            scenario_values = np.maximum(
                0.0, base_value * wallet_factor * conversion * leakage_urgency
            )
            expected = _money(_mean(scenario_values))
            tail_count = max(1, int(self.draws * self.alpha))
            downside_cvar = _money(_mean(np.sort(scenario_values)[:tail_count]))
            robust_score = _money((
                1.0 - self.risk_aversion
            ) * expected + self.risk_aversion * downside_cvar
            )
            candidates.append(
                (
                    PortfolioAction(
                        action_id=f"action:{opportunity.opportunity_id}",
                        opportunity_id=opportunity.opportunity_id,
                        entity_id=opportunity.entity_id,
                        entity_name=opportunity.entity_name,
                        sector=opportunity.sector,
                        product=opportunity.product,
                        robust_score=robust_score,
                        expected_scenario_value_zar=expected,
                        downside_cvar_zar=downside_cvar,
                        need_probability=need_probability,
                        leakage_probability=leakage_probability,
                        evidence_tier=EvidenceTier(opportunity.evidence_tier),
                    ),
                    scenario_values,
                )
            )

        selected: list[PortfolioAction] = []
        selected_draws: list[np.ndarray] = []
        client_counts: Counter[str] = Counter()
        product_counts: Counter[str] = Counter()
        sector_counts: Counter[str] = Counter()
        for action, draws in sorted(
            candidates, key=lambda pair: (-pair[0].robust_score, pair[0].action_id)
        ):
            if len(selected) >= capacity:
                break
            if client_counts[action.entity_id] >= max_per_client:
                continue
            if product_counts[action.product] >= max_per_product:
                continue
            if sector_counts[action.sector] >= max_per_sector:
                continue
            selected.append(action)
            selected_draws.append(draws)
            client_counts[action.entity_id] += 1
            product_counts[action.product] += 1
            sector_counts[action.sector] += 1

        portfolio_draws = np.asarray(
            [
                math.fsum(float(draw[index]) for draw in selected_draws)
                for index in range(self.draws)
            ],
            dtype=float,
        ) if selected_draws else np.zeros(self.draws)
        tail_count = max(1, int(self.draws * self.alpha))
        return RobustActionPortfolio(
            portfolio_id=f"rm-capacity:{as_of.isoformat()}:v3.0.0",
            as_of=as_of,
            capacity=capacity,
            selected_actions=selected,
            expected_scenario_value_zar=_money(_mean(portfolio_draws)),
            downside_cvar_zar=_money(_mean(np.sort(portfolio_draws)[:tail_count])),
            product_counts=dict(product_counts),
            sector_counts=dict(sector_counts),
            constraints={
                "max_per_client": max_per_client,
                "max_per_product": max_per_product,
                "max_per_sector": max_per_sector,
            },
            scenario_draws=self.draws,
            method="capacity-constrained robust selection using lower-tail CVaR scenario utility",
        )
