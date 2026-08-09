from __future__ import annotations

import json
import math
import os
import zipfile
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import norm, spearmanr

from .contracts import CalibrationObservation, CuratedMetadata, EvidenceTier, QualityStatus
from .fixtures import ROOT, build_fixture
from .timing import TimingService
from .wallet_model import DEFAULT_PRIORS, HierarchicalWalletModel, sample_crps


PRODUCTS = tuple(DEFAULT_PRIORS)
SECTORS = ("mining", "consumer", "insurance", "real_estate", "tech", "telecoms", "industrials_pharma")
RAW_ZIP = Path(os.environ.get("SYNBANK_DATA_ZIP", ROOT / "ref" / "Data Sets" / "Data.zip")).expanduser().resolve()


def _metadata(key: str, as_of: date) -> CuratedMetadata:
    timestamp = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc)
    import hashlib

    return CuratedMetadata(
        business_key=key,
        source_system_key=f"synthetic-known-truth:{key}",
        event_time=timestamp,
        valid_from=timestamp,
        source_hash=hashlib.sha256(key.encode("utf-8")).hexdigest(),
        transformation_version="known-truth-generator-1.0.0",
        quality_status=QualityStatus.VALID,
        data_owner="V2 validation laboratory",
        entitlement_domain="synthetic-validation",
    )


def _summary(values: Sequence[float]) -> dict:
    array = np.asarray(values, dtype=float)
    return {
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p05": float(np.quantile(array, 0.05)),
        "p95": float(np.quantile(array, 0.95)),
    }


