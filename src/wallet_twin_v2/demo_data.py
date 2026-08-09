from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd

from .contracts import PRODUCTS


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "data" / "v2" / "external_dataset_registry.json"
BASELINE_PATH = ROOT / "outputs" / "data" / "portfolio.json"
TRADE_REFERENCE_PATH = (
    ROOT / "data" / "v2" / "external" / "africa_trade_finance_gap" / "data" / "finance_gap_full.csv"
)
TRADE_REFERENCE_SUMMARY_PATH = ROOT / "data" / "v2" / "representative_trade_finance_summary.json"
CLIENT_DEMO_WATERMARK = "CLIENT DEMONSTRATION — SIMULATED/REPRESENTATIVE DATA — NOT FOR FINANCIAL DECISIONS"


@dataclass(frozen=True)
class DemoDataPaths:
    output_dir: Path
    panel_csv: Path
    outcomes_csv: Path
    manifest_json: Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_external_registry(path: Path = REGISTRY_PATH) -> dict:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if registry.get("registry_version") != "external-data-registry-1.0.0":
        raise ValueError("unsupported external dataset registry")
    if not registry.get("policy", {}).get("production_e3_requires_direct_multibank_observation"):
        raise ValueError("registry must preserve direct-observation E3 policy")
    return registry


def validate_external_registry(path: Path = REGISTRY_PATH, *, require_local_snapshots: bool = False) -> dict:
    registry = load_external_registry(path)
    structural_findings: List[str] = []
    snapshot_findings: List[str] = []
    resolved = 0
    for dataset in registry["datasets"]:
        required = {
            "dataset_id",
            "provider",
            "source_uri",
            "revision",
            "license",
            "classification",
            "usage_class",
            "contains_personal_data",
            "production_e3_eligible",
            "purpose",
        }
        missing = sorted(required.difference(dataset))
        structural_findings.extend(f"{dataset.get('dataset_id', 'UNKNOWN')}:MISSING_{field}" for field in missing)
        if dataset.get("production_e3_eligible"):
            structural_findings.append(f"{dataset['dataset_id']}:REPRESENTATIVE_DATA_CANNOT_BE_E3")
        snapshot = dataset.get("local_snapshot")
        expected = dataset.get("local_sha256")
        if snapshot:
            local_path = ROOT / snapshot
            if not local_path.exists():
                snapshot_findings.append(f"{dataset['dataset_id']}:LOCAL_SNAPSHOT_MISSING")
            else:
                resolved += 1
                if expected and _sha256(local_path).lower() != expected.lower():
                    snapshot_findings.append(f"{dataset['dataset_id']}:HASH_MISMATCH")
    findings = structural_findings + (snapshot_findings if require_local_snapshots else [])
    return {
        "registry_version": registry["registry_version"],
        "datasets": len(registry["datasets"]),
        "local_snapshots_verified": resolved,
        "local_snapshot_findings": snapshot_findings,
        "local_snapshots_passed": not snapshot_findings,
        "local_snapshots_required": require_local_snapshots,
        "registry_passed": not structural_findings,
        "findings": findings,
        "passed": not findings,
        "production_e3_claim_allowed": False,
    }


def _baseline_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    opportunities = pd.DataFrame(
        {
            "entity_id": item["entity_id"],
            "sector": item["sector"],
            "product": item["product"],
            "observed_activity_zar": float(item["observed_activity_zar"]),
        }
        for item in baseline["opportunities"]
    )
    clients = pd.DataFrame(baseline["clients"])[["entity_id", "sector", "country_count", "relationship_breadth"]]
    return opportunities, clients


def _trade_reference_summary() -> dict:
    summary = json.loads(TRADE_REFERENCE_SUMMARY_PATH.read_text(encoding="utf-8"))
    if summary.get("source_revision") != "d58f99fe2947f6613f321418bba5cf91cad805b1":
        raise ValueError("representative trade-finance summary revision is not pinned")
    if summary.get("classification") != "REPRESENTATIVE_SYNTHETIC_PUBLIC":
        raise ValueError("representative trade-finance summary classification is invalid")
    return summary


