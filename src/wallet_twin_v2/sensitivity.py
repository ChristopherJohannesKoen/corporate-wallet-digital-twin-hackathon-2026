from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional

import numpy as np
from scipy.stats import norm, qmc, spearmanr


DRIVERS = (
    "share_prior",
    "wallet",
    "target_share",
    "anchor_error",
    "competitor_error",
    "fx_policy",
    "price",
    "ftp",
    "capital",
)


@dataclass(frozen=True)
class SensitivityOpportunity:
    opportunity_id: str
    product: str
    wallet: float
    current_share: float
    price_bps: float
    ftp_bps: float = 0.0
    capital_bps: float = 0.0
    anchor_active: bool = False


class SensitivityEngine:
    """Correlated, reproducible global scenario analysis.

    The engine reports conclusions; it never encodes an expected winning
    product in tests or implementation.
    """

    version = "lhs-copula-sensitivity-2.0.0"

    def __init__(self, draws: int = 10_000, seed: int = 20260808) -> None:
        if draws < 10_000:
            raise ValueError("production sensitivity requires at least 10,000 draws")
        self.draws = draws
        self.seed = seed

    @staticmethod
    def _correlate(unit: np.ndarray, correlation: np.ndarray) -> np.ndarray:
        if correlation.shape != (len(DRIVERS), len(DRIVERS)):
            raise ValueError("correlation matrix has the wrong dimensions")
        if not np.allclose(correlation, correlation.T, atol=1e-8):
            raise ValueError("correlation matrix must be symmetric")
        eigenvalues = np.linalg.eigvalsh(correlation)
        if np.min(eigenvalues) < -1e-8:
            raise ValueError("correlation matrix must be positive semidefinite")
        jittered = correlation + np.eye(len(DRIVERS)) * 1e-10
        normal_scores = norm.ppf(np.clip(unit, 1e-9, 1 - 1e-9))
        correlated = normal_scores @ np.linalg.cholesky(jittered).T
        return norm.cdf(correlated)

    def run(
        self,
        opportunities: Iterable[SensitivityOpportunity],
        correlation: Optional[np.ndarray] = None,
    ) -> dict:
        items = list(opportunities)
        if not items:
            raise ValueError("at least one opportunity is required")
        sampler = qmc.LatinHypercube(d=len(DRIVERS), seed=self.seed)
        unit = sampler.random(self.draws)
        corr = correlation if correlation is not None else np.eye(len(DRIVERS))
        values = self._correlate(unit, corr)

        share_multiplier = 0.75 + 0.50 * values[:, 0]
        wallet_multiplier = 0.70 + 0.60 * values[:, 1]
        target_share = 0.30 + 0.20 * values[:, 2]
        anchor_multiplier = 0.85 + 0.30 * values[:, 3]
        competitor_multiplier = 0.80 + 0.40 * values[:, 4]
        fx_multiplier = 0.90 + 0.20 * values[:, 5]
        price_multiplier = 0.70 + 0.60 * values[:, 6]
        ftp_multiplier = 0.70 + 0.60 * values[:, 7]
        capital_multiplier = 0.70 + 0.60 * values[:, 8]

        economic = np.zeros((len(items), self.draws), dtype=float)
        for index, item in enumerate(items):
            wallet = item.wallet * wallet_multiplier
            if item.anchor_active:
                wallet *= anchor_multiplier
            if item.product == "Cross-border FX":
                wallet *= fx_multiplier
            share = np.clip(item.current_share * share_multiplier * competitor_multiplier, 0.01, 0.95)
            net_bps = np.maximum(
                item.price_bps * price_multiplier
                - item.ftp_bps * ftp_multiplier
                - item.capital_bps * capital_multiplier,
                0.0,
            )
            economic[index] = wallet * np.maximum(target_share - share, 0.0) * net_bps / 10_000.0

        top_index = np.argmax(economic, axis=0)
        top10_n = min(10, len(items))
        top10_indices = np.argpartition(economic, -top10_n, axis=0)[-top10_n:, :]
        products = sorted({item.product for item in items})
        product_summary: Dict[str, dict] = {}
        for product in products:
            product_rows = np.array([i for i, item in enumerate(items) if item.product == product], dtype=int)
            first_frequency = float(np.mean(np.isin(top_index, product_rows)))
            top10_counts = np.sum(np.isin(top10_indices, product_rows), axis=0)
            absolute = np.sum(economic[product_rows], axis=0)
            product_summary[product] = {
                "first_rank_frequency": first_frequency,
                "mean_top10_share": float(np.mean(top10_counts / top10_n)),
                "majority_dominance_frequency": float(np.mean(top10_counts >= max(1, (top10_n + 1) // 2))),
                "absolute_economics": {
                    "p05": float(np.quantile(absolute, 0.05)),
                    "p50": float(np.quantile(absolute, 0.50)),
                    "p95": float(np.quantile(absolute, 0.95)),
                },
            }

        total_economics = np.sum(economic, axis=0)
        voi = []
        for index, driver in enumerate(DRIVERS):
            coefficient = spearmanr(values[:, index], total_economics).statistic
            voi.append({"driver": driver, "absolute_rank_correlation": abs(float(coefficient))})
        voi.sort(key=lambda item: item["absolute_rank_correlation"], reverse=True)

        return {
            "version": self.version,
            "draws": self.draws,
            "seed": self.seed,
            "drivers": list(DRIVERS),
            "product_summary": product_summary,
            "portfolio_economics": {
                "p05": float(np.quantile(total_economics, 0.05)),
                "p50": float(np.quantile(total_economics, 0.50)),
                "p95": float(np.quantile(total_economics, 0.95)),
            },
            "value_of_information": voi,
            "correlation_matrix": corr.tolist(),
        }

    @staticmethod
    def legacy_grid(opportunities: Iterable[SensitivityOpportunity]) -> List[dict]:
        items = list(opportunities)
        cases = []
        for prior_name, prior_multiplier in (("low", 0.75), ("base", 1.0), ("high", 1.25)):
            for rate_name, rate_multiplier in (("low", 0.70), ("base", 1.0), ("high", 1.30)):
                values = []
                for item in items:
                    share = min(0.95, item.current_share * prior_multiplier)
                    gap = item.wallet * max(0.40 - share, 0.0) * item.price_bps * rate_multiplier / 10_000.0
                    values.append((gap, item))
                ranked = sorted(values, key=lambda pair: pair[0], reverse=True)
                top = ranked[: min(10, len(ranked))]
                trade_count = sum(item.product == "Trade finance" for _, item in top)
                cases.append(
                    {
                        "prior_case": prior_name,
                        "rate_case": rate_name,
                        "top_product": ranked[0][1].product,
                        "top_opportunity_id": ranked[0][1].opportunity_id,
                        "trade_finance_top10_count": trade_count,
                        "trade_finance_majority_dominant": trade_count >= max(1, (len(top) + 1) // 2),
                        "portfolio_gap": sum(value for value, _ in ranked),
                    }
                )
        return cases