def synthetic_calibration_lab(entity_count: int = 240, seed: int = 20260809) -> dict:
    """Known-truth experiment; results can validate mechanics, never empirical client accuracy."""
    rng = np.random.default_rng(seed)
    as_of = date(2026, 6, 30)
    rows: List[dict] = []
    sector_shift = {sector: rng.normal(0, 0.22, len(PRODUCTS)) for sector in SECTORS}
    product_scale = dict(zip(PRODUCTS, (8.5e9, 7.0e9, 2.2e9, 3.0e9, 1.4e9)))
    for entity_index in range(entity_count):
        sector = SECTORS[entity_index % len(SECTORS)]
        size = float(rng.lognormal(0.0, 0.75))
        for product_index, product in enumerate(PRODUCTS):
            prior = DEFAULT_PRIORS[product]
            logit = math.log(prior.mean / (1 - prior.mean)) + sector_shift[sector][product_index]
            mean = 1 / (1 + math.exp(-logit))
            concentration = max(5.0, prior.concentration * 0.85)
            truth_share = float(rng.beta(mean * concentration, (1 - mean) * concentration))
            truth_wallet = float(product_scale[product] * size * rng.lognormal(0, 0.28))
            observed = truth_wallet * truth_share
            anchor_mid = truth_wallet * float(rng.lognormal(0, 0.18))
            rows.append({
                "entity_id": f"S{entity_index:04d}",
                "sector": sector,
                "product": product,
                "truth_share": truth_share,
                "truth_wallet": truth_wallet,
                "observed": observed,
                "anchor": (max(observed, anchor_mid * 0.72), max(observed, anchor_mid), max(observed, anchor_mid * 1.32)),
                "size": size,
            })

    frame = pd.DataFrame(rows)
    log_size = np.log(frame["size"].to_numpy())
    select_logit = -1.05 + 0.55 * (log_size - log_size.mean()) / log_size.std() + 1.1 * (frame["truth_share"].to_numpy() - 0.30)
    selection_probability = np.clip(1 / (1 + np.exp(-select_logit)), 0.08, 0.80)
    selected = rng.random(len(frame)) < selection_probability
    # Keep calibration and evaluation entities disjoint to avoid relationship leakage.
    panel_entities = set(frame.loc[selected, "entity_id"].sample(frac=0.72, random_state=seed).tolist())
    calibration = frame[frame.entity_id.isin(panel_entities)].copy()
    holdout = frame[~frame.entity_id.isin(panel_entities)].copy()
    calibration["selection_probability"] = selection_probability[calibration.index]

    weighted_observations = []
    unweighted_observations = []
    for index, row in calibration.iterrows():
        base = dict(
            observation_id=f"CAL-{index}", entity_id=row["entity_id"], product=row["product"], sector=row["sector"],
            measured_share=float(row["truth_share"]), total_wallet=float(row["truth_wallet"]), tier=EvidenceTier.E3,
            as_of=as_of, metadata=_metadata(f"cal-{index}", as_of),
        )
        clipped_weight = min(6.0, 1.0 / float(row.selection_probability))
        weighted_observations.append(CalibrationObservation(selection_weight=clipped_weight, **base))
        unweighted_observations.append(CalibrationObservation(selection_weight=1.0, **base))

    models = {
        "frozen_prior": HierarchicalWalletModel(draws=1_200),
        "biased_panel_unweighted": HierarchicalWalletModel(unweighted_observations, draws=1_200),
        "selection_weighted_panel": HierarchicalWalletModel(weighted_observations, draws=1_200),
    }
    metrics: Dict[str, dict] = {}
    predictions: Dict[str, List[dict]] = defaultdict(list)
    for model_name, model in models.items():
        for index, row in holdout.iterrows():
            estimate, wallet_draws, share_draws = model.estimate(
                opportunity_id=f"SYN-{index}", entity_id=row["entity_id"], product=row["product"], sector=row["sector"],
                observed_activity=float(row["observed"]), as_of=as_of, evidence_tier=EvidenceTier.E0,
                dataset_version="synthetic-known-truth-1.0.0",
            )
            predictions[model_name].append({
                "entity_id": row["entity_id"], "sector": row["sector"], "product": row["product"],
                "truth_share": row["truth_share"], "truth_wallet": row["truth_wallet"],
                "share_lower": estimate.share_interval.lower, "share_median": estimate.share_interval.median, "share_upper": estimate.share_interval.upper,
                "wallet_lower": estimate.posterior_wallet.lower, "wallet_median": estimate.posterior_wallet.median, "wallet_upper": estimate.posterior_wallet.upper,
                "share_crps": sample_crps(share_draws, float(row.truth_share)),
                "wallet_crps_scaled": sample_crps(wallet_draws / row["truth_wallet"], 1.0),
            })

    # Isolate the incremental effect of E1 anchors over the strongest panel model.
    anchor_predictions = []
    anchored_model = models["selection_weighted_panel"]
    for index, row in holdout.iterrows():
        estimate, wallet_draws, share_draws = anchored_model.estimate(
            opportunity_id=f"SYN-A-{index}", entity_id=row["entity_id"], product=row["product"], sector=row["sector"],
            observed_activity=float(row["observed"]), as_of=as_of, evidence_tier=EvidenceTier.E1,
            anchor_range=row["anchor"], fact_ids=(f"SYN-ANCHOR-{index}",), dataset_version="synthetic-known-truth-1.0.0",
        )
        anchor_predictions.append({
            "entity_id": row["entity_id"], "sector": row["sector"], "product": row["product"],
            "truth_share": row["truth_share"], "truth_wallet": row["truth_wallet"],
            "share_lower": estimate.share_interval.lower, "share_median": estimate.share_interval.median, "share_upper": estimate.share_interval.upper,
            "wallet_lower": estimate.posterior_wallet.lower, "wallet_median": estimate.posterior_wallet.median, "wallet_upper": estimate.posterior_wallet.upper,
            "share_crps": sample_crps(share_draws, float(row.truth_share)),
            "wallet_crps_scaled": sample_crps(wallet_draws / row["truth_wallet"], 1.0),
        })
    predictions["selection_weighted_plus_e1_anchor"] = anchor_predictions

    def score(items: List[dict]) -> dict:
        scored = pd.DataFrame(items)
        share_covered = (scored.truth_share >= scored.share_lower) & (scored.truth_share <= scored.share_upper)
        wallet_covered = (scored.truth_wallet >= scored.wallet_lower) & (scored.truth_wallet <= scored.wallet_upper)
        product_metrics = {}
        for product, group in scored.groupby("product"):
            product_metrics[product] = {
                "n": len(group),
                "share_90_coverage": float(((group.truth_share >= group.share_lower) & (group.truth_share <= group.share_upper)).mean()),
                "wallet_90_coverage": float(((group.truth_wallet >= group.wallet_lower) & (group.truth_wallet <= group.wallet_upper)).mean()),
                "share_bias": float((group.share_median - group.truth_share).mean()),
            }
        rank_correlations = []
        for _, group in scored.groupby("entity_id"):
            truth_gap = group.truth_wallet * np.maximum(0.40 - group.truth_share, 0)
            estimated_gap = group.wallet_median * np.maximum(0.40 - group.share_median, 0)
            corr = spearmanr(truth_gap, estimated_gap).statistic
            if np.isfinite(corr):
                rank_correlations.append(float(corr))
        return {
            "n_holdout_records": len(scored),
            "share_90_coverage": float(share_covered.mean()),
            "wallet_90_coverage": float(wallet_covered.mean()),
            "share_bias": float((scored.share_median - scored.truth_share).mean()),
            "share_crps": float(scored.share_crps.mean()),
            "wallet_scaled_crps": float(scored.wallet_crps_scaled.mean()),
            "median_share_interval_width": float((scored.share_upper - scored.share_lower).median()),
            "median_wallet_relative_interval_width": float(((scored.wallet_upper - scored.wallet_lower) / scored.truth_wallet).median()),
            "mean_within_client_rank_spearman": float(np.mean(rank_correlations)),
            "by_product": product_metrics,
        }

    for name, values in predictions.items():
        metrics[name] = score(values)

    def conformal_audit(items: List[dict]) -> dict:
        """Split-conformal widening audit on entities never used for model fitting."""
        scored = pd.DataFrame(items).copy()
        entities = sorted(scored.entity_id.unique())
        calibration_entities = set(entities[::2])
        calibration = scored[scored.entity_id.isin(calibration_entities)]
        evaluation = scored[~scored.entity_id.isin(calibration_entities)].copy()

        def interval_audit(prefix: str, truth_column: str) -> dict:
            lower = calibration[f"{prefix}_lower"].to_numpy(dtype=float)
            median = calibration[f"{prefix}_median"].to_numpy(dtype=float)
            upper = calibration[f"{prefix}_upper"].to_numpy(dtype=float)
            truth = calibration[truth_column].to_numpy(dtype=float)
            scale = np.maximum(np.maximum(median - lower, upper - median), 1e-9)
            scores = np.maximum.reduce(((lower - truth) / scale, (truth - upper) / scale, np.zeros(len(truth))))
            level = min(1.0, math.ceil((len(scores) + 1) * 0.90) / len(scores))
            quantile = float(np.quantile(scores, level, method="higher"))
            factor = 1.0 + max(0.0, quantile)
            eval_lower = evaluation[f"{prefix}_median"] - factor * (
                evaluation[f"{prefix}_median"] - evaluation[f"{prefix}_lower"]
            )
            eval_upper = evaluation[f"{prefix}_median"] + factor * (
                evaluation[f"{prefix}_upper"] - evaluation[f"{prefix}_median"]
            )
            raw_covered = (
                (evaluation[truth_column] >= evaluation[f"{prefix}_lower"])
                & (evaluation[truth_column] <= evaluation[f"{prefix}_upper"])
            )
            covered = (evaluation[truth_column] >= eval_lower) & (evaluation[truth_column] <= eval_upper)
            segment_coverage = {}
            for sector, group in evaluation.assign(_covered=covered).groupby("sector"):
                segment_coverage[sector] = {"n": len(group), "coverage_90": float(group._covered.mean())}
            return {
                "calibration_records": len(calibration),
                "evaluation_records": len(evaluation),
                "conformal_scale_factor": factor,
                "raw_coverage_90": float(raw_covered.mean()),
                "conformal_coverage_90": float(covered.mean()),
                "median_width_increase": float(
                    np.median(eval_upper - eval_lower)
                    / max(np.median(evaluation[f"{prefix}_upper"] - evaluation[f"{prefix}_lower"]), 1e-9)
                    - 1.0
                ),
                "by_sector": segment_coverage,
            }

        return {
            "status": "SYNTHETIC_SPLIT_CONFORMAL_AUDIT",
            "production_claim_allowed": False,
            "entity_disjoint_from_model_fit": True,
            "calibration_evaluation_entity_disjoint": True,
            "share": interval_audit("share", "truth_share"),
            "wallet": interval_audit("wallet", "truth_wallet"),
        }

    conformal = conformal_audit(predictions["selection_weighted_plus_e1_anchor"])
    prior_crps = metrics["frozen_prior"]["share_crps"]
    weighted_crps = metrics["selection_weighted_panel"]["share_crps"]
    prior_width = metrics["selection_weighted_panel"]["median_wallet_relative_interval_width"]
    anchor_width = metrics["selection_weighted_plus_e1_anchor"]["median_wallet_relative_interval_width"]
    return {
        "status": "SYNTHETIC_KNOWN_TRUTH_ONLY",
        "production_claim_allowed": False,
        "seed": seed,
        "entities": entity_count,
        "records": len(frame),
        "panel_entities": len(panel_entities),
        "holdout_entities": holdout.entity_id.nunique(),
        "selection_weight_policy": "inverse estimated inclusion probability, clipped at 6.0",
        "metrics": metrics,
        "comparisons": {
            "selection_weighted_share_crps_improvement_vs_frozen_prior": float((prior_crps - weighted_crps) / prior_crps),
            "e1_anchor_median_wallet_interval_narrowing": float((prior_width - anchor_width) / prior_width),
            "e1_anchor_coverage_preserved": metrics["selection_weighted_plus_e1_anchor"]["wallet_90_coverage"] >= 0.85,
        },
        "split_conformal_audit": conformal,
        "stress_tests": {
            "selection_bias": {
                "unweighted_share_crps": metrics["biased_panel_unweighted"]["share_crps"],
                "weighted_share_crps": metrics["selection_weighted_panel"]["share_crps"],
            },
            "missing_public_anchor": {
                "unanchored_wallet_coverage_90": metrics["selection_weighted_panel"]["wallet_90_coverage"],
                "anchored_wallet_coverage_90": metrics["selection_weighted_plus_e1_anchor"]["wallet_90_coverage"],
                "anchored_interval_narrowing": float((prior_width - anchor_width) / prior_width),
            },
        },
        "gate_interpretation": "Mechanics can be assessed; E3 portfolio calibration gate remains open because the truth and panel are synthetic.",
    }


