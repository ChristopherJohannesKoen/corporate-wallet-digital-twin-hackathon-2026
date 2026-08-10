from __future__ import annotations

import math
from datetime import date
from typing import Sequence

import numpy as np
from scipy.stats import norm

from .contracts import ChangePointSignal, LeakageAlarm, ShadowWalletReconstruction


class BayesianChangePointDetector:
    """Online run-length filter with a Gaussian conjugate predictive model."""

    def __init__(
        self, expected_run_months: float = 12.0, max_run_length: int = 48
    ) -> None:
        self.hazard = 1.0 / expected_run_months
        self.max_run_length = max_run_length

    def detect(
        self,
        opportunity_id: str,
        entity_id: str,
        product: str,
        values: Sequence[float],
        as_of: date,
    ) -> ChangePointSignal:
        raw = np.asarray(values, dtype=float)
        if raw.size < 8:
            raise ValueError("at least eight observations are required")
        transformed = np.log1p(np.maximum(raw, 0.0))
        global_mean = float(np.median(transformed[: min(12, len(transformed))]))
        variance = float(max(np.var(transformed), 0.03**2))
        prior_variance = variance * 4.0
        run_probs = np.array([1.0])
        means = np.array([global_mean])
        counts = np.array([0.0])
        change_probabilities: list[float] = []

        for value in transformed:
            predictive_variance = variance * (1.0 + 1.0 / np.maximum(counts + 1.0, 1.0))
            growth_likelihood = norm.pdf(
                value, loc=means, scale=np.sqrt(predictive_variance)
            )
            reset_likelihood = float(
                norm.pdf(
                    value, loc=global_mean, scale=math.sqrt(variance + prior_variance)
                )
            )
            reset_mass = self.hazard * reset_likelihood
            growth_mass = (1.0 - self.hazard) * run_probs * growth_likelihood
            normalizer = reset_mass + growth_mass.sum()
            probability = float(reset_mass / max(normalizer, 1e-300))
            change_probabilities.append(probability)

            next_probs = np.concatenate(
                [[probability], growth_mass / max(normalizer, 1e-300)]
            )
            next_means = np.concatenate(
                [[global_mean], (means * counts + value) / (counts + 1.0)]
            )
            next_counts = np.concatenate([[0.0], counts + 1.0])
            if len(next_probs) > self.max_run_length + 1:
                next_probs = next_probs[: self.max_run_length + 1]
                next_means = next_means[: self.max_run_length + 1]
                next_counts = next_counts[: self.max_run_length + 1]
            run_probs = next_probs / next_probs.sum()
            means, counts = next_means, next_counts

        recent = transformed[-3:]
        previous = transformed[-9:-3]
        signed_shift = float(
            np.expm1(recent.mean()) / max(np.expm1(previous.mean()), 1e-9) - 1.0
        )
        current = float(change_probabilities[-1])
        recent_peak = float(max(change_probabilities[-6:]))
        monthly_event = min(0.95, max(current, recent_peak * 0.65))
        p30 = monthly_event
        p60 = 1.0 - (1.0 - monthly_event) ** 2
        p90 = 1.0 - (1.0 - monthly_event) ** 3
        return ChangePointSignal(
            opportunity_id=opportunity_id,
            entity_id=entity_id,
            product=product,
            as_of=as_of,
            current_probability=current,
            recent_peak_probability=recent_peak,
            run_length_mode_months=int(np.argmax(run_probs)),
            signed_level_shift=signed_shift,
            probability_30d=p30,
            probability_60d=p60,
            probability_90d=p90,
            method="Bayesian online run-length filtering with Gaussian predictive densities",
            calibration_status="REPRESENTATIVE_TEMPORAL_REPLAY_NOT_RM_OUTCOME_CALIBRATED",
        )


def leakage_alarm(
    signal: ChangePointSignal, shadow: ShadowWalletReconstruction
) -> LeakageAlarm:
    decline = min(1.0, max(0.0, -signal.signed_level_shift))
    probability = min(1.0, signal.recent_peak_probability * (0.35 + 1.65 * decline))
    at_risk = shadow.latent_external_wallet.median * decline * probability
    severity = (
        "HIGH" if probability >= 0.6 else "MEDIUM" if probability >= 0.3 else "LOW"
    )
    reasons = ["RECENT_CHANGE_POINT"]
    reasons.append(
        "OBSERVED_ACTIVITY_DECLINE"
        if decline > 0.05
        else "NO_MATERIAL_OBSERVED_DECLINE"
    )
    reasons.append("EXTERNAL_WALLET_RECONSTRUCTED_NOT_MEASURED")
    return LeakageAlarm(
        opportunity_id=signal.opportunity_id,
        entity_id=signal.entity_id,
        product=signal.product,
        alarm_probability=probability,
        expected_external_flow_at_risk_zar=max(0.0, at_risk),
        observed_level_decline=decline,
        severity=severity,
        reason_codes=reasons,
    )
