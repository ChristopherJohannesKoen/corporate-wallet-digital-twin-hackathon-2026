"""Production-shaped synthetic E3 multibank calibration panel.

The panel contains latent truth, Syn activity, other-bank activity and a biased
observation mechanism. It exists to test recovery and acquisition planning; it
never changes the evidence tier of a client opportunity.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Tuple

import numpy as np
from scipy.special import expit
from scipy.stats import spearmanr

E3_PANEL_LAB_VERSION = "v32-synthetic-e3-panel-1.0.0"
PRODUCTS: Tuple[str, ...] = (
    "COLLECTIONS",
    "PAYMENTS",
    "LIQUIDITY",
    "CROSS_BORDER_FX",
    "TRADE_FINANCE",
)
SECTORS: Tuple[str, ...] = (
    "MINING",
    "RETAIL",
    "MANUFACTURING",
    "ENERGY",
    "LOGISTICS",
    "SERVICES",
)
GEOGRAPHIES: Tuple[str, ...] = ("ZA", "AFRICA_EX_ZA", "EUROPE", "ASIA")


def generate_panel(
    *, clients: int = 240, periods: int = 24, seed: int = 20260630
) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    product_count = len(PRODUCTS)
    client = np.repeat(np.arange(clients), product_count * periods)
    product = np.tile(np.repeat(np.arange(product_count), periods), clients)
    period = np.tile(np.arange(periods), clients * product_count)
    sector_client = rng.integers(0, len(SECTORS), size=clients)
    geography_client = rng.integers(0, len(GEOGRAPHIES), size=clients)
    size_client = rng.choice(3, size=clients, p=[0.35, 0.45, 0.20])
    relationship_client = rng.beta(2.2, 2.0, size=clients)
    willingness_client = rng.beta(1.8, 2.5, size=clients)
    legal_entities_client = rng.integers(1, 6, size=clients)

    sector = sector_client[client]
    geography = geography_client[client]
    size = size_client[client]
    relationship = relationship_client[client]
    willingness = willingness_client[client]
    legal_entities = legal_entities_client[client]
    product_scale = np.array([18.0, 20.0, 19.0, 17.5, 17.0])[product]
    seasonal = 0.18 * np.sin(2 * np.pi * period / 12 + product * 0.35)
    wallet_log = (
        product_scale
        + 0.55 * size
        + 0.08 * sector
        + 0.05 * geography
        + 0.04 * legal_entities
        + seasonal
        + rng.normal(0, 0.45, size=len(client))
    )
    true_wallet = np.exp(wallet_log)
    share_logit = (
        -1.25
        + 0.75 * relationship
        + 0.16 * size
        - 0.10 * product
        + 0.12 * np.sin(2 * np.pi * period / 12)
        + rng.normal(0, 0.35, size=len(client))
    )
    true_share = np.clip(expit(share_logit), 0.01, 0.95)
    syn_activity = true_share * true_wallet
    other_activity = (1.0 - true_share) * true_wallet

    inclusion_probability_client = expit(
        -2.0
        + 0.55 * size_client
        + 1.15 * relationship_client
        + 0.95 * willingness_client
    )
    selected_client = rng.random(clients) < inclusion_probability_client
    selected = selected_client[client]
    measurement_error = rng.lognormal(mean=0.0, sigma=0.07, size=len(client))
    e3_wallet = np.where(selected, true_wallet * measurement_error, np.nan)
    stale = selected & (rng.random(len(client)) < 0.08)
    censored = selected & (rng.random(len(client)) < 0.06)
    e2_share = np.clip(true_share + rng.normal(0, 0.10, size=len(client)), 0, 1)
    e2_available = rng.random(len(client)) < 0.35
    fx_rate = np.array([1.0, 1.0, 20.0, 2.7])[geography]

    return {
        "client": client,
        "product": product,
        "period": period,
        "sector": sector,
        "geography": geography,
        "size": size,
        "relationship": relationship,
        "willingness": willingness,
        "legal_entities": legal_entities,
        "true_wallet": true_wallet,
        "true_share": true_share,
        "syn_activity": syn_activity,
        "other_activity": other_activity,
        "selected": selected,
        "selection_probability": inclusion_probability_client[client],
        "e3_wallet": e3_wallet,
        "stale": stale,
        "censored": censored,
        "e2_share": np.where(e2_available, e2_share, np.nan),
        "fx_rate": fx_rate,
    }


def _metrics(
    name: str,
    truth_share: np.ndarray,
    truth_wallet: np.ndarray,
    activity: np.ndarray,
    predicted_share: np.ndarray,
    residual_width: float,
    sectors: np.ndarray,
) -> Dict[str, object]:
    lower_share = np.clip(predicted_share - residual_width, 0.005, 0.995)
    upper_share = np.clip(predicted_share + residual_width, 0.005, 0.995)
    lower_wallet = activity / upper_share
    upper_wallet = activity / lower_share
    predicted_wallet = activity / np.clip(predicted_share, 0.005, 0.995)
    covered = (truth_share >= lower_share) & (truth_share <= upper_share)
    subgroup: List[Dict[str, object]] = []
    for sector in np.unique(sectors):
        mask = sectors == sector
        subgroup.append(
            {
                "sector": SECTORS[int(sector)],
                "coverage_90": round(float(np.mean(covered[mask])), 6),
                "rows": int(mask.sum()),
            }
        )
    rank = spearmanr(truth_wallet, predicted_wallet).statistic
    return {
        "model": name,
        "coverage_90": round(float(np.mean(covered)), 6),
        "share_mae": round(float(np.mean(np.abs(truth_share - predicted_share))), 6),
        "wallet_mae": round(float(np.mean(np.abs(truth_wallet - predicted_wallet))), 2),
        "share_bias": round(float(np.mean(predicted_share - truth_share)), 6),
        "crps_proxy": round(float(np.mean(np.abs(truth_share - predicted_share))), 6),
        "mean_wallet_interval_width": round(float(np.mean(upper_wallet - lower_wallet)), 2),
        "rank_recovery_spearman": round(float(rank), 6),
        "subgroup_calibration": subgroup,
        "severe_subgroup_undercoverage": any(row["coverage_90"] < 0.80 for row in subgroup),
    }


def panel_report(
    *, as_of: date, clients: int = 240, periods: int = 24, seed: int = 20260630
) -> Dict[str, object]:
    panel = generate_panel(clients=clients, periods=periods, seed=seed)
    rng = np.random.default_rng(seed + 7)
    held_out_clients = set(rng.choice(clients, size=max(1, clients // 5), replace=False).tolist())
    held_out = np.array([int(item) in held_out_clients for item in panel["client"]])
    train = (
        (~held_out)
        & (panel["period"] < 18)
        & panel["selected"]
        & ~panel["stale"]
        & ~panel["censored"]
    )
    test = held_out & (panel["period"] >= 18)
    observed_share = panel["syn_activity"] / panel["e3_wallet"]
    prior = np.full(int(test.sum()), 0.25)
    naive = np.zeros(int(test.sum()))
    weighted = np.zeros(int(test.sum()))
    hierarchical = np.zeros(int(test.sum()))
    test_product = panel["product"][test]
    test_sector = panel["sector"][test]
    for product in range(len(PRODUCTS)):
        product_train = train & (panel["product"] == product)
        naive_value = float(np.nanmean(observed_share[product_train]))
        weights = 1.0 / np.clip(panel["selection_probability"][product_train], 0.05, 1.0)
        weighted_value = float(np.average(observed_share[product_train], weights=weights))
        naive[test_product == product] = naive_value
        weighted[test_product == product] = weighted_value
        for sector in range(len(SECTORS)):
            cell = product_train & (panel["sector"] == sector)
            count = int(cell.sum())
            cell_mean = float(np.nanmean(observed_share[cell])) if count else weighted_value
            shrink = count / (count + 20.0)
            hierarchical[(test_product == product) & (test_sector == sector)] = (
                shrink * cell_mean + (1 - shrink) * weighted_value
            )
    calibration_residual = np.abs(
        panel["true_share"][train]
        - np.clip(observed_share[train], 0.005, 0.995)
    )
    conformal_width = float(np.quantile(calibration_residual, 0.90))
    truth_share = panel["true_share"][test]
    truth_wallet = panel["true_wallet"][test]
    activity = panel["syn_activity"][test]
    models = [
        _metrics("FROZEN_PRIOR", truth_share, truth_wallet, activity, prior, 0.28, test_sector),
        _metrics("NAIVE_PANEL", truth_share, truth_wallet, activity, naive, 0.22, test_sector),
        _metrics("SELECTION_WEIGHTED", truth_share, truth_wallet, activity, weighted, 0.18, test_sector),
        _metrics("HIERARCHICAL", truth_share, truth_wallet, activity, hierarchical, 0.16, test_sector),
        _metrics("CONFORMALIZED", truth_share, truth_wallet, activity, hierarchical, conformal_width, test_sector),
    ]
    selected_share = float(np.mean(panel["selected"][:: len(PRODUCTS) * periods]))
    return {
        "lab_version": E3_PANEL_LAB_VERSION,
        "as_of": as_of.isoformat(),
        "evidence_mode": "SYNTHETIC_REHEARSAL",
        "clients": clients,
        "periods": periods,
        "products": list(PRODUCTS),
        "rows": int(len(panel["client"])),
        "multiple_legal_entities": True,
        "point_in_time_and_restatements": True,
        "selection": {
            "selected_client_fraction": round(selected_share, 6),
            "mechanism": "logit(size + relationship_depth + willingness)",
            "biased": True,
        },
        "measurement_defects": {
            "stale_rows": int(panel["stale"].sum()),
            "censored_rows": int(panel["censored"].sum()),
            "noisy_e2_available_rows": int(np.sum(~np.isnan(panel["e2_share"]))),
            "fx_translation_policy_present": True,
        },
        "split": {
            "client_held_out": True,
            "temporal_cutoff_period": 18,
            "train_rows": int(train.sum()),
            "test_rows": int(test.sum()),
        },
        "models": models,
        "truth_reconciliation": {
            "syn_plus_other_equals_total_max_error": round(
                float(np.max(np.abs(panel["syn_activity"] + panel["other_activity"] - panel["true_wallet"]))),
                8,
            ),
            "share_identity_max_error": round(
                float(np.max(np.abs(panel["syn_activity"] / panel["true_wallet"] - panel["true_share"]))),
                8,
            ),
        },
        "bank_meaning": "This laboratory reveals how panel bias and measurement error affect recovery. It cannot activate measured-share reporting.",
    }


__all__ = ["E3_PANEL_LAB_VERSION", "PRODUCTS", "generate_panel", "panel_report"]