def _aggregate_historical(zip_path: Path = RAW_ZIP) -> Tuple[pd.DataFrame, dict]:
    parts: List[pd.DataFrame] = []
    raw_counts: Dict[str, int] = {}
    with zipfile.ZipFile(zip_path) as archive:
        transaction_groups = []
        liquidity_groups = []
        transaction_rows = 0
        for chunk in pd.read_csv(
            archive.open("transactional_banking.csv"),
            usecols=["transaction_id", "entity_id", "sector", "date", "direction", "amount_zar"],
            parse_dates=["date"], chunksize=250_000,
        ):
            transaction_rows += len(chunk)
            chunk = chunk.drop_duplicates("transaction_id")
            chunk["month"] = chunk.date.dt.to_period("M").astype(str)
            chunk["product"] = np.where(chunk.direction.eq("inbound"), "Collections", "Payments")
            transaction_groups.append(chunk.groupby(["entity_id", "sector", "month", "product"], as_index=False).amount_zar.sum())
            chunk["signed"] = np.where(chunk.direction.eq("inbound"), chunk.amount_zar, -chunk.amount_zar)
            liquidity_groups.append(chunk.groupby(["entity_id", "sector", "month"], as_index=False).signed.sum())
        tx = pd.concat(transaction_groups).groupby(["entity_id", "sector", "month", "product"], as_index=False).amount_zar.sum()
        liq = pd.concat(liquidity_groups).groupby(["entity_id", "sector", "month"], as_index=False).signed.sum()
        liq["amount_zar"] = liq.signed.abs()
        liq["product"] = "Liquidity"
        parts.extend([tx[["entity_id", "sector", "month", "product", "amount_zar"]], liq[["entity_id", "sector", "month", "product", "amount_zar"]]])
        raw_counts["transactional_banking"] = transaction_rows

        for filename, product, id_col, amount_col in (
            ("cross_border_payments.csv", "Cross-border FX", "transaction_id", "value_zar"),
            ("trade_finance.csv", "Trade finance", "instrument_id", "value_zar"),
        ):
            data = pd.read_csv(
                archive.open(filename), usecols=[id_col, "entity_id", "sector", "date", amount_col], parse_dates=["date"]
            )
            raw_counts[filename.removesuffix(".csv")] = len(data)
            data = data.drop_duplicates(id_col)
            data["month"] = data.date.dt.to_period("M").astype(str)
            data["product"] = product
            data = data.rename(columns={amount_col: "amount_zar"})
            parts.append(data.groupby(["entity_id", "sector", "month", "product"], as_index=False).amount_zar.sum())
    monthly = pd.concat(parts).groupby(["entity_id", "sector", "month", "product"], as_index=False).amount_zar.sum()
    return monthly, raw_counts


