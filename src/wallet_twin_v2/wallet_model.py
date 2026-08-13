from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from .bounds import BoundEvidence, DeterministicBoundsEngine
from .measurement_policy import DEFAULT_MEASUREMENT_POLICY, MeasurementPolicy
from .contracts import (
    ArtifactReference,
    CalibrationObservation,
    CalibrationStatus,
    ClaimClass,
    EvidenceTier,
    IntervalEstimate,
    Money,
    WalletEstimate,
)


TIER_ORDER = {
    EvidenceTier.E0: 0,
    EvidenceTier.E1: 1,
    EvidenceTier.E2: 2,
    EvidenceTier.E3: 3,
    EvidenceTier.E4: 4,
}


@dataclass(frozen=True)
class ProductPrior:
    mean: float
    concentration: float


DEFAULT_PRIORS: Dict[str, ProductPrior] = {
    "Collections": ProductPrior(0.36, 12.0),
    "Payments": ProductPrior(0.34, 12.0),
    "Liquidity": ProductPrior(0.28, 9.0),
    "Cross-border FX": ProductPrior(0.30, 10.0),
    "Trade finance": ProductPrior(0.26, 8.0),
}


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32 - 1)


def _interval(
    values: np.ndarray,
    as_of: date,
    version: str,
    claim: ClaimClass,
    nominal_coverage: float = 0.90,
) -> IntervalEstimate:
    """A central interval at the requested nominal coverage.

    ``nominal_coverage`` defaults to 0.90, which is what every published
    artifact uses, so this parameterisation changes no committed byte. It exists
    because the V3.2 calibration laboratory audits coverage at 50% and 80% as
    well: a model can be well calibrated at 90% and badly calibrated in the
    middle of its distribution, and checking one nominal level cannot detect
    that.
    """
    if not 0.0 < nominal_coverage < 1.0:
        raise ValueError(f"nominal_coverage must lie in (0, 1); got {nominal_coverage}")
    tail = (1.0 - nominal_coverage) / 2.0
    lower, median, upper = np.quantile(values, [tail, 0.50, 1.0 - tail])
    return IntervalEstimate(
        lower=float(lower),
        median=float(median),
        upper=float(upper),
        nominal_coverage=nominal_coverage,
        model_version=version,
        as_of=as_of,
        claim_class=claim,
    )


