from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable

from .contracts import ApprovalStatus, CuratedMetadata, DeploymentEnvironment, QualityStatus, RateCard
from .economics import EconomicsService


ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / "data" / "v2" / "benchmark_rate_cards.json"


def _benchmark_metadata(key: str, as_of: date, owner: str, domain: str) -> CuratedMetadata:
    timestamp = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc)
    return CuratedMetadata(
        business_key=key,
        source_system_key=f"benchmark:{key}",
        event_time=timestamp,
        valid_from=timestamp,
        ingestion_time=timestamp,
        source_hash=hashlib.sha256(key.encode("utf-8")).hexdigest(),
        transformation_version="e0-benchmark-rate-card-1.0.0",
        quality_status=QualityStatus.LEGACY_INCOMPLETE,
        data_owner=owner,
        entitlement_domain=domain,
    )


def load_benchmark_packs(path: Path = PACK_PATH) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("production_eligible") is not False or payload.get("evidence_tier") != "E0":
        raise ValueError("benchmark packs must be explicitly E0 and non-production")
    return payload


def benchmark_rate_card(product: str, pack_name: str, as_of: date) -> RateCard:
    registry = load_benchmark_packs()
    pack = registry["packs"][pack_name]
    gross = Decimal(str(pack["gross_price_bps"][product]))
    costs = pack["cost_fraction_of_gross"]
    return RateCard(
        rate_card_id=f"e0-benchmark-{pack_name}-{product.lower().replace(' ', '-')}",
        version=registry["version"],
        product=product,
        revenue_driver="annual_activity",
        gross_price_bps=gross,
        client_discount_bps=gross * Decimal(str(costs["client_discount"])),
        ftp_bps=gross * Decimal(str(costs["ftp"])),
        liquidity_bps=gross * Decimal(str(costs["liquidity"])),
        expected_loss_bps=gross * Decimal(str(costs["expected_loss"])),
        capital_bps=gross * Decimal(str(costs["capital"])),
        hedging_bps=gross * Decimal(str(costs["hedging"])),
        execution_bps=gross * Decimal(str(costs["execution"])),
        servicing_bps=gross * Decimal(str(costs["servicing"])),
        operating_cost_bps=gross * Decimal(str(costs["operating_cost"])),
        tax_bps=gross * Decimal(str(costs["tax"])),
        acquisition_cost=Decimal("0"),
        approved_hurdle_bps=Decimal(str(pack["hurdle_bps"])),
        currency="ZAR",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        approval_status=ApprovalStatus.APPROVED,
        reconciliation_status="RECONCILED",
        synthetic=True,
        owner="V2 governed benchmark registry (not Product Finance)",
        metadata=_benchmark_metadata(
            f"benchmark:{pack_name}:{product}", as_of, "V2 model governance", f"product:{product}"
        ),
    )


