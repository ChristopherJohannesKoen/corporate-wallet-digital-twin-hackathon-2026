"""E1 anchor-weight sensitivity sweep.

The E1 pooling weight of 0.35 is a governed judgement, not a measurement. An
unstated judgement that moves a published ranking is exactly the kind of thing a
model-risk reviewer is entitled to challenge, so this reports what actually
changes across a plausible range.

The arms share Beta draws — ``_stable_seed`` does not include the weight — so
this is a paired comparison under common random numbers rather than three
independent Monte Carlo runs. Differences are attributable to the weight.

    python scripts/run_measurement_sensitivity.py
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.canonical import artifact_timestamp, write_canonical_json  # noqa: E402
from wallet_twin_v2.contracts import DeploymentEnvironment, EvidenceTier  # noqa: E402
from wallet_twin_v2.economics import EconomicsService  # noqa: E402
from wallet_twin_v2.fixtures import synthetic_rate_card  # noqa: E402
from wallet_twin_v2.measurement_policy import (  # noqa: E402
    DEFAULT_MEASUREMENT_POLICY,
    MEASUREMENT_POLICY_VERSION,
)
from wallet_twin_v2.public_evidence import PublicEvidenceRegistry  # noqa: E402
from wallet_twin_v2.wallet_model import DEFAULT_PRIORS, HierarchicalWalletModel, sample_crps  # noqa: E402

OUTPUT = ROOT / "outputs" / "v2_validation" / "measurement_policy_sensitivity.json"
V1_BASELINE = ROOT / "legacy" / "v1" / "fixtures" / "portfolio.json"
ARMS: Tuple[float, ...] = (0.20, 0.35, 0.50)
BASELINE_ARM = 0.35
TARGET_SHARE = 0.40


def known_truth_diagnostics(weight: float, entity_count: int = 100, seed: int = 20260812) -> dict:
    """Paired synthetic known-truth check for coverage/CRPS under each E1 weight.

    This does not validate client accuracy. It tests the claimed interval effect
    in a sealed, reproducible laboratory where the total wallet is known.
    """

    rng = np.random.default_rng(seed)
    as_of = date(2026, 6, 30)
    policy = DEFAULT_MEASUREMENT_POLICY.with_e1_weight(weight)
    model = HierarchicalWalletModel(draws=1_000, policy=policy)
    products = tuple(DEFAULT_PRIORS)
    product_scale = dict(zip(products, (8.5e9, 7.0e9, 2.2e9, 3.0e9, 1.4e9)))
    covered = []
    crps = []
    widths = []
    relative_widths = []
    for entity_index in range(entity_count):
        size = float(rng.lognormal(0.0, 0.75))
        for product in products:
            prior = DEFAULT_PRIORS[product]
            truth_share = float(
                rng.beta(
                    prior.mean * prior.concentration,
                    (1.0 - prior.mean) * prior.concentration,
                )
            )
            truth_wallet = float(product_scale[product] * size * rng.lognormal(0, 0.28))
            observed = truth_wallet * truth_share
            anchor_mid = truth_wallet * float(rng.lognormal(0, 0.18))
            anchor = (
                max(observed, anchor_mid * 0.72),
                max(observed, anchor_mid),
                max(observed, anchor_mid * 1.32),
            )
            estimate, wallet_draws, _ = model.estimate(
                opportunity_id=f"E1W-SYN-{entity_index}-{product}",
                entity_id=f"S{entity_index:04d}",
                product=product,
                sector="synthetic_known_truth",
                observed_activity=observed,
                as_of=as_of,
                evidence_tier=EvidenceTier.E1,
                anchor_range=anchor,
                fact_ids=(f"SYN-ANCHOR-{entity_index}-{product}",),
                dataset_version="measurement-weight-known-truth-1.0.0",
            )
            width = estimate.posterior_wallet.upper - estimate.posterior_wallet.lower
            widths.append(width)
            relative_widths.append(width / truth_wallet)
            covered.append(estimate.posterior_wallet.lower <= truth_wallet <= estimate.posterior_wallet.upper)
            crps.append(sample_crps(wallet_draws / truth_wallet, 1.0))
    return {
        "status": "SYNTHETIC_KNOWN_TRUTH_ONLY",
        "production_claim_allowed": False,
        "records": len(covered),
        "wallet_90_coverage": float(np.mean(covered)),
        "wallet_scaled_crps": float(np.mean(crps)),
        "median_wallet_interval_width_zar": float(np.median(widths)),
        "median_wallet_relative_interval_width": float(np.median(relative_widths)),
    }


def kendall_tau(left: List[str], right: List[str]) -> float:
    """Rank correlation between two orderings of the same items."""
    position = {item: index for index, item in enumerate(right)}
    order = [position[item] for item in left]
    concordant = discordant = 0
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            if order[i] < order[j]:
                concordant += 1
            else:
                discordant += 1
    total = concordant + discordant
    return (concordant - discordant) / total if total else 1.0


def evaluate(weight: float) -> Dict[str, object]:
    baseline = json.loads(V1_BASELINE.read_text(encoding="utf-8"))
    as_of = date.fromisoformat(baseline["metadata"]["as_of"])
    policy = DEFAULT_MEASUREMENT_POLICY.with_e1_weight(weight)
    model = HierarchicalWalletModel(draws=4_000, policy=policy)
    economics = EconomicsService()
    registry = PublicEvidenceRegistry(as_of)
    cards: Dict[str, object] = {}

    cells: List[Dict[str, object]] = []
    for raw in baseline["opportunities"]:
        decision = registry.activate(
            raw["entity_id"],
            raw["product"],
            raw["sector"],
            float(raw["observed_activity_zar"]),
            preset=raw.get("public_anchor"),
            preset_fact_ids=raw.get("anchor_impact", {}).get("fact_ids", ()),
        )
        tier = EvidenceTier.E1 if decision.activated else EvidenceTier.E0
        estimate, _, _ = model.estimate(
            opportunity_id=raw["opportunity_id"],
            entity_id=raw["entity_id"],
            product=raw["product"],
            sector=raw["sector"],
            observed_activity=float(raw["observed_activity_zar"]),
            as_of=as_of,
            evidence_tier=tier,
            anchor_range=list(decision.anchor_range) if decision.anchor_range else None,
            fact_ids=list(decision.active_fact_ids),
        )
        rate_bps = float(raw["assumptions"]["economic_rate_bps"]["base"])
        card = cards.setdefault(
            raw["product"], synthetic_rate_card(raw["product"], rate_bps, as_of)
        )
        commercial = economics.evaluate(
            as_of=as_of,
            environment=DeploymentEnvironment.CLIENT_DEMO,
            rate_card=card,
            observed_activity=float(estimate.observed_activity.normalized_amount),
            wallet_median=estimate.posterior_wallet.median,
            current_share=estimate.share_interval.median,
            target_share=TARGET_SHARE,
        )
        contribution = (
            float(commercial.contestable_scenario_contribution.normalized_amount)
            if commercial.contestable_scenario_contribution
            else 0.0
        )
        wallet = estimate.posterior_wallet
        cells.append(
            {
                "opportunity_id": raw["opportunity_id"],
                "activated": decision.activated,
                "posterior_wallet_median": wallet.median,
                "posterior_wallet_interval_width": wallet.upper - wallet.lower,
                "contestable_scenario_contribution": contribution,
            }
        )

    cells.sort(key=lambda item: (-float(item["contestable_scenario_contribution"]), item["opportunity_id"]))
    for rank, cell in enumerate(cells, start=1):
        cell["rank"] = rank
    top10 = cells[:10]
    trade_count = sum(cell["opportunity_id"].endswith("-trade-finance") for cell in top10)
    return {
        "e1_anchor_weight": weight,
        "policy_version": policy.version,
        "activated_cells": sum(1 for cell in cells if cell["activated"]),
        "cells": cells,
        "ranking": [str(cell["opportunity_id"]) for cell in cells],
        "trade_finance": {
            "first_ranked": bool(cells and cells[0]["opportunity_id"].endswith("-trade-finance")),
            "top10_count": trade_count,
            "top10_share": trade_count / 10.0,
            "majority_dominant": trade_count >= 6,
            "absolute_economics_top10_zar": math.fsum(
                float(cell["contestable_scenario_contribution"])
                for cell in top10
                if cell["opportunity_id"].endswith("-trade-finance")
            ),
        },
        "known_truth_diagnostics": known_truth_diagnostics(weight),
    }


def main() -> int:
    arms = {weight: evaluate(weight) for weight in ARMS}
    baseline = arms[BASELINE_ARM]
    baseline_rank = {
        str(cell["opportunity_id"]): int(cell["rank"]) for cell in baseline["cells"]
    }
    baseline_top8 = set(baseline["ranking"][:8])

    comparisons = {}
    for weight, arm in arms.items():
        if weight == BASELINE_ARM:
            continue
        moves = {
            str(cell["opportunity_id"]): int(cell["rank"]) - baseline_rank[str(cell["opportunity_id"])]
            for cell in arm["cells"]
        }
        activated_moves = {
            cell_id: delta
            for cell_id, delta in moves.items()
            if any(
                c["opportunity_id"] == cell_id and c["activated"] for c in arm["cells"]
            )
        }
        comparisons[f"{weight:.2f}"] = {
            "kendall_tau_vs_baseline": kendall_tau(arm["ranking"], baseline["ranking"]),
            "cells_moving_more_than_five_ranks": sum(
                1 for delta in moves.values() if abs(delta) > 5
            ),
            "max_absolute_rank_move": max(abs(delta) for delta in moves.values()),
            "activated_cell_max_rank_move": (
                max(abs(delta) for delta in activated_moves.values())
                if activated_moves
                else 0
            ),
            "top8_overlap_with_baseline": len(baseline_top8 & set(arm["ranking"][:8])),
            "top8_identical": baseline_top8 == set(arm["ranking"][:8]),
        }

    top8_stable = all(item["top8_identical"] for item in comparisons.values())
    report = {
        "version": "measurement-policy-sensitivity-1.1.0",
        "generated_at": artifact_timestamp(),
        "baseline_policy_version": MEASUREMENT_POLICY_VERSION,
        "baseline_e1_anchor_weight": BASELINE_ARM,
        "arms_evaluated": list(ARMS),
        "design": (
            "Paired comparison under common random numbers: the Beta draw seed excludes "
            "the anchor weight, so the arms share draws and differences are attributable "
            "to the weight rather than to Monte Carlo noise."
        ),
        "activated_cells": baseline["activated_cells"],
        "comparisons": comparisons,
        "headline": (
            "The top-8 selection is invariant to the E1 anchor weight across 0.20-0.50."
            if top8_stable
            else "The top-8 selection is NOT invariant across 0.20-0.50; see comparisons."
        ),
        "top8_invariant": top8_stable,
        "known_truth_boundary": (
            "Coverage and CRPS are evaluated only in a seeded synthetic known-truth laboratory. "
            "They do not demonstrate real-client calibration."
        ),
        "arms": {f"{weight:.2f}": arm for weight, arm in arms.items()},
        "claim_boundary": (
            "A sensitivity sweep evidences robustness to one governed assumption. It is "
            "not a calibration and does not license a measured-share claim."
        ),
    }
    write_canonical_json(OUTPUT, report)
    print(f"measurement sensitivity written to {OUTPUT.relative_to(ROOT)}")
    print(
        json.dumps(
            {
                "activated_cells": report["activated_cells"],
                "top8_invariant": top8_stable,
                "comparisons": comparisons,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