def historical_validation_lab(zip_path: Path = RAW_ZIP) -> Tuple[dict, pd.DataFrame]:
    monthly, raw_counts = _aggregate_historical(zip_path)
    errors = []
    for (entity_id, sector, product), group in monthly.groupby(["entity_id", "sector", "product"]):
        group = group.sort_values("month").reset_index(drop=True)
        values = group.amount_zar.to_numpy(dtype=float)
        for index in range(12, len(values)):
            prediction = max(values[index - 12], 0.0)
            prior_errors = [abs(values[j] - values[j - 12]) for j in range(12, index)]
            half_width = float(np.quantile(prior_errors, 0.90)) if len(prior_errors) >= 3 else max(prediction * 0.50, 1.0)
            actual = values[index]
            errors.append({
                "entity_id": entity_id, "sector": sector, "product": product, "month": group.month.iloc[index],
                "actual": actual, "prediction": prediction, "absolute_error": abs(actual - prediction),
                "smape": 2 * abs(actual - prediction) / max(abs(actual) + abs(prediction), 1.0),
                "covered_90": max(0.0, prediction - half_width) <= actual <= prediction + half_width,
            })
    error_frame = pd.DataFrame(errors)
    rolling = {
        "n_forecasts": len(error_frame),
        "mae_zar": float(error_frame.absolute_error.mean()),
        "median_smape": float(error_frame.smape.median()),
        "nominal_90_interval_coverage": float(error_frame.covered_90.mean()),
        "by_product": {},
    }
    for product, group in error_frame.groupby("product"):
        rolling["by_product"][product] = {
            "n": len(group), "mae_zar": float(group.absolute_error.mean()),
            "median_smape": float(group.smape.median()), "coverage_90": float(group.covered_90.mean()),
        }

    # Adjacent-month top-10 overlap and leading-product frequency test ranking stability without labels.
    top_sets = []
    leaders: Dict[str, int] = defaultdict(int)
    for month, group in monthly.groupby("month"):
        ranked = group.sort_values("amount_zar", ascending=False)
        top_sets.append((month, set((ranked["entity_id"] + "|" + ranked["product"]).head(10))))
        leaders[str(ranked.iloc[0]["product"])] += 1
    jaccards = []
    for (_, left), (_, right) in zip(top_sets, top_sets[1:]):
        jaccards.append(len(left & right) / max(1, len(left | right)))

    # Leave-one-client-out sector medians are a transparent surrogate benchmark, not wallet truth.
    annual = monthly.groupby(["entity_id", "sector", "product"], as_index=False).amount_zar.mean()
    loco_errors = []
    for row in annual.to_dict(orient="records"):
        peers = annual[(annual["sector"] == row["sector"]) & (annual["product"] == row["product"]) & (annual["entity_id"] != row["entity_id"])]
        if not peers.empty:
            prediction = float(peers.amount_zar.median())
            loco_errors.append(abs(math.log1p(row["amount_zar"]) - math.log1p(prediction)))
    timing = timing_surrogate_lab(monthly)
    return {
        "status": "SUPPLIED_SYNTHETIC_TRANSACTION_HISTORY",
        "production_claim_allowed": False,
        "period_start": monthly.month.min(),
        "period_end": monthly.month.max(),
        "entities": int(monthly.entity_id.nunique()),
        "products": int(monthly["product"].nunique()),
        "raw_rows_read": raw_counts,
        "monthly_records": len(monthly),
        "rolling_origin_seasonal_naive": rolling,
        "leave_one_client_out_sector_product_log_mae": float(np.mean(loco_errors)),
        "ranking_stability": {
            "adjacent_month_top10_jaccard_mean": float(np.mean(jaccards)),
            "adjacent_month_top10_jaccard_min": float(np.min(jaccards)),
            "first_ranked_product_month_frequency": {key: value / len(top_sets) for key, value in leaders.items()},
        },
        "timing_surrogate": timing,
        "interpretation": "Evaluates temporal mechanics and stability only; supplied histories are synthetic and contain no recommendation/action/outcome labels.",
    }, monthly


