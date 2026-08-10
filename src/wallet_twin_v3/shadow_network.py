from __future__ import annotations

import hashlib
import math
from datetime import date
from typing import Iterable, Sequence

import numpy as np

from wallet_twin_v2.contracts import ClaimClass, DataProvenanceClass, OpportunityView

from .contracts import AmountInterval, ShadowFlow, ShadowWalletReconstruction


ANONYMOUS_PROVIDERS = (
    "External provider A",
    "External provider B",
    "External provider C",
)


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16) % (2**32)


def _normalise(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    array = np.maximum(array, 1e-12)
    return array / array.sum()


def sinkhorn_coupling(
    row_marginal: Sequence[float],
    column_marginal: Sequence[float],
    cost: np.ndarray,
    epsilon: float = 0.65,
    iterations: int = 40,
) -> np.ndarray:
    """Entropy-regularised transport coupling with exact marginal scaling."""
    rows = _normalise(row_marginal)
    columns = _normalise(column_marginal)
    if cost.shape != (len(rows), len(columns)):
        raise ValueError("cost matrix shape does not match marginals")
    kernel = np.exp(-np.asarray(cost, dtype=float) / max(epsilon, 1e-6))
    kernel = np.maximum(kernel, 1e-15)
    u = np.ones_like(rows)
    v = np.ones_like(columns)
    for _ in range(iterations):
        u = rows / np.maximum(kernel @ v, 1e-15)
        v = columns / np.maximum(kernel.T @ u, 1e-15)
    coupling = np.diag(u) @ kernel @ np.diag(v)
    return coupling / coupling.sum()


class ShadowNetworkReconstructor:
    """Reconstructs an anonymous external wallet network under hard mass balance.

    The ensemble varies posterior total wallet, anonymous-provider concentration
    and transport costs.  This quantifies the identified ambiguity; it does not
    identify named competitor banks.
    """

    def __init__(self, draws: int = 256, epsilon: float = 0.65) -> None:
        if draws < 32:
            raise ValueError("at least 32 ensemble draws are required")
        self.draws = draws
        self.epsilon = epsilon

    def reconstruct(
        self,
        opportunity: OpportunityView,
        corridors: Sequence[tuple[str, float]],
    ) -> ShadowWalletReconstruction:
        rng = np.random.default_rng(_seed(opportunity.opportunity_id))
        observed = float(opportunity.observed_activity.normalized_amount)
        total = opportunity.posterior_wallet
        corridor_names = [name for name, _ in corridors[:5]] or ["Unspecified corridor"]
        corridor_prior = _normalise([value for _, value in corridors[:5]] or [1.0])
        provider_prior = _normalise(self._provider_prior(opportunity.product))
        base_cost = self._cost_matrix(len(corridor_names), opportunity.product)

        totals = rng.triangular(total.lower, total.median, total.upper, size=self.draws)
        totals = np.maximum(totals, observed)
        external_totals = totals - observed
        edge_draws = np.zeros(
            (self.draws, len(corridor_names), len(ANONYMOUS_PROVIDERS))
        )
        for draw in range(self.draws):
            provider_marginal = rng.dirichlet(provider_prior * 18.0)
            perturbed_cost = np.maximum(
                0.0, base_cost + rng.normal(0.0, 0.12, base_cost.shape)
            )
            coupling = sinkhorn_coupling(
                corridor_prior,
                provider_marginal,
                perturbed_cost,
                epsilon=self.epsilon,
            )
            edge_draws[draw] = coupling * external_totals[draw]

        medians = np.quantile(edge_draws, 0.5, axis=0)
        median_total = max(total.median, observed)
        target_external = median_total - observed
        if medians.sum() > 0:
            medians *= target_external / medians.sum()
        lowers = np.minimum(np.quantile(edge_draws, 0.1, axis=0), medians)
        uppers = np.maximum(np.quantile(edge_draws, 0.9, axis=0), medians)

        flows: list[ShadowFlow] = []
        for row, corridor in enumerate(corridor_names):
            for column, provider in enumerate(ANONYMOUS_PROVIDERS):
                flows.append(
                    ShadowFlow(
                        edge_id=f"{opportunity.opportunity_id}:{row}:{column}",
                        entity_id=opportunity.entity_id,
                        product=opportunity.product,
                        corridor=corridor,
                        provider_node=provider,
                        amount=AmountInterval(
                            lower=float(lowers[row, column]),
                            median=float(medians[row, column]),
                            upper=float(uppers[row, column]),
                        ),
                        observed_by_bank=False,
                        claim_class=ClaimClass.SCENARIO,
                        provenance=DataProvenanceClass.SYNTHETIC_SIMULATION,
                    )
                )

        median_coupling = medians / max(medians.sum(), 1e-12)
        entropy = -float(
            np.sum(median_coupling * np.log(np.maximum(median_coupling, 1e-12)))
        )
        entropy /= math.log(max(2, median_coupling.size))
        external_interval = AmountInterval(
            lower=max(0.0, total.lower - observed),
            median=target_external,
            upper=max(0.0, total.upper - observed),
        )
        share_values = [
            min(1.0, observed / max(total.upper, observed)),
            min(1.0, observed / max(median_total, observed)),
            min(1.0, observed / max(total.lower, observed)),
        ]
        return ShadowWalletReconstruction(
            reconstruction_id=f"shadow:{opportunity.opportunity_id}:v3.0.0",
            opportunity_id=opportunity.opportunity_id,
            entity_id=opportunity.entity_id,
            product=opportunity.product,
            as_of=date.fromisoformat(str(opportunity.as_of)),
            observed_bank_flow=observed,
            total_wallet=AmountInterval(
                lower=max(observed, total.lower),
                median=median_total,
                upper=max(median_total, total.upper),
            ),
            latent_external_wallet=external_interval,
            bank_share=AmountInterval(
                lower=share_values[0],
                median=share_values[1],
                upper=share_values[2],
                currency="ratio",
            ),
            flows=flows,
            normalized_entropy=min(1.0, max(0.0, entropy)),
            ensemble_draws=self.draws,
            method="posterior-constrained ensemble + entropy-regularised Sinkhorn transport",
        )

    @staticmethod
    def _provider_prior(product: str) -> tuple[float, float, float]:
        return {
            "Trade finance": (0.48, 0.32, 0.20),
            "Cross-border FX": (0.44, 0.34, 0.22),
            "Liquidity": (0.52, 0.29, 0.19),
            "Payments": (0.40, 0.35, 0.25),
            "Collections": (0.39, 0.34, 0.27),
        }.get(product, (0.45, 0.33, 0.22))

    @staticmethod
    def _cost_matrix(rows: int, product: str) -> np.ndarray:
        product_offset = (sum(ord(character) for character in product) % 7) / 20.0
        return np.fromfunction(
            lambda row, column: (
                np.abs((row % 3) - column) * 0.28 + row * 0.03 + product_offset
            ),
            (rows, len(ANONYMOUS_PROVIDERS)),
            dtype=float,
        )