def generate_representative_multibank_analog(
    relationship_count: int = 300,
    seed: int = 20260809,
) -> pd.DataFrame:
    """Create known-truth multibank analogs for mechanics testing.

    These rows deliberately do not use EvidenceTier.E3. They are simulated peers,
    not observations of the named portfolio or its competitors.
    """

    opportunities, clients = _baseline_frames()
    rng = np.random.default_rng(seed)
    sector_distribution = clients["sector"].value_counts(normalize=True)
    sectors = rng.choice(
        sector_distribution.index.to_numpy(),
        size=relationship_count,
        p=sector_distribution.to_numpy(),
    )
    geographies = np.array(["South Africa", "SADC", "Rest of Africa", "Global"])
    geography_p = np.array([0.48, 0.19, 0.18, 0.15])
    size_buckets = np.array(["large", "upper_mid", "mid"])
    size_p = np.array([0.30, 0.45, 0.25])
    maturity_buckets = np.array(["new", "developing", "established"])
    maturity_p = np.array([0.18, 0.37, 0.45])
    product_prior = {
        "Collections": (5.3, 9.4),
        "Payments": (5.0, 9.8),
        "Liquidity": (4.4, 10.2),
        "Cross-border FX": (3.7, 11.2),
        "Trade finance": (3.2, 11.8),
    }
    rows: List[Dict[str, Any]] = []

    for relationship_index, sector in enumerate(sectors, start=1):
        relationship_id = f"DEMO-R{relationship_index:04d}"
        geography = str(rng.choice(geographies, p=geography_p))
        size = str(rng.choice(size_buckets, p=size_p))
        maturity = str(rng.choice(maturity_buckets, p=maturity_p))
        team_id = f"DEMO-TEAM-{((relationship_index - 1) % 30) + 1:02d}"
        size_multiplier = {"large": 2.0, "upper_mid": 1.0, "mid": 0.45}[size]
        maturity_multiplier = {"new": 0.75, "developing": 1.0, "established": 1.25}[maturity]
        selection_probability = float(
            np.clip(0.18 + 0.12 * size_multiplier + 0.08 * maturity_multiplier + rng.normal(0, 0.03), 0.12, 0.72)
        )

        for product in PRODUCTS:
            peers = opportunities[(opportunities["sector"] == sector) & (opportunities["product"] == product)]
            if peers.empty:
                peers = opportunities[opportunities["product"] == product]
            focal_anchor = float(peers["observed_activity_zar"].median())
            focal_activity = float(
                np.exp(rng.normal(np.log(max(focal_anchor * size_multiplier, 1.0)), 0.46)) * maturity_multiplier
            )
            alpha, beta = product_prior[product]
            focal_share = float(np.clip(rng.beta(alpha, beta), 0.05, 0.82))
            total_wallet = focal_activity / focal_share
            other_bank_activity = total_wallet - focal_activity
            rows.append(
                {
                    "observation_id": f"{relationship_id}-{product.lower().replace(' ', '-').replace('cross-border', 'fx')}",
                    "relationship_id": relationship_id,
                    "team_id": team_id,
                    "product": product,
                    "sector": sector,
                    "geography": geography,
                    "size_bucket": size,
                    "relationship_maturity": maturity,
                    "observation_period_start": "2025-07-01",
                    "observation_period_end": "2026-06-30",
                    "available_date": "2026-08-09",
                    "focal_bank_activity_zar": round(focal_activity, 2),
                    "other_bank_activity_zar": round(other_bank_activity, 2),
                    "total_multibank_wallet_zar": round(total_wallet, 2),
                    "known_truth_share": round(focal_share, 8),
                    "selection_probability": round(selection_probability, 8),
                    "selection_weight": round(1.0 / selection_probability, 8),
                    "reconciled_to_bank_records": False,
                    "consent_reference": None,
                    "provenance_class": "SYNTHETIC_SIMULATION",
                    "truth_status": "SIMULATED_KNOWN_TRUTH",
                    "evidence_tier": None,
                    "production_e3_eligible": False,
                    "measured_share_label_allowed": False,
                    "dataset_version": f"representative-multibank-analog-1.0.0+seed.{seed}",
                }
            )
    return pd.DataFrame(rows)