def timing_surrogate_lab(monthly: pd.DataFrame) -> dict:
    event_counts: Dict[str, int] = defaultdict(int)
    eligible_intervals = 0
    outcome_events = 0
    for (_, _), group in monthly.groupby(["entity_id", "product"]):
        values = group.sort_values("month").amount_zar.to_numpy(dtype=float)
        eligible_intervals += max(0, len(values) - 1)
        if len(values):
            event_counts["ACTIVATION"] += 1
        for index in range(6, len(values)):
            baseline = float(np.median(values[index - 6:index]))
            if baseline > 0 and values[index] >= 1.5 * baseline:
                event_counts["VOLUME_UPLIFT_50"] += 1
                outcome_events += 1
            elif baseline > 0 and values[index] <= 0.2 * baseline:
                event_counts["DORMANCY_80"] += 1
                outcome_events += 1
    gate = TimingService.promotion_gate(eligible_intervals, outcome_events, effective_degrees_of_freedom=8)
    # Surrogate volume events are not qualified RM actions, so the promotable outcome count is zero.
    actual_gate = TimingService.promotion_gate(eligible_intervals, 0, effective_degrees_of_freedom=8)
    return {
        "event_definitions": {
            "ACTIVATION": "first month with observed product activity",
            "VOLUME_UPLIFT_50": "monthly volume at least 150% of prior six-month median",
            "DORMANCY_80": "monthly volume at most 20% of prior six-month median",
        },
        "surrogate_event_counts": dict(event_counts),
        "start_stop_intervals": eligible_intervals,
        "surrogate_gate_if_labels_were_valid": gate,
        "qualified_rm_action_gate": actual_gate,
        "discrete_time_challenger": discrete_time_surrogate_challenger(monthly),
        "decision": "RETAIN_SEASONAL_BASELINE",
        "reason": "Transaction-derived events are useful covariates/surrogates but are not recommendation, action or outcome labels.",
    }


