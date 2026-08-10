from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

from .contracts import (
    ApprovalStatus,
    CuratedMetadata,
    DeploymentEnvironment,
    EligibilityState,
    EvidenceTier,
    OpportunityView,
    QualityStatus,
    RateCard,
    RecommendationEligibility,
)
from .economics import EconomicsService
from .public_evidence import PublicEvidenceRegistry
from .sensitivity import SensitivityEngine, SensitivityOpportunity
from .timing import TimingService
from .wallet_model import HierarchicalWalletModel


ROOT = Path(__file__).resolve().parents[2]
V1_BASELINE = ROOT / "legacy" / "v1" / "fixtures" / "portfolio.json"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _metadata(key: str, as_of: date, owner: str, domain: str, quality: QualityStatus = QualityStatus.VALID) -> CuratedMetadata:
    timestamp = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc)
    return CuratedMetadata(
        business_key=key,
        source_system_key=f"fixture:{key}",
        event_time=timestamp,
        valid_from=timestamp,
        ingestion_time=timestamp,
        source_hash=_hash(key),
        transformation_version="v1-fixture-adapter-1.0.0",
        quality_status=quality,
        data_owner=owner,
        entitlement_domain=domain,
    )


def synthetic_rate_card(product: str, rate_bps: float, as_of: date) -> RateCard:
    # The cost split is deliberately synthetic and may never pass a controlled
    # environment gate. It exists only to exercise the calculation contract.
    gross = Decimal(str(rate_bps))
    return RateCard(
        rate_card_id=f"fixture-{product.lower().replace(' ', '-')}",
        version="fixture-1.0.0",
        product=product,
        revenue_driver="annual_activity",
        gross_price_bps=gross,
        client_discount_bps=gross * Decimal("0.05"),
        ftp_bps=gross * Decimal("0.03"),
        liquidity_bps=gross * Decimal("0.02"),
        expected_loss_bps=gross * Decimal("0.02"),
        capital_bps=gross * Decimal("0.03"),
        hedging_bps=gross * Decimal("0.01"),
        execution_bps=gross * Decimal("0.01"),
        servicing_bps=gross * Decimal("0.02"),
        operating_cost_bps=gross * Decimal("0.03"),
        tax_bps=gross * Decimal("0.01"),
        acquisition_cost=Decimal("0"),
        approved_hurdle_bps=Decimal("0"),
        currency="ZAR",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        approval_status=ApprovalStatus.APPROVED,
        reconciliation_status="RECONCILED",
        synthetic=True,
        owner="Fixture Product Finance",
        metadata=_metadata(
            f"rate:{product}",
            as_of,
            "Fixture Product Finance",
            f"product:{product}",
            QualityStatus.LEGACY_INCOMPLETE,
        ),
    )