def evaluate_benchmark_packs(opportunities: Iterable[object], as_of: date) -> dict:
    service = EconomicsService()
    registry = load_benchmark_packs()
    result: Dict[str, dict] = {}
    for pack_name, pack in registry["packs"].items():
        product_totals: Dict[str, float] = {}
        observed_totals: Dict[str, float] = {}
        total = 0.0
        observed_total = 0.0
        frontiers = []
        break_even_shares = []
        portfolio_frontier = {share: 0.0 for share in (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60)}
        for opportunity in opportunities:
            card = benchmark_rate_card(opportunity.product, pack_name, as_of)
            evaluated = service.evaluate(
                as_of=as_of,
                environment=DeploymentEnvironment.FIXTURE,
                rate_card=card,
                observed_activity=float(opportunity.observed_activity.normalized_amount),
                wallet_median=opportunity.posterior_wallet.median,
                current_share=opportunity.share_interval.median,
                target_share=float(pack["target_share"]),
            )
            value = float(evaluated.contestable_scenario_contribution.normalized_amount) if evaluated.contestable_scenario_contribution else 0.0
            observed_value = float(evaluated.observed_contribution.normalized_amount) if evaluated.observed_contribution else 0.0
            total += value
            observed_total += observed_value
            product_totals[opportunity.product] = product_totals.get(opportunity.product, 0.0) + value
            observed_totals[opportunity.product] = observed_totals.get(opportunity.product, 0.0) + observed_value
            net_rate = float(EconomicsService.net_bps(card)) / 10_000
            current_share = opportunity.share_interval.median
            required_capture = float(card.acquisition_cost) / max(opportunity.posterior_wallet.median * net_rate, 1e-9)
            break_even_shares.append(min(1.0, current_share + required_capture))
            for frontier_share in portfolio_frontier:
                point = service.evaluate(
                    as_of=as_of,
                    environment=DeploymentEnvironment.FIXTURE,
                    rate_card=card,
                    observed_activity=float(opportunity.observed_activity.normalized_amount),
                    wallet_median=opportunity.posterior_wallet.median,
                    current_share=current_share,
                    target_share=frontier_share,
                )
                portfolio_frontier[frontier_share] += (
                    float(point.contestable_scenario_contribution.normalized_amount)
                    if point.contestable_scenario_contribution else 0.0
                )
            if len(frontiers) < 5:
                frontier = service.scenario_frontier(
                    shares=(0.30, 0.35, 0.40, 0.45, 0.50),
                    as_of=as_of,
                    environment=DeploymentEnvironment.FIXTURE,
                    rate_card=card,
                    observed_activity=float(opportunity.observed_activity.normalized_amount),
                    wallet_median=opportunity.posterior_wallet.median,
                    current_share=opportunity.share_interval.median,
                )
                frontiers.append({
                    "opportunity_id": opportunity.opportunity_id,
                    "points": [
                        {"target_share": point.target_share, "scenario_value_zar": float(point.contestable_scenario_contribution.normalized_amount) if point.contestable_scenario_contribution else 0.0}
                        for point in frontier
                    ],
                })
        margin_waterfalls = {}
        for product in pack["gross_price_bps"]:
            card = benchmark_rate_card(product, pack_name, as_of)
            costs = {field: float(getattr(card, field)) for field in EconomicsService._cost_fields}
            margin_waterfalls[product] = {
                "gross_price_bps": float(card.gross_price_bps),
                "costs_bps": costs,
                "total_cost_bps": sum(costs.values()),
                "net_contribution_bps": float(EconomicsService.net_bps(card)),
                "hurdle_bps": float(card.approved_hurdle_bps),
                "hurdle_headroom_bps": float(EconomicsService.net_bps(card) - card.approved_hurdle_bps),
            }
        product_shares = {product: value / max(total, 1e-9) for product, value in product_totals.items()}
        result[pack_name] = {
            "portfolio_scenario_value_zar": total,
            "portfolio_observed_contribution_zar": observed_total,
            "product_scenario_value_zar": product_totals,
            "product_observed_contribution_zar": observed_totals,
            "top_product": max(product_totals, key=product_totals.get),
            "target_share": pack["target_share"],
            "portfolio_frontier": [
                {"target_share": share, "scenario_value_zar": value}
                for share, value in portfolio_frontier.items()
            ],
            "break_even_target_share": {
                "definition": "current share plus capture required to recover explicit acquisition cost",
                "median": float(sorted(break_even_shares)[len(break_even_shares) // 2]),
                "maximum": max(break_even_shares),
                "note": "Benchmark acquisition cost is zero; bank implementation costs must be supplied before production.",
            },
            "margin_waterfalls": margin_waterfalls,
            "concentration": {
                "top_product_share": max(product_shares.values()),
                "product_hhi": sum(value * value for value in product_shares.values()),
            },
            "reconciliation": {
                "product_sum_zar": sum(product_totals.values()),
                "difference_zar": total - sum(product_totals.values()),
                "passes": abs(total - sum(product_totals.values())) < 0.01,
            },
            "sample_frontiers": frontiers,
        }
    return {
        "registry_version": registry["version"],
        "claim_class": "SCENARIO",
        "evidence_tier": "E0",
        "production_eligible": False,
        "watermark": registry["watermark"],
        "packs": result,
    }