def discrete_time_surrogate_challenger(monthly: pd.DataFrame) -> dict:
    """Evaluate a discrete-time hazard challenger on surrogate volume events.

    This deliberately does not reinterpret transaction-derived events as RM
    actions.  It exercises the full calibration and promotion machinery while
    leaving the qualified-outcome gate closed.
    """
    rows = []
    product_names = sorted(monthly["product"].unique())
    product_index = {product: index for index, product in enumerate(product_names)}
    for (entity_id, product), group in monthly.groupby(["entity_id", "product"]):
        group = group.sort_values("month").reset_index(drop=True)
        values = group.amount_zar.to_numpy(dtype=float)
        for index in range(6, len(values) - 1):
            baseline = max(float(np.median(values[index - 6:index])), 1.0)
            next_value = values[index + 1]
            event = int(next_value >= 1.5 * baseline or next_value <= 0.2 * baseline)
            target_period = pd.Period(group.month.iloc[index + 1], freq="M")
            rows.append({
                "entity_id": entity_id,
                "product": product,
                "target_month": str(target_period),
                "month_number": target_period.month,
                "log_volume": math.log1p(values[index]),
                "ratio": min(5.0, values[index] / baseline),
                "event": event,
            })
    frame = pd.DataFrame(rows)
    if len(frame) < 100 or frame.event.nunique() < 2:
        return {"status": "INSUFFICIENT_SURROGATE_DATA", "production_claim_allowed": False, "records": len(frame)}
    months = sorted(frame.target_month.unique())
    split_month = months[max(1, int(len(months) * 0.72))]
    train = frame[frame.target_month < split_month].copy()
    test = frame[frame.target_month >= split_month].copy()
    numeric_mean = train[["log_volume", "ratio"]].mean()
    numeric_std = train[["log_volume", "ratio"]].std().replace(0, 1)

    def design(data: pd.DataFrame) -> np.ndarray:
        columns = [np.ones(len(data))]
        columns.append(((data.log_volume - numeric_mean.log_volume) / numeric_std.log_volume).to_numpy())
        columns.append(((data.ratio - numeric_mean.ratio) / numeric_std.ratio).to_numpy())
        radians = 2 * np.pi * data.month_number.to_numpy() / 12.0
        columns.extend([np.sin(radians), np.cos(radians)])
        for product in product_names[1:]:
            columns.append(data["product"].eq(product).astype(float).to_numpy())
        return np.column_stack(columns)

    x_train, y_train = design(train), train.event.to_numpy(dtype=float)
    x_test, y_test = design(test), test.event.to_numpy(dtype=float)

    def objective(beta: np.ndarray) -> tuple[float, np.ndarray]:
        probabilities = np.clip(expit(x_train @ beta), 1e-7, 1 - 1e-7)
        penalty = 0.01 * np.sum(beta[1:] ** 2)
        loss = -np.sum(y_train * np.log(probabilities) + (1 - y_train) * np.log(1 - probabilities)) + penalty
        gradient = x_train.T @ (probabilities - y_train)
        gradient[1:] += 0.02 * beta[1:]
        return float(loss), gradient

    fit = minimize(lambda beta: objective(beta), np.zeros(x_train.shape[1]), jac=True, method="L-BFGS-B")
    challenger = np.clip(expit(x_test @ fit.x), 1e-6, 1 - 1e-6)
    global_rate = float(train.event.mean())
    grouped_rates = train.groupby(["product", "month_number"]).event.agg(["sum", "count"])
    baseline = []
    for row in test.itertuples():
        key = (row.product, row.month_number)
        if key in grouped_rates.index:
            record = grouped_rates.loc[key]
            baseline.append(float((record["sum"] + 12 * global_rate) / (record["count"] + 12)))
        else:
            baseline.append(global_rate)
    baseline_array = np.clip(np.asarray(baseline), 1e-6, 1 - 1e-6)

    def metrics(probabilities: np.ndarray) -> dict:
        brier = float(np.mean((probabilities - y_test) ** 2))
        log_loss = float(-np.mean(y_test * np.log(probabilities) + (1 - y_test) * np.log(1 - probabilities)))
        bins = np.minimum((probabilities * 10).astype(int), 9)
        ece = 0.0
        calibration = []
        for bin_index in sorted(set(bins)):
            mask = bins == bin_index
            predicted = float(probabilities[mask].mean())
            observed = float(y_test[mask].mean())
            ece += float(mask.mean()) * abs(predicted - observed)
            calibration.append({"bin": int(bin_index), "n": int(mask.sum()), "predicted": predicted, "observed": observed})
        return {"brier": brier, "log_loss": log_loss, "expected_calibration_error": ece, "calibration": calibration}

    baseline_metrics = metrics(baseline_array)
    challenger_metrics = metrics(challenger)
    average_hazard = float(challenger.mean())
    improvement = (baseline_metrics["brier"] - challenger_metrics["brier"]) / baseline_metrics["brier"]
    return {
        "status": "SURROGATE_CHALLENGER_NOT_PROMOTABLE",
        "production_claim_allowed": False,
        "model": "L2-regularized discrete-time logistic hazard",
        "optimizer_converged": bool(fit.success),
        "train_records": len(train),
        "test_records": len(test),
        "test_events": int(y_test.sum()),
        "temporal_split_month": split_month,
        "seasonal_baseline": baseline_metrics,
        "challenger": challenger_metrics,
        "brier_improvement": float(improvement),
        "mean_surrogate_probability": {
            "30d": average_hazard,
            "60d": 1 - (1 - average_hazard) ** 2,
            "90d": 1 - (1 - average_hazard) ** 3,
        },
        "promotion_gate": {
            "surrogate_performance_pass": bool(improvement >= 0.05 and challenger_metrics["expected_calibration_error"] <= 0.05),
            "qualified_rm_outcomes_pass": False,
            "decision": "RETAIN_SEASONAL_BASELINE",
        },
    }