def build_fixture() -> Dict[str, Any]:
    if not V1_BASELINE.exists():
        raise FileNotFoundError("Frozen V1 portfolio baseline is missing")
    baseline = json.loads(V1_BASELINE.read_text(encoding="utf-8"))
    as_of = date.fromisoformat(baseline["metadata"]["as_of"])
    model = HierarchicalWalletModel(draws=4_000)
    economics = EconomicsService()
    timing = TimingService()
    public_evidence = PublicEvidenceRegistry(as_of)
    cards: Dict[str, RateCard] = {}
    opportunities: List[OpportunityView] = []
    sensitivity_inputs: List[SensitivityOpportunity] = []

    for raw in baseline["opportunities"]:
        anchor = raw.get("public_anchor")
        expanded_anchor = public_evidence.anchor_for(
            raw["entity_id"], raw["product"], raw["sector"], float(raw["observed_activity_zar"])
        )
        if anchor is None and expanded_anchor is not None:
            anchor = {
                "low_zar": expanded_anchor.low_zar,
                "base_zar": expanded_anchor.base_zar,
                "high_zar": expanded_anchor.high_zar,
            }
        tier = EvidenceTier.E1 if anchor else EvidenceTier.E0
        anchor_range = [anchor["low_zar"], anchor["base_zar"], anchor["high_zar"]] if anchor else None
        fact_ids = list(raw.get("anchor_impact", {}).get("fact_ids", []))
        if not fact_ids and expanded_anchor is not None:
            fact_ids = list(expanded_anchor.fact_ids)
        estimate, _, _ = model.estimate(
            opportunity_id=raw["opportunity_id"],
            entity_id=raw["entity_id"],
            product=raw["product"],
            sector=raw["sector"],
            observed_activity=float(raw["observed_activity_zar"]),
            as_of=as_of,
            evidence_tier=tier,
            anchor_range=anchor_range,
            fact_ids=fact_ids,
        )
        rate_bps = float(raw["assumptions"]["economic_rate_bps"]["base"])
        card = cards.setdefault(raw["product"], synthetic_rate_card(raw["product"], rate_bps, as_of))
        commercial = economics.evaluate(
            as_of=as_of,
            environment=DeploymentEnvironment.CLIENT_DEMO,
            rate_card=card,
            observed_activity=float(estimate.observed_activity.normalized_amount),
            wallet_median=estimate.posterior_wallet.median,
            current_share=estimate.share_interval.median,
            target_share=0.40,
        )
        raw_timing = float(raw.get("timing_score", 0.5))
        prediction = timing.predict_baseline(
            as_of=as_of,
            event_name="qualified RM action",
            seasonal_ratio=max(0.25, raw_timing / 0.58),
            recurrence=float(raw.get("recurrence", 0.5)),
        )
        reason_codes = ["CLIENT_DEMO_MODE_ACTIVE", "REPRESENTATIVE_SCENARIO_ECONOMICS"]
        if tier == EvidenceTier.E0:
            reason_codes.append("PRIOR_LED_WALLET")
        else:
            reason_codes.append("PUBLIC_PROXY_NOT_MULTIBANK_MEASUREMENT")
        opportunity = OpportunityView(
            opportunity_id=raw["opportunity_id"],
            entity_id=raw["entity_id"],
            entity_name=raw["entity_name"],
            sector=raw["sector"],
            product=raw["product"],
            as_of=as_of,
            observed_activity=estimate.observed_activity,
            identification_bounds=estimate.identification_bounds,
            posterior_wallet=estimate.posterior_wallet,
            share_interval=estimate.share_interval,
            share_claim=estimate.share_claim,
            evidence_tier=tier,
            calibration_status=estimate.calibration_status,
            freshness_days=max(0, (date(2026, 8, 8) - as_of).days),
            timing=prediction,
            commercial=commercial,
            eligibility=RecommendationEligibility(
                state=EligibilityState.SHADOW_ONLY,
                reason_codes=reason_codes,
                evaluated_at=datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc),
            ),
            evidence_fact_ids=fact_ids,
            artifacts=estimate.artifacts.model_copy(update={"rate_card_version": card.version}),
        )
        opportunities.append(opportunity)
        sensitivity_inputs.append(
            SensitivityOpportunity(
                opportunity_id=opportunity.opportunity_id,
                product=opportunity.product,
                wallet=opportunity.posterior_wallet.median,
                current_share=opportunity.share_interval.median,
                price_bps=rate_bps,
                ftp_bps=float(card.ftp_bps),
                capital_bps=float(card.capital_bps),
                anchor_active=bool(anchor),
            )
        )

    opportunities.sort(
        key=lambda item: float(item.commercial.contestable_scenario_contribution.normalized_amount)
        if item.commercial.contestable_scenario_contribution
        else 0.0,
        reverse=True,
    )
    for rank, opportunity in enumerate(opportunities, start=1):
        opportunity.rank = rank

    sensitivity_engine = SensitivityEngine(draws=10_000)
    sensitivity = sensitivity_engine.run(sensitivity_inputs)
    legacy_sensitivity = sensitivity_engine.legacy_grid(sensitivity_inputs)

    clients = {}
    for client in baseline["clients"]:
        entity_id = client["entity_id"]
        clients[entity_id] = {
            "entity_id": entity_id,
            "entity_name": client["entity_name"],
            "sector": client["sector"],
            "as_of": as_of.isoformat(),
            "relationship_breadth": client["relationship_breadth"],
            "country_count": client["country_count"],
            "public_facts": [public_evidence.fact_payload(fact) for fact in public_evidence.facts_for(entity_id)],
            "evidence_tier": "E1" if public_evidence.facts_for(entity_id) else "E0",
            "active_public_anchors": sum(
                public_evidence.anchor_for(entity_id, product, client["sector"], 1.0) is not None
                for product in ("Collections", "Payments", "Liquidity", "Cross-border FX", "Trade finance")
            ),
            "competitor_activity_status": "REPRESENTATIVE_ANALOG_ONLY_NOT_MEASURED",
            "pricing_status": "REPRESENTATIVE_SCENARIO_NOT_BANK_APPROVED",
            "opportunity_ids": [item.opportunity_id for item in opportunities if item.entity_id == entity_id],
        }

    from .benchmark_economics import evaluate_benchmark_packs
    from .genai_eval import evaluate_golden_set
    from .genai_gateway import ProviderGateway

    validation_path = ROOT / "outputs" / "v2_validation" / "offline_validation_report.json"
    genai_evaluation_path = ROOT / "outputs" / "v2_validation" / "genai_golden_eval.json"
    replay_path = ROOT / "outputs" / "v2_validation" / "shadow_replay_summary.json"
    scorecard_path = ROOT / "outputs" / "v2_validation" / "production_candidate_scorecard.json"
    evidence_qa_path = ROOT / "outputs" / "v2_validation" / "public_evidence_qa.json"
    trial_path = ROOT / "outputs" / "v2_validation" / "trial_rehearsal.json"
    operational_path = ROOT / "outputs" / "v2_validation" / "operational_rehearsal.json"
    production_target_path = ROOT / "outputs" / "v2_validation" / "production_target_validation.json"
    demo_manifest_path = ROOT / "outputs" / "client_demo" / "client_demo_data_manifest.json"
    demo_scorecard_path = ROOT / "outputs" / "client_demo" / "client_demo_scorecard.json"
    offline_validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {
        "report_version": "NOT_RUN", "global_watermark": "OFFLINE VALIDATION NOT RUN"
    }
    shadow_replay = json.loads(replay_path.read_text(encoding="utf-8")) if replay_path.exists() else {
        "events": 0, "production_release_allowed": False, "watermark": "SHADOW REPLAY NOT RUN"
    }
    release = {
        "status": "CLIENT_DEMO_READY_BANK_PRODUCTION_NOT_PROMOTABLE",
        "client_demo_status": "READY",
        "bank_production_status": "NOT_PROMOTABLE",
        "shadow_days": 0,
        "blocking_gates": [
            "representative E3 multibank calibration panel",
            "approved bank economics",
            "finance-SME approval of 51 pending public facts",
            "qualified RM-action timing outcomes",
            "real recommendation/action/outcome history",
            "bank provider approval and scanned-document golden-set adjudication",
            "bank SSO, Unity Catalog, SIEM and independent security validation",
            "30 consecutive clean shadow days",
        ],
    }
    return {
        "metadata": {
            "version": "2.1.0",
            "as_of": as_of.isoformat(),
            "deployment_mode": "CLIENT_DEMO",
            "recommendations_visible_to_rm": False,
            "recommendation_hypotheses_visible_to_demo_users": True,
            "source": "SynBank supplied simulation, audited public E1 facts, and pinned representative reference datasets transformed into governed V2 contracts",
            "watermark": "CLIENT DEMONSTRATION — SIMULATED/REPRESENTATIVE DATA — NOT FOR FINANCIAL DECISIONS",
        },
        "opportunities": opportunities,
        "clients": clients,
        "rate_cards": cards,
        "facts": {fact.fact_id: public_evidence.fact_payload(fact) for fact in public_evidence.facts},
        "sensitivity": sensitivity,
        "legacy_sensitivity": legacy_sensitivity,
        "evidence_coverage": {
            "clients": len(clients),
            "e1_clients": sum(client["evidence_tier"] == "E1" for client in clients.values()),
            "e1_facts": len(public_evidence.facts),
            "approved_e1_facts": sum(fact.approval_status == "APPROVED" for fact in public_evidence.facts),
            "pending_sme_facts": sum(fact.approval_status == "PENDING_REVIEW" for fact in public_evidence.facts),
            "e2_plus_economic_value_share": 0.0,
            "pilot_gate": 0.80,
            "pilot_ready": False,
        },
        "benchmark_economics": evaluate_benchmark_packs(opportunities, as_of),
        "offline_validation": offline_validation,
        "genai_evaluation": json.loads(genai_evaluation_path.read_text(encoding="utf-8")) if genai_evaluation_path.exists() else evaluate_golden_set(),
        "genai_provider_status": ProviderGateway().status(),
        "shadow_replay": shadow_replay,
        "production_candidate": json.loads(scorecard_path.read_text(encoding="utf-8")) if scorecard_path.exists() else {},
        "public_evidence_qa": json.loads(evidence_qa_path.read_text(encoding="utf-8")) if evidence_qa_path.exists() else {},
        "trial_rehearsal": json.loads(trial_path.read_text(encoding="utf-8")) if trial_path.exists() else {},
        "operational_rehearsal": json.loads(operational_path.read_text(encoding="utf-8")) if operational_path.exists() else {},
        "client_demo_data": json.loads(demo_manifest_path.read_text(encoding="utf-8")) if demo_manifest_path.exists() else {},
        "client_demo_scorecard": json.loads(demo_scorecard_path.read_text(encoding="utf-8")) if demo_scorecard_path.exists() else {},
        "production_target": json.loads(production_target_path.read_text(encoding="utf-8")) if production_target_path.exists() else {},
        "release": release,
    }
