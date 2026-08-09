from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import numpy as np


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def percentile_rank(values: list[float], value: float) -> float:
    if not values:
        return 0.5
    ordered = sorted(values)
    return sum(v <= value for v in ordered) / len(ordered)


def stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32 - 1)


def money_quantiles(samples: np.ndarray) -> dict[str, float]:
    p10, p50, p90 = np.quantile(samples, [0.10, 0.50, 0.90])
    return {"p10": float(p10), "p50": float(p50), "p90": float(p90)}


@dataclass
class OpportunityInput:
    entity_id: str
    product: str
    observed_activity: float
    recurrence: float
    relationship_breadth: float
    scale_percentile: float
    trend: float
    data_quality: float
    evidence_coverage: float
    fit: float
    timing: float
    share_prior_mean: float
    share_prior_concentration: float
    economic_rate_bps: tuple[float, float, float]
    target_share: tuple[float, float, float]
    anchor_low: float | None = None
    anchor_base: float | None = None
    anchor_high: float | None = None
    anchor_weight: float = 0.0
    anchor_name: str | None = None
    anchor_fact_ids: tuple[str, ...] = ()
    evidence_coverage_before_anchor: float | None = None


def estimate_opportunity(
    inp: OpportunityInput,
    draws: int = 2_000,
    seed_suffix: str = "base",
) -> tuple[dict[str, Any], np.ndarray]:
    """Estimate a contestable wallet while preserving A=qT non-identification.

    The share prior is modestly conditioned by relationship signals. It is not
    presented as a causal estimate. All stochastic outputs are reproducible.
    """

    rng = np.random.default_rng(stable_seed(inp.entity_id, inp.product, "wallet-v2", seed_suffix))

    adjusted_mean = clamp(
        inp.share_prior_mean
        + 0.08 * (inp.relationship_breadth - 0.60)
        + 0.07 * (inp.recurrence - 0.50)
        + 0.04 * (inp.scale_percentile - 0.50),
        0.08,
        0.78,
    )
    concentration = max(4.0, inp.share_prior_concentration * (0.70 + 0.60 * inp.recurrence) * inp.data_quality)
    alpha = adjusted_mean * concentration
    beta = (1.0 - adjusted_mean) * concentration
    prior_share = np.clip(rng.beta(alpha, beta, draws), 0.03, 0.95)
    prior_total_activity = inp.observed_activity / prior_share if inp.observed_activity > 0 else np.zeros(draws)

    has_anchor = bool(
        inp.anchor_low is not None
        and inp.anchor_base is not None
        and inp.anchor_high is not None
        and inp.anchor_high > 0
        and inp.anchor_weight > 0
    )
    if has_anchor:
        anchor_left = max(inp.observed_activity, float(inp.anchor_low))
        anchor_mode = max(anchor_left, float(inp.anchor_base))
        anchor_right = max(anchor_mode, float(inp.anchor_high))
        anchor_activity = (
            np.full(draws, anchor_right)
            if anchor_right == anchor_left
            else rng.triangular(anchor_left, anchor_mode, anchor_right, size=draws)
        )
        # Precision-weighted geometric pooling keeps the prior visible while
        # letting audited accounting anchors materially constrain its spread.
        weight = clamp(inp.anchor_weight, 0.0, 0.95)
        total_activity = np.exp(
            (1.0 - weight) * np.log(np.maximum(prior_total_activity, 1.0))
            + weight * np.log(np.maximum(anchor_activity, 1.0))
        )
        total_activity = np.maximum(total_activity, inp.observed_activity)
        share = np.clip(inp.observed_activity / np.maximum(total_activity, 1.0), 0.0001, 0.95)
    else:
        total_activity = prior_total_activity
        share = prior_share

    target = (
        np.full(draws, inp.target_share[0])
        if inp.target_share[0] == inp.target_share[2]
        else rng.triangular(*inp.target_share, size=draws)
    )
    rates = (
        np.full(draws, inp.economic_rate_bps[0])
        if inp.economic_rate_bps[0] == inp.economic_rate_bps[2]
        else rng.triangular(*inp.economic_rate_bps, size=draws)
    ) / 10_000.0
    contestable_activity = total_activity * np.maximum(target - share, 0.0)
    revenue_gap = contestable_activity * rates

    coverage_before = (
        inp.evidence_coverage
        if inp.evidence_coverage_before_anchor is None
        else inp.evidence_coverage_before_anchor
    )
    confidence_before = clamp(
        0.40 * coverage_before
        + 0.20 * inp.data_quality
        + 0.15 * inp.recurrence
        + 0.10 * (1.0 - min(1.0, abs(inp.trend) / 0.50)),
        0.0,
        1.0,
    )
    confidence_with_evidence = clamp(
        0.40 * inp.evidence_coverage
        + 0.20 * inp.data_quality
        + 0.15 * inp.recurrence
        + 0.10 * (1.0 - min(1.0, abs(inp.trend) / 0.50)),
        0.0,
        1.0,
    )
    confidence = clamp(confidence_with_evidence + (0.20 * inp.anchor_weight if has_anchor else 0.0), 0.0, 1.0)
    priority_samples = revenue_gap * confidence * inp.fit * inp.timing
    share_q = money_quantiles(share)
    total_q = money_quantiles(total_activity)
    prior_total_q = money_quantiles(prior_total_activity)
    gap_q = money_quantiles(revenue_gap)
    contestable_q = money_quantiles(contestable_activity)

    # A defensible identification envelope: activity cannot be below observed;
    # the upper end corresponds to the 5th percentile of the declared share prior.
    if has_anchor:
        identification = {
            "lower": max(inp.observed_activity, float(inp.anchor_low)),
            "upper": max(inp.observed_activity, float(inp.anchor_high)),
            "basis": f"Audited public anchor range pooled with the explicit share prior: {inp.anchor_name}",
        }
    else:
        q05, q95 = np.quantile(share, [0.05, 0.95])
        identification = {
            "lower": float(inp.observed_activity / q95) if inp.observed_activity else 0.0,
            "upper": float(inp.observed_activity / q05) if inp.observed_activity else 0.0,
            "basis": "Observed activity divided by the 95th/5th percentile of the explicit share prior",
        }

    prior_relative_width = (
        (prior_total_q["p90"] - prior_total_q["p10"]) / prior_total_q["p50"]
        if prior_total_q["p50"]
        else 0.0
    )
    anchored_relative_width = (
        (total_q["p90"] - total_q["p10"]) / total_q["p50"] if total_q["p50"] else 0.0
    )
    interval_reduction = (
        1.0 - anchored_relative_width / prior_relative_width if has_anchor and prior_relative_width else 0.0
    )

    label = "High" if confidence >= 0.75 else "Medium" if confidence >= 0.55 else "Low"
    result = {
        "entity_id": inp.entity_id,
        "product": inp.product,
        "observed_activity_zar": inp.observed_activity,
        "need_propensity": clamp(0.45 + 0.35 * inp.recurrence + 0.15 * inp.fit + 0.05 * max(-0.5, min(0.5, inp.trend)), 0.0, 0.99),
        "current_share": share_q,
        "total_wallet_zar": total_q,
        "partial_identification_zar": identification,
        "contestable_activity_zar": contestable_q,
        "revenue_gap_zar": gap_q,
        "confidence": confidence,
        "confidence_label": label,
        "fit_score": inp.fit,
        "timing_score": inp.timing,
        "priority_score": float(np.median(priority_samples)),
        "recurrence": inp.recurrence,
        "trend": inp.trend,
        "anchor_impact": {
            "active": has_anchor,
            "anchor_name": inp.anchor_name,
            "fact_ids": list(inp.anchor_fact_ids),
            "prior_only_total_wallet_zar": prior_total_q,
            "anchored_total_wallet_zar": total_q,
            "prior_relative_interval_width": prior_relative_width,
            "anchored_relative_interval_width": anchored_relative_width,
            "relative_interval_width_reduction": interval_reduction,
            "confidence_before": confidence_before,
            "confidence_after": confidence,
            "confidence_lift": confidence - confidence_before,
        },
        "assumptions": {
            "share_prior_mean": inp.share_prior_mean,
            "share_prior_concentration": inp.share_prior_concentration,
            "target_share": {"low": inp.target_share[0], "base": inp.target_share[1], "high": inp.target_share[2]},
            "economic_rate_bps": {"low": inp.economic_rate_bps[0], "base": inp.economic_rate_bps[1], "high": inp.economic_rate_bps[2]},
            "public_anchor_weight": inp.anchor_weight if has_anchor else 0.0,
        },
        "provenance": {
            "observed_activity_zar": "observed",
            "current_share": "model-estimated",
            "total_wallet_zar": "model-estimated",
            "partial_identification_zar": "assumption-bounded",
            "revenue_gap_zar": "model-estimated",
            "target_share": "assumption",
            "economic_rate_bps": "assumption",
            "public_anchor": "audited-public-facts plus declared transformation assumptions" if has_anchor else "not available",
        },
    }
    return result, priority_samples