def causal_trial_simulation(seed: int = 20260809) -> dict:
    rng = np.random.default_rng(seed)
    clusters = 48
    opportunities_per_cluster = 24
    intracluster_correlation = 0.08
    control_rate = 0.18
    encouragement_compliance = 0.62
    control_contamination = 0.10
    censoring = 0.12
    assumed_complier_effect = 0.07
    assignment = rng.integers(0, 2, clusters)
    cluster_effect = rng.normal(0, math.sqrt(intracluster_correlation), clusters)
    records = []
    for cluster in range(clusters):
        for _ in range(opportunities_per_cluster):
            encouraged = int(assignment[cluster])
            exposure_probability = encouragement_compliance if encouraged else control_contamination
            exposed = int(rng.random() < exposure_probability)
            probability = np.clip(control_rate + assumed_complier_effect * exposed + 0.07 * cluster_effect[cluster], 0.01, 0.95)
            outcome = int(rng.random() < probability)
            observed = rng.random() >= censoring
            records.append((encouraged, exposed, outcome, observed))
    frame = pd.DataFrame(records, columns=["assignment", "exposure", "outcome", "observed"])
    complete = frame[frame.observed]
    rates = complete.groupby("assignment").outcome.mean()
    exposure_rates = complete.groupby("assignment").exposure.mean()
    itt = float(rates.get(1, np.nan) - rates.get(0, np.nan))
    first_stage = float(exposure_rates.get(1, np.nan) - exposure_rates.get(0, np.nan))
    iv = itt / first_stage if first_stage > 0.05 else None

    alpha = 0.05
    power = 0.80
    design_effect = 1 + (opportunities_per_cluster - 1) * intracluster_correlation
    effective_n = clusters * opportunities_per_cluster * (1 - censoring) / design_effect
    mde = (norm.ppf(1 - alpha / 2) + norm.ppf(power)) * math.sqrt(2 * control_rate * (1 - control_rate) / (effective_n / 2))
    power_curve = []
    for candidate_clusters in (24, 36, 48, 60, 72, 96):
        effective = candidate_clusters * opportunities_per_cluster * (1 - censoring) / design_effect
        candidate_mde = (norm.ppf(1 - alpha / 2) + norm.ppf(power)) * math.sqrt(2 * control_rate * (1 - control_rate) / (effective / 2))
        power_curve.append({"clusters": candidate_clusters, "mde_absolute_percentage_points": 100 * candidate_mde})
    return {
        "status": "SIMULATED_TRIAL_DESIGN_ONLY",
        "causal_claim_allowed": False,
        "seed": seed,
        "design": "cluster-randomized encouragement by RM team",
        "assumptions": {
            "clusters": clusters, "opportunities_per_cluster": opportunities_per_cluster,
            "intracluster_correlation": intracluster_correlation, "control_action_rate": control_rate,
            "encouragement_compliance": encouragement_compliance, "control_contamination": control_contamination,
            "censoring": censoring, "assumed_complier_effect": assumed_complier_effect,
        },
        "single_simulated_trial": {
            "complete_cases": len(complete), "itt_absolute_effect": itt, "first_stage": first_stage,
            "wald_iv_complier_effect": iv, "iv_label": "DIAGNOSTIC_ONLY_NOT_AN_ESTIMATE_FROM_REAL_OUTCOMES",
        },
        "powered_mde_absolute_percentage_points": 100 * mde,
        "power_curve": power_curve,
        "pre_registration_required": ["treatment", "primary outcome", "horizon", "exclusions", "censoring", "ITT analysis"],
    }