def generate_trial_analog(panel: pd.DataFrame, seed: int = 20260809) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 17)
    frame = panel.copy()
    team_assignment = {
        team: int(hashlib.sha256(f"{seed}:{team}".encode()).hexdigest(), 16) % 2
        for team in sorted(frame["team_id"].unique())
    }
    frame["encouragement_arm"] = frame["team_id"].map(team_assignment)
    product_effect = frame["product"].map(
        {
            "Collections": -0.10,
            "Payments": 0.00,
            "Liquidity": 0.08,
            "Cross-border FX": 0.15,
            "Trade finance": 0.22,
        }
    )
    base_logit = -1.35 + product_effect + 0.35 * (frame["relationship_maturity"] == "established").astype(float)
    action_probability = 1.0 / (1.0 + np.exp(-(base_logit + 0.38 * frame["encouragement_arm"])))
    frame["qualified_action_30d"] = rng.binomial(1, action_probability)
    pipeline_probability = np.clip(0.12 + 0.52 * frame["qualified_action_30d"], 0, 0.90)
    frame["pipeline_milestone_60d"] = rng.binomial(1, pipeline_probability)
    outcome_probability = np.clip(0.04 + 0.34 * frame["pipeline_milestone_60d"], 0, 0.80)
    frame["reconciled_outcome_90d"] = rng.binomial(1, outcome_probability)
    unit_margin = frame["product"].map(
        {"Collections": 1.2, "Payments": 0.8, "Liquidity": 1.8, "Cross-border FX": 4.5, "Trade finance": 6.5}
    )
    contestable = np.maximum(frame["total_multibank_wallet_zar"] * 0.40 - frame["focal_bank_activity_zar"], 0)
    frame["simulated_contribution_zar"] = (
        contestable * unit_margin / 10_000 * frame["reconciled_outcome_90d"]
    ).round(2)
    frame["assignment_probability"] = 0.5
    frame["censored"] = False
    frame["outcome_provenance"] = "SYNTHETIC_CAUSAL_REHEARSAL"
    frame["production_causal_claim_allowed"] = False
    return frame[
        [
            "observation_id",
            "relationship_id",
            "team_id",
            "product",
            "sector",
            "encouragement_arm",
            "assignment_probability",
            "qualified_action_30d",
            "pipeline_milestone_60d",
            "reconciled_outcome_90d",
            "simulated_contribution_zar",
            "censored",
            "outcome_provenance",
            "production_causal_claim_allowed",
        ]
    ]


def _stratum_coverage(panel: pd.DataFrame, columns: Iterable[str]) -> dict:
    return {column: {str(key): int(value) for key, value in panel[column].value_counts().sort_index().items()} for column in columns}


def build_client_demo_data(
    output_dir: Path | None = None,
    relationship_count: int = 300,
    seed: int = 20260809,
) -> dict:
    directory = output_dir or (ROOT / "outputs" / "client_demo")
    directory.mkdir(parents=True, exist_ok=True)
    paths = DemoDataPaths(
        output_dir=directory,
        panel_csv=directory / "representative_multibank_analog.csv",
        outcomes_csv=directory / "simulated_trial_outcomes.csv",
        manifest_json=directory / "client_demo_data_manifest.json",
    )
    registry_validation = validate_external_registry()
    if not registry_validation["passed"]:
        raise ValueError("external dataset registry failed validation")
    panel = generate_representative_multibank_analog(relationship_count=relationship_count, seed=seed)
    outcomes = generate_trial_analog(panel, seed=seed)
    panel.to_csv(paths.panel_csv, index=False)
    outcomes.to_csv(paths.outcomes_csv, index=False)
    manifest = {
        "version": "client-demo-data-estate-1.0.0",
        "as_of": "2026-08-09",
        "status": "CLIENT_DEMO_DATA_READY",
        "watermark": CLIENT_DEMO_WATERMARK,
        "source_estate": {
            "synbank_rows": 3064295,
            "audited_public_e1_facts": 82,
            "representative_trade_finance_rows": 10000,
            "remote_federated_transaction_rows": 6362620,
            "finqa_numerical_reasoning_cases": 8281,
            "named_client_competitor_observations": 0,
        },
        "representative_panel": {
            "relationships": int(panel["relationship_id"].nunique()),
            "observations": int(len(panel)),
            "products": int(panel["product"].nunique()),
            "selection_weighted": True,
            "known_truth": True,
            "production_e3_eligible": False,
            "strata": _stratum_coverage(
                panel,
                ("product", "sector", "geography", "size_bucket", "relationship_maturity"),
            ),
        },
        "trial_analog": {
            "eligible_opportunities": int(len(outcomes)),
            "clusters": int(outcomes["team_id"].nunique()),
            "qualified_actions_30d": int(outcomes["qualified_action_30d"].sum()),
            "pipeline_milestones_60d": int(outcomes["pipeline_milestone_60d"].sum()),
            "reconciled_outcomes_90d": int(outcomes["reconciled_outcome_90d"].sum()),
            "production_causal_claim_allowed": False,
        },
        "trade_finance_reference": _trade_reference_summary(),
        "registry_validation": registry_validation,
        "artifacts": {
            "panel": {"path": _artifact_path(paths.panel_csv), "sha256": _sha256(paths.panel_csv)},
            "outcomes": {"path": _artifact_path(paths.outcomes_csv), "sha256": _sha256(paths.outcomes_csv)},
        },
        "claim_boundary": {
            "client_demo_ready": True,
            "bank_production_ready": False,
            "measured_share_label_allowed": False,
            "causal_uplift_label_allowed": False,
            "financial_decision_use_allowed": False,
        },
    }
    paths.manifest_json.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
