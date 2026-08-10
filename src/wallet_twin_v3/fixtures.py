from __future__ import annotations

import json
import math
from datetime import date
from typing import Any, Sequence

import numpy as np

from wallet_twin_v2.contracts import OpportunityView
from wallet_twin_v2.fixtures import ROOT, build_fixture

from .contracts import V3OpportunityView
from .decision_portfolio import RobustPortfolioOptimizer
from .event_dynamics import BayesianChangePointDetector, leakage_alarm
from .pu_learning import PURecord, PositiveUnlabelledNeedModel
from .shadow_network import ShadowNetworkReconstructor
from .treasury_graph import build_treasury_graph
from .voi import DecisionDirectedEvidencePlanner


BASELINE = ROOT / "legacy" / "v1" / "fixtures" / "portfolio.json"
SENSOR_REGISTRY = ROOT / "data" / "v3" / "public_sensor_registry.json"


def _load_baseline() -> dict[str, Any]:
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _feature_record(
    raw: dict[str, Any], client: dict[str, Any], threshold: float
) -> PURecord:
    labelled = (
        bool(raw.get("public_anchor"))
        or float(raw["observed_activity_zar"]) >= threshold
    )
    return PURecord(
        opportunity_id=raw["opportunity_id"],
        entity_id=raw["entity_id"],
        product=raw["product"],
        features=(
            math.log1p(float(raw["observed_activity_zar"])),
            float(raw.get("recurrence", 0.0)),
            float(raw.get("trend", 0.0)),
            float(raw.get("timing_score", 0.0)),
            float(client.get("relationship_breadth", 0)) / 5.0,
            min(1.0, float(client.get("country_count", 0)) / 20.0),
        ),
        labelled_positive=labelled,
    )