class HierarchicalWalletModel:
    """Product-specific Bayesian share model with transparent pooled hyperpriors.

    Direct E3/E4 observations update product and sector pseudo-counts. E1/E2
    anchors enter as noisy wallet measurements rather than exact labels. The
    deterministic identification set is computed independently.
    """

    version = "hierarchical-wallet-2.0.0"
    prior_version = "product-sector-priors-1.0.0"
    transformation_version = "measurement-model-1.0.0"

    def __init__(
        self,
        observations: Iterable[CalibrationObservation] = (),
        priors: Optional[Dict[str, ProductPrior]] = None,
        draws: int = 4_000,
        policy: MeasurementPolicy = DEFAULT_MEASUREMENT_POLICY,
    ) -> None:
        self.observations = list(observations)
        self.priors = priors or DEFAULT_PRIORS
        self.draws = draws
        self.policy = policy
        self.bounds = DeterministicBoundsEngine()

    @property
    def _anchor_weight(self) -> Mapping[EvidenceTier, float]:
        return self.policy.anchor_weights

    def _posterior_parameters(self, product: str, sector: str, as_of: date) -> Tuple[float, float, int]:
        """Return a posterior-*predictive* beta distribution for a new relationship.

        Calibration rows inform the population mean and between-relationship
        dispersion. They must not be accumulated as if hundreds of different
        clients were repeated measurements of one client's share; doing that
        collapses predictive intervals and severely under-covers holdouts.
        """
        prior = self.priors[product]
        values: List[float] = []
        weights: List[float] = []
        for observation in self.observations:
            if observation.product != product or observation.as_of > as_of:
                continue
            reliability = {
                EvidenceTier.E0: 0.0,
                EvidenceTier.E1: 0.0,
                EvidenceTier.E2: 0.25,
                EvidenceTier.E3: 1.0,
                EvidenceTier.E4: 1.5,
            }[observation.tier]
            weight = reliability * observation.selection_weight
            if weight <= 0:
                continue
            # Other sectors inform the product hyperprior but are discounted.
            weight *= 1.0 if observation.sector == sector else 0.35
            values.append(observation.measured_share)
            weights.append(weight)
        used = len(values)
        if not values:
            return prior.mean * prior.concentration, (1.0 - prior.mean) * prior.concentration, 0

        value_array = np.asarray(values, dtype=float)
        weight_array = np.asarray(weights, dtype=float)
        weighted_mean = float(np.average(value_array, weights=weight_array))
        effective_n = float(weight_array.sum() ** 2 / np.sum(weight_array**2))
        blend = effective_n / (effective_n + 8.0)
        predictive_mean = (1.0 - blend) * prior.mean + blend * weighted_mean

        if effective_n >= 2.0:
            weighted_variance = float(np.average((value_array - weighted_mean) ** 2, weights=weight_array))
            inferred_concentration = predictive_mean * (1.0 - predictive_mean) / max(weighted_variance, 0.003) - 1.0
            inferred_concentration = float(np.clip(inferred_concentration, 4.0, 35.0))
            predictive_concentration = (1.0 - blend) * prior.concentration + blend * inferred_concentration
        else:
            predictive_concentration = prior.concentration
        alpha = predictive_mean * predictive_concentration
        beta = (1.0 - predictive_mean) * predictive_concentration
        return alpha, beta, used

    def estimate(
        self,
        *,
        opportunity_id: str,
        entity_id: str,
        product: str,
        sector: str,
        observed_activity: float,
        as_of: date,
        evidence_tier: EvidenceTier,
        anchor_range: Optional[Sequence[float]] = None,
        fact_ids: Sequence[str] = (),
        capacity: Optional[float] = None,
        direct_share: Optional[float] = None,
        dataset_version: str = "fixture-v1-baseline",
    ) -> Tuple[WalletEstimate, np.ndarray, np.ndarray]:
        if product not in self.priors:
            raise ValueError(f"unsupported product: {product}")
        if observed_activity < 0:
            raise ValueError("observed_activity must be non-negative")
        if direct_share is not None and evidence_tier not in {EvidenceTier.E3, EvidenceTier.E4}:
            raise ValueError("direct_share requires E3 or E4 evidence")
        if direct_share is not None and not 0 < direct_share < 1:
            raise ValueError("direct_share must be in (0, 1)")

        rng = np.random.default_rng(_stable_seed(entity_id, product, str(as_of), self.version))
        alpha, beta, calibration_count = self._posterior_parameters(product, sector, as_of)
        if direct_share is not None:
            concentration = 400.0 if evidence_tier == EvidenceTier.E3 else 800.0
            alpha += direct_share * concentration
            beta += (1.0 - direct_share) * concentration
        share = np.clip(rng.beta(alpha, beta, self.draws), 0.01, 0.99)
        prior_wallet = observed_activity / share if observed_activity else np.zeros(self.draws)
        wallet = prior_wallet.copy()

        anchor_active = anchor_range is not None
        anchor_weight = 0.0
        if anchor_range is not None:
            if len(anchor_range) != 3:
                raise ValueError("anchor_range must contain low, mode and high")
            low, mode, high = map(float, anchor_range)
            low = max(low, observed_activity)
            mode = max(mode, low)
            high = max(high, mode)
            anchor_draws = (
                np.full(self.draws, high)
                if high == low
                else rng.triangular(low, mode, high, self.draws)
            )
            anchor_weight = self._anchor_weight[evidence_tier]
            wallet = np.exp(
                (1.0 - anchor_weight) * np.log(np.maximum(prior_wallet, 1.0))
                + anchor_weight * np.log(np.maximum(anchor_draws, 1.0))
            )
            wallet = np.maximum(wallet, observed_activity)
            share = np.clip(observed_activity / np.maximum(wallet, 1.0), 0.0001, 0.99)

        if anchor_range is not None:
            # An anchor only reaches this method once the activation policy has
            # confirmed every fact behind it is approved, so "approved" here is
            # an enforced property rather than a label.
            bound_evidence = BoundEvidence(
                lower=float(anchor_range[0]),
                upper=float(anchor_range[2]),
                capacity=capacity,
                basis=(
                    "approved noisy measurement range "
                    f"({self.policy.activation_policy_version})"
                ),
            )
        else:
            prior = self.priors[product]
            declared_floor = max(
                self.policy.declared_share_floor,
                prior.mean - 2.5 * np.sqrt(prior.mean * (1 - prior.mean) / (prior.concentration + 1)),
            )
            bound_evidence = BoundEvidence(
                capacity=capacity,
                minimum_share=float(declared_floor),
                basis=(
                    "observed activity plus governed share floor "
                    f"{self.policy.declared_share_floor:.2f} — assumption-light, "
                    "deliberately wide"
                ),
            )

        bounds = self.bounds.calculate(observed_activity, as_of, bound_evidence)
        share_claim = ClaimClass.OBSERVED if direct_share is not None else ClaimClass.POSTERIOR
        if evidence_tier in {EvidenceTier.E3, EvidenceTier.E4}:
            calibration_status = CalibrationStatus.EMPIRICALLY_CALIBRATED
        elif evidence_tier == EvidenceTier.E2:
            calibration_status = CalibrationStatus.CLIENT_VALIDATED
        elif anchor_active:
            calibration_status = CalibrationStatus.PUBLICLY_ANCHORED
        else:
            calibration_status = CalibrationStatus.PRIOR_LED

        estimate = WalletEstimate(
            opportunity_id=opportunity_id,
            entity_id=entity_id,
            product=product,
            sector=sector,
            observed_activity=Money(
                amount=Decimal(str(observed_activity)),
                currency="ZAR",
                normalized_amount=Decimal(str(observed_activity)),
                normalized_currency="ZAR",
                source_unit="annual_activity",
                fx_policy_ref="identity-zar",
            ),
            identification_bounds=bounds,
            posterior_wallet=_interval(wallet, as_of, self.version, ClaimClass.POSTERIOR),
            share_interval=_interval(share, as_of, self.version, share_claim),
            share_claim=share_claim,
            evidence_tier=evidence_tier,
            calibration_status=calibration_status,
            diagnostics={
                "draws": self.draws,
                "posterior_alpha": alpha,
                "posterior_beta": beta,
                "calibration_observations": calibration_count,
                "anchor_active": anchor_active,
                "anchor_weight": anchor_weight,
                "fact_ids": list(fact_ids),
                "partial_identification_separate": True,
            },
            artifacts=ArtifactReference(
                model_version=self.version,
                dataset_version=dataset_version,
                prior_version=self.prior_version,
                transformation_version=self.transformation_version,
                measurement_policy_version=self.policy.version,
                schema_version="v1",
            ),
        )
        return estimate, wallet, share


def empirical_interval_coverage(truth: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    if not (truth.shape == lower.shape == upper.shape):
        raise ValueError("truth and interval arrays must have identical shapes")
    return float(np.mean((truth >= lower) & (truth <= upper)))


def sample_crps(draws: np.ndarray, truth: float) -> float:
    """Empirical CRPS for a univariate sample."""
    draws = np.asarray(draws, dtype=float)
    first = np.mean(np.abs(draws - truth))
    sorted_draws = np.sort(draws)
    n = len(sorted_draws)
    weights = 2 * np.arange(1, n + 1) - n - 1
    second = np.sum(weights * sorted_draws) / (n * n)
    return float(first - second)
