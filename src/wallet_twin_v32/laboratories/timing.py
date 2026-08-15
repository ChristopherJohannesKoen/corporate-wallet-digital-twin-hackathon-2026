"""Timing validation on client-held-out temporal splits.

Two things must both hold for a timing evaluation to mean anything, and using
either alone produces an optimistic number:

**Temporal split** — train on the past, test on the future. A random split lets
the model see a client's later behaviour while predicting their earlier
behaviour, which is leakage in the most direct sense.

**Client held out** — the test clients must not appear in training at all.
Splitting only on time still lets the model learn client-specific patterns and
then be scored on the same clients, so it measures memorisation rather than
generalisation to the next client the bank onboards.

Both are applied here, and the report states which is doing the work by also
computing the optimistic variants. A single number cannot show that; three can.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Dict, List, Sequence, Tuple

import numpy as np

from .compute import CPU

TIMING_LAB_VERSION = "v32-timing-temporal-split-1.0.0"
TIMING_HAZARD_LAB_VERSION = "v32-timing-hazard-recovery-2.0.1"
TIMING_COEFFICIENT_DECIMALS = 6
TIMING_PROBABILITY_DECIMALS = 5


def _quantize_float(value: float, decimal_places: int) -> float:
    """Quantize a computed value independently of the host BLAS reduction path."""
    quantum = Decimal(1).scaleb(-decimal_places)
    return float(Decimal(str(float(value))).quantize(quantum, rounding=ROUND_HALF_EVEN))


def _quantize_array(values: np.ndarray, decimal_places: int) -> np.ndarray:
    return np.fromiter(
        (_quantize_float(value, decimal_places) for value in values),
        dtype=float,
        count=len(values),
    )


def _stable_mean(values: np.ndarray) -> float:
    """Return an ordered, reproducible mean for governed output aggregation."""
    if len(values) == 0:
        raise ValueError("stable mean requires at least one value")
    return math.fsum(float(value) for value in values) / len(values)


@dataclass(frozen=True)
class SplitResult:
    split: str
    train_rows: int
    test_rows: int
    mae_months: float
    description: str


def _panel(seed: int, clients: int = 180, months: int = 24) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Synthetic client-month panel with a client-specific timing offset.

    The client effect is the point: it is what a leaky split lets the model
    memorise, so a panel without one could not demonstrate the difference.
    """
    rng = np.random.default_rng(seed)
    client_ids = np.repeat(np.arange(clients), months)
    month_index = np.tile(np.arange(months), clients)
    client_offset = rng.normal(0.0, 2.5, size=clients)[client_ids]
    seasonal = 1.5 * np.sin(2 * np.pi * month_index / 12.0)
    truth = 6.0 + client_offset + seasonal + rng.normal(0.0, 1.0, size=clients * months)
    return client_ids, month_index, truth


def _fit_predict(
    train_mask: np.ndarray,
    client_ids: np.ndarray,
    month_index: np.ndarray,
    truth: np.ndarray,
) -> float:
    """Fit a per-client mean with a global fallback, return test MAE.

    Deliberately simple. The comparison being made is between *splits*, and a
    more elaborate estimator would confound the two effects.
    """
    test_mask = ~train_mask
    global_mean = float(truth[train_mask].mean())

    per_client: Dict[int, float] = {}
    for client in np.unique(client_ids[train_mask]):
        per_client[int(client)] = float(truth[train_mask & (client_ids == client)].mean())

    predictions = np.array(
        [per_client.get(int(client), global_mean) for client in client_ids[test_mask]]
    )
    seasonal_adjustment = 1.5 * np.sin(2 * np.pi * month_index[test_mask] / 12.0)
    return float(np.mean(np.abs(truth[test_mask] - (predictions + seasonal_adjustment))))