def build_v3_fixture(v2_fixture: dict[str, Any] | None = None) -> dict[str, Any]:
    v2 = v2_fixture or build_fixture()
    baseline = _load_baseline()
    as_of = date.fromisoformat(v2["metadata"]["as_of"])
    raw_opportunities = {
        item["opportunity_id"]: item for item in baseline["opportunities"]
    }
    raw_clients = {item["entity_id"]: item for item in baseline["clients"]}
    opportunities: Sequence[OpportunityView] = v2["opportunities"]

    by_product: dict[str, list[float]] = {}
    for raw in raw_opportunities.values():
        by_product.setdefault(raw["product"], []).append(
            float(raw["observed_activity_zar"])
        )
    thresholds = {
        product: float(np.quantile(values, 0.75))
        for product, values in by_product.items()
    }
    pu_records = [
        _feature_record(
            raw_opportunities[item.opportunity_id],
            raw_clients[item.entity_id],
            thresholds[item.product],
        )
        for item in opportunities
    ]
    need_list = PositiveUnlabelledNeedModel().fit_predict(pu_records)
    needs = {item.opportunity_id: item for item in need_list}

    reconstructor = ShadowNetworkReconstructor(draws=256)
    detector = BayesianChangePointDetector()
    shadows = {}
    changes = {}
    leakages = {}
    for opportunity in opportunities:
        client = raw_clients[opportunity.entity_id]
        corridors = [
            (item["name"], float(item["value_zar"]))
            for item in client.get("top_countries", [])
        ]
        shadow = reconstructor.reconstruct(opportunity, corridors)
        monthly = client["monthly"][opportunity.product]
        signal = detector.detect(
            opportunity.opportunity_id,
            opportunity.entity_id,
            opportunity.product,
            [float(item["value_zar"]) for item in monthly],
            as_of,
        )
        shadows[opportunity.opportunity_id] = shadow
        changes[opportunity.opportunity_id] = signal
        leakages[opportunity.opportunity_id] = leakage_alarm(signal, shadow)

    portfolio = RobustPortfolioOptimizer().optimize(
        opportunities, needs, leakages, as_of
    )
    selected_ids = {action.opportunity_id for action in portfolio.selected_actions}
    evidence_plan = DecisionDirectedEvidencePlanner().plan(
        opportunities,
        portfolio.selected_actions,
        shadows,
        as_of,
    )

    v3_opportunities: list[V3OpportunityView] = []
    for opportunity in opportunities:
        need = needs[opportunity.opportunity_id]
        change = changes[opportunity.opportunity_id]
        leakage = leakages[opportunity.opportunity_id]
        rank_component = 1.0 - min(1.0, ((opportunity.rank or 100) - 1) / 99.0)
        decision_score = 100.0 * (
            0.40 * need.product_need_probability
            + 0.25 * leakage.alarm_probability
            + 0.20 * rank_component
            + 0.15 * float(opportunity.rank_probability or 0.0)
        )
        v3_opportunities.append(
            V3OpportunityView(
                opportunity_id=opportunity.opportunity_id,
                entity_id=opportunity.entity_id,
                entity_name=opportunity.entity_name,
                sector=opportunity.sector,
                product=opportunity.product,
                as_of=as_of,
                v2_rank=opportunity.rank,
                need=need,
                shadow_wallet=shadows[opportunity.opportunity_id],
                change_point=change,
                leakage=leakage,
                decision_score=decision_score,
                evidence_tier=opportunity.evidence_tier,
                commercial_status=opportunity.commercial.status.value,
            )
        )
    v3_opportunities.sort(key=lambda item: (-item.decision_score, item.opportunity_id))

    treasury_graphs: dict[str, dict[str, Any]] = {}
    for entity_id, client in raw_clients.items():
        client_shadows = [
            shadow for shadow in shadows.values() if shadow.entity_id == entity_id
        ]
        mean_entropy = float(
            np.mean([shadow.normalized_entropy for shadow in client_shadows])
        )
        treasury_graphs[entity_id] = build_treasury_graph(
            entity_id,
            client["entity_name"],
            client["sector"],
            int(client.get("relationship_breadth", 0)),
            client.get("top_countries", []),
            mean_entropy,
        )

    mass_errors = [
        abs(
            shadow.total_wallet.median
            - shadow.observed_bank_flow
            - shadow.latent_external_wallet.median
        )
        for shadow in shadows.values()
    ]
    sensor_registry = json.loads(SENSOR_REGISTRY.read_text(encoding="utf-8"))
    return {
        "metadata": {
            "title": "Corporate Wallet Digital Twin V3",
            "version": "3.0.0",
            "as_of": as_of.isoformat(),
            "central_idea": "Reconstruct the latent corporate financial system from one bank's partial observations, then optimize decisions and evidence acquisition under uncertainty.",
            "deployment_mode": "CLIENT_DEMO_REPRESENTATIVE_LAB",
            "watermark": "SYN BANK SIMULATION + PUBLIC E1 + REPRESENTATIVE PRIORS — RECONSTRUCTED COMPETITOR FLOWS ARE NOT MEASURED",
        },
        "opportunities": v3_opportunities,
        "shadow_reconstructions": shadows,
        "treasury_graphs": treasury_graphs,
        "action_portfolio": portfolio,
        "evidence_acquisition": evidence_plan,
        "public_sensors": sensor_registry,
        "validation": {
            "status": "REPRESENTATIVE_VALIDATION",
            "opportunities": len(v3_opportunities),
            "clients": len(treasury_graphs),
            "shadow_flow_edges": sum(len(item.flows) for item in shadows.values()),
            "max_mass_balance_error_zar": max(mass_errors, default=0.0),
            "pu_labelled_positives": sum(
                item.positive_label_observed for item in need_list
            ),
            "pu_selection_constant": need_list[0].selection_constant
            if need_list
            else None,
            "change_point_series": len(changes),
            "rm_actions_selected": len(portfolio.selected_actions),
            "rm_capacity_respected": len(portfolio.selected_actions)
            <= portfolio.capacity,
            "positive_net_voi_requests": len(evidence_plan.selected),
            "all_selected_voi_positive": all(
                item.net_value_of_information_zar > 0 for item in evidence_plan.selected
            ),
            "anonymous_provider_nodes_only": True,
            "measured_competitor_share_claims": 0,
            "causal_value_claims": 0,
        },
        "decision_selected_ids": sorted(selected_ids),
        "release": {
            "client_demo_status": "V3_DECISION_LAB_READY",
            "bank_production_status": "NOT_PROMOTABLE",
            "new_v3_capabilities": [
                "entropy-constrained shadow-wallet reconstruction",
                "positive-unlabelled product-need estimation",
                "Bayesian change-point and leakage signals",
                "CVaR-aware RM capacity portfolio",
                "decision-directed value-of-information evidence plan",
                "evidence-cited LLM claim-pack compiler",
            ],
            "blocking_external_gates": v2["release"]["blocking_gates"],
        },
    }