def run_offline_lab(include_history: bool = True, zip_path: Path | None = None) -> dict:
    fixture = build_fixture()
    from .benchmark_economics import evaluate_benchmark_packs

    history, monthly = historical_validation_lab(zip_path or RAW_ZIP) if include_history else ({"status": "NOT_RUN"}, pd.DataFrame())
    report = {
        "report_version": "offline-validation-1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "global_watermark": "SYNTHETIC / PUBLIC / BENCHMARK EVIDENCE — NOT BANK-VALIDATED",
        "as_of": fixture["metadata"]["as_of"],
        "synthetic_calibration": synthetic_calibration_lab(),
        "historical_validation": history,
        "benchmark_economics": evaluate_benchmark_packs(fixture["opportunities"], date.fromisoformat(fixture["metadata"]["as_of"])),
        "causal_trial_simulation": causal_trial_simulation(),
        "residual_bank_gates": [
            "representative E3 multibank calibration panel", "approved Product Finance/Treasury/risk rate inputs",
            "real eligibility/exposure/action/outcome history", "qualified RM-action timing labels",
        ],
    }
    return report


def write_offline_outputs(output_dir: Path, include_history: bool = True, zip_path: Path | None = None) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = run_offline_lab(include_history=include_history, zip_path=zip_path)
    (output_dir / "offline_validation_report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