def evaluate_splits(*, seed: int = 20260630) -> List[SplitResult]:
    """The governed split and the two optimistic variants, for comparison."""
    client_ids, month_index, truth = _panel(seed)
    rng = np.random.default_rng(seed + 1)
    clients = int(client_ids.max()) + 1
    held_out = set(rng.choice(clients, size=clients // 4, replace=False).tolist())
    cutoff = 18

    random_mask = rng.random(len(truth)) < 0.75
    temporal_mask = month_index < cutoff
    client_temporal_mask = temporal_mask & np.array(
        [int(client) not in held_out for client in client_ids]
    )

    return [
        SplitResult(
            "random",
            int(random_mask.sum()),
            int((~random_mask).sum()),
            _fit_predict(random_mask, client_ids, month_index, truth),
            "Optimistic. Leaks the future and the client; reported for contrast only.",
        ),
        SplitResult(
            "temporal-only",
            int(temporal_mask.sum()),
            int((~temporal_mask).sum()),
            _fit_predict(temporal_mask, client_ids, month_index, truth),
            "Still optimistic. Test clients appear in training, so it measures "
            "memorisation rather than generalisation.",
        ),
        SplitResult(
            "client-held-out-temporal",
            int(client_temporal_mask.sum()),
            int((~client_temporal_mask).sum()),
            _fit_predict(client_temporal_mask, client_ids, month_index, truth),
            "The governed split. Train on the past, test on unseen clients in "
            "the future.",
        ),
    ]


def timing_report(results: Sequence[SplitResult], as_of: date) -> Dict[str, object]:
    by_split = {item.split: item for item in results}
    governed = by_split["client-held-out-temporal"]
    optimism = governed.mae_months - by_split["random"].mae_months
    return {
        "lab_version": TIMING_LAB_VERSION,
        "device": CPU,
        "as_of": as_of.isoformat(),
        "governed_split": "client-held-out-temporal",
        "governed_mae_months": round(governed.mae_months, 6),
        "splits": [
            {
                "split": item.split,
                "train_rows": item.train_rows,
                "test_rows": item.test_rows,
                "mae_months": round(item.mae_months, 6),
                "description": item.description,
            }
            for item in results
        ],
        "optimism_of_a_random_split_months": round(optimism, 6),
        "why_both_conditions": (
            "A temporal split alone still lets the model be scored on clients it "
            "trained on. Reporting all three shows how much of the apparent "
            "accuracy came from leakage rather than from the model."
        ),
        "evidence_mode": "SYNTHETIC_REHEARSAL",
        "bank_meaning": (
            "Measured on a synthetic panel. No timing claim about real clients "
            "follows from it."
        ),
    }


def hazard_recovery_report(
    *, as_of: date, clients: int = 2_000, months: int = 36, seed: int = 20260630
) -> Dict[str, object]:
    """Recover a planted discrete-time hazard on held-out clients and future time.

    The generator includes drift, delayed/missing outcomes, censoring and label
    noise. It is a method test only; every output is SYNTHETIC_REHEARSAL.
    """
    from scipy.optimize import minimize
    from scipy.special import expit

    if clients < 2_000 or months < 36:
        raise ValueError("canonical timing rehearsal requires 2,000 clients and 36 months")
    rng = np.random.default_rng(seed)
    client_ids = np.repeat(np.arange(clients), months)
    month = np.tile(np.arange(months), clients)
    sector = np.repeat(rng.integers(0, 6, size=clients), months)
    relationship = np.repeat(rng.beta(2.5, 2.0, size=clients), months)
    magnitude = rng.lognormal(mean=0.0, sigma=0.7, size=clients * months)
    maturity = np.clip((month - 20) / 12 + rng.normal(0, 0.25, size=len(month)), 0, 1)
    seasonal = np.sin(2 * np.pi * month / 12)
    cash_peak = np.cos(2 * np.pi * (month + sector) / 12)
    recommendation_error = rng.random(len(month)) < 0.08
    features = np.column_stack(
        [np.log1p(magnitude), maturity, seasonal, relationship, cash_peak, recommendation_error]
    )
    planted = np.array([0.42, 0.85, 0.28, 0.36, 0.22, -0.55])
    drift = np.where(month >= 24, -0.32 * features[:, 0] + 0.18 * features[:, 2], 0.0)
    linear = -3.15 + features @ planted + drift + 0.08 * sector
    hazard = expit(linear)
    truth = rng.binomial(1, hazard).astype(float)

    # Operational defects are explicit: delayed events move one month, missing
    # labels become NaN, censoring removes the tail and label noise flips a few.
    delayed = rng.random(len(truth)) < 0.07
    observed = truth.copy()
    for client in range(clients):
        start = client * months
        for offset in range(months - 2, -1, -1):
            idx = start + offset
            if delayed[idx] and observed[idx] == 1:
                observed[idx] = 0
                observed[idx + 1] = 1
    label_noise = rng.random(len(observed)) < 0.03
    observed[label_noise] = 1 - observed[label_noise]
    missing = rng.random(len(observed)) < 0.05
    censored = month >= np.repeat(rng.integers(30, 36, size=clients), months)
    observed[missing | censored] = np.nan

    held_out_clients = set(rng.choice(clients, size=clients // 4, replace=False).tolist())
    held_out = np.array([int(client) in held_out_clients for client in client_ids])
    train = (~held_out) & (month < 24) & ~np.isnan(observed)
    test = held_out & (month >= 24) & (month <= 32) & ~np.isnan(observed)
    means = np.nanmean(features[train], axis=0)
    scales = np.nanstd(features[train], axis=0)
    scales[scales == 0] = 1.0
    x = (features - means) / scales
    x_design = np.column_stack([np.ones(len(x)), x])

    def objective(beta: np.ndarray) -> float:
        probability = np.clip(expit(x_design[train] @ beta), 1e-9, 1 - 1e-9)
        target = observed[train]
        return float(-np.sum(target * np.log(probability) + (1 - target) * np.log(1 - probability)))

    fitted = minimize(objective, np.zeros(x_design.shape[1]), method="L-BFGS-B")
    fitted_coefficients = _quantize_array(fitted.x, TIMING_COEFFICIENT_DECIMALS)
    monthly = np.clip(expit(x_design @ fitted_coefficients), 1e-9, 1 - 1e-9)

    horizon_metrics: Dict[str, object] = {}
    for horizon_months, label in ((1, "30d"), (2, "60d"), (3, "90d")):
        future = np.full(len(observed), np.nan)
        for client in held_out_clients:
            start = client * months
            values = observed[start : start + months]
            for offset in range(months - horizon_months + 1):
                window = values[offset : offset + horizon_months]
                if not np.isnan(window).any():
                    future[start + offset] = float(np.max(window))
        mask = test & ~np.isnan(future)
        probability = _quantize_array(
            1 - np.power(1 - monthly[mask], horizon_months),
            TIMING_PROBABILITY_DECIMALS,
        )
        target = future[mask]
        brier = math.fsum(
            (float(predicted) - float(actual)) ** 2
            for predicted, actual in zip(probability, target, strict=True)
        ) / len(target)
        log_loss = -math.fsum(
            float(actual) * math.log(float(predicted))
            + (1 - float(actual)) * math.log1p(-float(predicted))
            for predicted, actual in zip(probability, target, strict=True)
        ) / len(target)
        bins: List[Dict[str, object]] = []
        for lower in np.linspace(0, 0.8, 5):
            upper = lower + 0.2
            in_bin = (probability >= lower) & (probability < upper if upper < 1 else probability <= upper)
            if in_bin.any():
                bins.append(
                    {
                        "predicted": round(_stable_mean(probability[in_bin]), 6),
                        "observed": round(_stable_mean(target[in_bin]), 6),
                        "count": int(in_bin.sum()),
                    }
                )
        horizon_metrics[label] = {
            "rows": int(mask.sum()),
            "brier": round(brier, 6),
            "log_loss": round(log_loss, 6),
            "calibration": bins,
        }

    fitted_signs = np.sign(fitted_coefficients[1:]).astype(int)
    planted_signs = np.sign(planted).astype(int)
    return {
        "lab_version": TIMING_HAZARD_LAB_VERSION,
        "numeric_policy": {
            "coefficient_decimals": TIMING_COEFFICIENT_DECIMALS,
            "probability_decimals": TIMING_PROBABILITY_DECIMALS,
            "aggregation": "ORDERED_MATH_FSUM",
        },
        "as_of": as_of.isoformat(),
        "evidence_mode": "SYNTHETIC_REHEARSAL",
        "clients": clients,
        "months": months,
        "rows": int(len(observed)),
        "train_rows": int(train.sum()),
        "test_rows": int(test.sum()),
        "client_held_out": True,
        "temporal_split": True,
        "injections": {
            "concept_drift": True,
            "sector_heterogeneity": True,
            "delayed_outcomes": int(delayed.sum()),
            "missing_outcomes": int(missing.sum()),
            "censored_rows": int(censored.sum()),
            "label_noise": int(label_noise.sum()),
            "incorrect_recommendations": int(recommendation_error.sum()),
        },
        "optimizer_converged": bool(fitted.success),
        "coefficient_direction_recovery": {
            "recovered": int(np.sum(fitted_signs == planted_signs)),
            "total": int(len(planted)),
            "all_recovered": bool(np.all(fitted_signs == planted_signs)),
        },
        "horizons": horizon_metrics,
        "bank_meaning": "The planted relationship was tested in a synthetic laboratory. It is not evidence about banker response behavior.",
    }


__all__ = [
    "TIMING_HAZARD_LAB_VERSION",
    "TIMING_LAB_VERSION",
    "SplitResult",
    "evaluate_splits",
    "hazard_recovery_report",
    "timing_report",
]