def seasonal_naive_backtest(monthly: list[float], season: int = 12) -> dict[str, float | int | None]:
    if len(monthly) <= season:
        return {"n": 0, "wape": None, "mae": None, "rmse": None}
    actual = np.asarray(monthly[season:], dtype=float)
    predicted = np.asarray(monthly[:-season], dtype=float)
    errors = actual - predicted
    denominator = float(np.sum(np.abs(actual)))
    return {
        "n": int(len(actual)),
        "wape": float(np.sum(np.abs(errors)) / denominator) if denominator else None,
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(errors**2))),
    }


def synthetic_recovery(seed: int = 20260807, n: int = 2_000) -> dict[str, float | int]:
    """Checks whether declared intervals recover latent T under their own DGP.

    This is a calibration experiment, not evidence that the real-world prior is true.
    """

    rng = np.random.default_rng(seed)
    true_total = rng.lognormal(mean=18.0, sigma=0.8, size=n)
    true_share = rng.beta(4.0, 8.0, size=n)
    observed = true_total * true_share
    draws = rng.beta(4.0, 8.0, size=(n, 800))
    inferred = observed[:, None] / np.clip(draws, 0.03, 0.95)
    p10 = np.quantile(inferred, 0.10, axis=1)
    p90 = np.quantile(inferred, 0.90, axis=1)
    p50 = np.quantile(inferred, 0.50, axis=1)
    coverage = np.mean((true_total >= p10) & (true_total <= p90))
    rank_corr = float(np.corrcoef(np.argsort(np.argsort(true_total)), np.argsort(np.argsort(p50)))[0, 1])
    median_ape = float(np.median(np.abs(p50 - true_total) / true_total))
    return {"n": n, "p10_p90_coverage": float(coverage), "rank_correlation": rank_corr, "median_absolute_percentage_error": median_ape}


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


def growth_rate(current: float, prior: float) -> float:
    if prior <= 0:
        return 0.0
    return clamp(current / prior - 1.0, -1.0, 2.0)


def weighted_mean(values: list[tuple[float, float]]) -> float:
    denominator = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / denominator if denominator else math.nan
