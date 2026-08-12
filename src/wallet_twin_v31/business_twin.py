"""Business Model Twin construction.

One :class:`BusinessTwinSnapshot` per client per ``as_of``, carrying twelve
components.  Each component reports what is supported, what is inferred, what
is unknown and what is contradicted, together with the evidence behind every
statement.  Unknown stays unknown: a component with no evidence carries no
facts, only a description of what is missing and how to acquire it.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from wallet_twin_v2.contracts import (
    ApprovalStatus,
    ArtifactReference,
    ClaimClass,
    EvidenceTier,
)

from .business_evidence import (
    BusinessEvidenceRegistry,
    SECTOR_OPERATING_MODEL,
    SECTOR_PRIMARY_RISKS,
)
from .contracts import (
    BusinessTwinComponent,
    BusinessTwinSnapshot,
    IndicatorValue,
    V31_VERSION,
)
from .indicators import build_indicators
from .taxonomy import (
    BusinessProblem,
    BusinessTwinDomain as D,
    ComponentStatus,
    DOMAIN_LABELS,
    RESPONSIBILITY_MATRIX,
)

ROOT = Path(__file__).resolve().parents[2]
V1_BASELINE = ROOT / "legacy" / "v1" / "fixtures" / "portfolio.json"

TWIN_VERSION = "v31-business-twin-3.1.0"

WATERMARK = (
    "CLIENT DEMONSTRATION — AUDITED PUBLIC E1 FACTS + SYN BANK SIMULATION + "
    "REPRESENTATIVE POLICY — UNKNOWN INPUTS REMAIN UNKNOWN"
)

#: Materiality weights per domain.  Used to size evidence gaps and to weight
#: the change digest; they are governed policy, not learned parameters.
DOMAIN_MATERIALITY: Mapping[D, float] = {
    D.REVENUE_ENGINE: 0.95,
    D.COST_ENGINE: 0.90,
    D.WORKING_CAPITAL_CYCLE: 0.95,
    D.FUNDING_STRUCTURE: 0.95,
    D.LIQUIDITY_AND_BUFFER: 0.90,
    D.OPERATING_MODEL: 0.70,
    D.GEOGRAPHIC_EXPOSURE: 0.75,
    D.CURRENCY_AND_COMMODITY_EXPOSURE: 0.85,
    D.PROJECTS_SUBSIDIARIES_SPVS: 0.70,
    D.STAKEHOLDER_RESPONSIBILITY: 0.60,
    D.BUSINESS_AND_FINANCIAL_RISKS: 0.65,
    D.STRATEGY_ACTIONS_AND_ESG: 0.55,
}

#: Which indicators belong to which component.
DOMAIN_INDICATORS: Mapping[D, Tuple[str, ...]] = {
    D.WORKING_CAPITAL_CYCLE: ("CCC", "WORKING_CAPITAL_GAP"),
    D.LIQUIDITY_AND_BUFFER: ("LIQUIDITY_BUFFER", "CASH_COVER"),
    D.FUNDING_STRUCTURE: ("REFINANCING_EXPOSURE_12M", "LEVERAGE_PROXY"),
    D.CURRENCY_AND_COMMODITY_EXPOSURE: ("FX_EXPOSURE",),
}

#: What each component is allowed to influence downstream.
DOMAIN_DECISION_IMPACTS: Mapping[D, Dict[str, List[str]]] = {
    D.REVENUE_ENGINE: {
        "problems": [
            BusinessProblem.COLLECTIONS_INEFFICIENCY.value,
            BusinessProblem.WORKING_CAPITAL_PRESSURE.value,
        ],
        "solutions": ["COLLECTIONS", "SUPPLY_CHAIN_FINANCE"],
        "timing": ["collection seasonality"],
    },
    D.COST_ENGINE: {
        "problems": [
            BusinessProblem.PAYMENTS_INEFFICIENCY.value,
            BusinessProblem.SUPPLY_CHAIN_RISK.value,
        ],
        "solutions": ["PAYMENTS", "SUPPLY_CHAIN_FINANCE", "TRADE_FINANCE"],
        "timing": ["supplier payment runs"],
    },
    D.WORKING_CAPITAL_CYCLE: {
        "problems": [
            BusinessProblem.WORKING_CAPITAL_PRESSURE.value,
            BusinessProblem.SUPPLY_CHAIN_RISK.value,
        ],
        "solutions": [
            "WORKING_CAPITAL_REVOLVING",
            "SUPPLY_CHAIN_FINANCE",
            "TRADE_FINANCE",
        ],
        "timing": ["cash-conversion pressure points"],
    },
    D.FUNDING_STRUCTURE: {
        "problems": [
            BusinessProblem.REFINANCING_CLIFF.value,
            BusinessProblem.NEW_FUNDING_REQUIREMENT.value,
            BusinessProblem.INTEREST_RATE_EXPOSURE.value,
        ],
        "solutions": [
            "TERM_AND_SYNDICATED_LENDING",
            "DEBT_CAPITAL_MARKETS",
            "INTEREST_RATE_RISK_MANAGEMENT",
        ],
        "timing": ["debt maturity dates"],
    },
    D.LIQUIDITY_AND_BUFFER: {
        "problems": [
            BusinessProblem.LIQUIDITY_FRAGMENTATION.value,
            BusinessProblem.REFINANCING_CLIFF.value,
        ],
        "solutions": ["LIQUIDITY_CASH_MANAGEMENT", "WORKING_CAPITAL_REVOLVING"],
        "timing": ["buffer depletion"],
    },
    D.OPERATING_MODEL: {
        "problems": [
            BusinessProblem.TREASURY_CENTRALISATION.value,
            BusinessProblem.OPERATIONAL_RESILIENCE.value,
        ],
        "solutions": ["PAYMENTS", "LIQUIDITY_CASH_MANAGEMENT", "COLLECTIONS"],
        "timing": ["ERP and treasury system change windows"],
    },
    D.GEOGRAPHIC_EXPOSURE: {
        "problems": [
            BusinessProblem.FX_EXPOSURE.value,
            BusinessProblem.SUPPLY_CHAIN_RISK.value,
        ],
        "solutions": ["CROSS_BORDER_FX", "TRADE_FINANCE"],
        "timing": ["corridor seasonality"],
    },
    D.CURRENCY_AND_COMMODITY_EXPOSURE: {
        "problems": [
            BusinessProblem.FX_EXPOSURE.value,
            BusinessProblem.COMMODITY_EXPOSURE.value,
        ],
        "solutions": ["CROSS_BORDER_FX", "COMMODITY_RISK_MANAGEMENT"],
        "timing": ["hedge roll dates"],
    },
    D.PROJECTS_SUBSIDIARIES_SPVS: {
        "problems": [
            BusinessProblem.PROJECT_MOBILISATION.value,
            BusinessProblem.GUARANTEE_OR_COLLATERAL_REQUIREMENT.value,
        ],
        "solutions": ["PROJECT_FINANCE", "GUARANTEES_AND_LC", "ESCROW_AND_AGENCY"],
        "timing": ["project financial close"],
    },
    D.STAKEHOLDER_RESPONSIBILITY: {
        "problems": [],
        "solutions": [],
        "timing": ["decision-authority availability"],
    },
    D.BUSINESS_AND_FINANCIAL_RISKS: {
        "problems": [
            BusinessProblem.OPERATIONAL_RESILIENCE.value,
            BusinessProblem.COMMODITY_EXPOSURE.value,
        ],
        "solutions": ["COMMODITY_RISK_MANAGEMENT", "GUARANTEES_AND_LC"],
        "timing": ["risk-review cycle"],
    },
    D.STRATEGY_ACTIONS_AND_ESG: {
        "problems": [
            BusinessProblem.MA_OR_STRATEGIC_EVENT.value,
            BusinessProblem.ESG_TRANSITION_FUNDING.value,
            BusinessProblem.CAPITAL_STRUCTURE_EVENT.value,
        ],
        "solutions": [
            "MA_AND_STRATEGIC_ADVISORY",
            "SUSTAINABLE_FINANCE",
            "ESCROW_AND_AGENCY",
        ],
        "timing": ["announcement and results dates"],
    },
}


def _load_clients() -> Dict[str, Dict[str, Any]]:
    baseline = json.loads(V1_BASELINE.read_text(encoding="utf-8"))
    return {item["entity_id"]: item for item in baseline["clients"]}


class BusinessTwinBuilder:
    """Builds the twelve-component Business Model Twin for every client."""

    version = TWIN_VERSION

    def __init__(self, registry: BusinessEvidenceRegistry, as_of: date) -> None:
        self.registry = registry
        self.as_of = as_of
        self.clients = _load_clients()

    # -- helpers ----------------------------------------------------------
    def _component_evidence(
        self, entity_id: str, domain: D
    ) -> Tuple[List[str], EvidenceTier, ClaimClass, Optional[int], bool]:
        claims = self.registry.claims_in_domain(entity_id, domain)
        if not claims:
            return [], EvidenceTier.E0, ClaimClass.SCENARIO, None, False
        ids = sorted(claim.claim_id for claim in claims)
        best_tier = min(
            (claim.tier for claim in claims), key=lambda tier: tier.value
        )
        approved = [
            claim
            for claim in claims
            if claim.approval_status is ApprovalStatus.APPROVED
        ]
        freshest = max(claim.available_date for claim in claims)
        freshness = max(0, (self.as_of - freshest).days)
        if any(claim.claim_class is ClaimClass.OBSERVED for claim in approved):
            claim_class = ClaimClass.OBSERVED
        elif approved:
            claim_class = ClaimClass.IDENTIFIED_BOUND
        else:
            claim_class = ClaimClass.POSTERIOR
        return ids, best_tier, claim_class, freshness, bool(approved)

    def _indicators(self, entity_id: str, domain: D) -> List[IndicatorValue]:
        wanted = DOMAIN_INDICATORS.get(domain, ())
        if not wanted:
            return []
        computed = self._indicator_cache.setdefault(
            entity_id, build_indicators(self.registry, entity_id)
        )
        return [computed[key] for key in wanted if key in computed]

    def _status(
        self,
        claim_ids: Sequence[str],
        has_approved: bool,
        indicators: Sequence[IndicatorValue],
        facts: Mapping[str, Any],
    ) -> ComponentStatus:
        if not claim_ids and not facts:
            return ComponentStatus.UNKNOWN
        if has_approved and any(
            indicator.governed for indicator in indicators
        ):
            return ComponentStatus.SUPPORTED
        if has_approved and not indicators:
            return ComponentStatus.SUPPORTED
        return ComponentStatus.INFERRED

    # -- component builders ------------------------------------------------
    def _build_component(
        self,
        entity_id: str,
        domain: D,
        facts: Dict[str, Any],
        *,
        assumptions: Optional[List[str]] = None,
        contradictions: Optional[List[str]] = None,
        missing: Optional[List[str]] = None,
        force_status: Optional[ComponentStatus] = None,
    ) -> BusinessTwinComponent:
        claim_ids, tier, claim_class, freshness, has_approved = self._component_evidence(
            entity_id, domain
        )
        indicators = self._indicators(entity_id, domain)
        missing_info = list(missing or [])
        for indicator in indicators:
            if indicator.status is ComponentStatus.UNKNOWN:
                missing_info.extend(
                    f"{indicator.indicator_id}: {item}"
                    for item in indicator.missing_inputs
                )
        status = force_status or self._status(
            claim_ids, has_approved, indicators, facts
        )
        if status is ComponentStatus.UNKNOWN:
            facts = {}
            if not missing_info:
                missing_info = [
                    f"No reviewed evidence covers {DOMAIN_LABELS[domain].lower()}."
                ]
        gap = next(
            (item for item in self.registry.gaps_for(entity_id) if item.domain is domain),
            None,
        )
        if gap is not None:
            missing_info.append(gap.reason)
        pending = [
            claim_id
            for claim_id in claim_ids
            if (claim := self.registry.get(claim_id)) is not None
            and claim.approval_status is not ApprovalStatus.APPROVED
        ]
        extra_assumptions = list(assumptions or [])
        if pending:
            extra_assumptions.append(
                f"{len(pending)} supporting claim(s) await finance-SME review and "
                "cannot support a client-facing product proposal."
            )
        return BusinessTwinComponent(
            domain=domain,
            label=DOMAIN_LABELS[domain],
            status=status,
            facts=facts,
            evidence_claim_ids=claim_ids,
            claim_class=claim_class,
            evidence_tier=tier,
            materiality=DOMAIN_MATERIALITY[domain],
            freshness_days=freshness,
            valid_from=None,
            valid_to=None,
            available_date=None,
            assumptions=extra_assumptions,
            contradictions=list(contradictions or []),
            missing_information=sorted(set(missing_info)),
            indicators=indicators,
            decision_impacts=DOMAIN_DECISION_IMPACTS[domain],
        )

    def build(self, entity_id: str) -> BusinessTwinSnapshot:
        self._indicator_cache: Dict[str, Dict[str, IndicatorValue]] = getattr(
            self, "_indicator_cache", {}
        )
        client = self.clients[entity_id]
        sector = client["sector"]
        claims = self.registry.claims_for(entity_id)
        by_concept = {claim.concept: claim for claim in claims}

        def observed(concept: str) -> Optional[float]:
            claim = by_concept.get(concept)
            return claim.money_value if claim is not None else None

        def counted(concept: str) -> Optional[int]:
            claim = by_concept.get(concept)
            return claim.count_value if claim is not None else None

        components: List[BusinessTwinComponent] = []

        # 1 revenue engine
        components.append(
            self._build_component(
                entity_id,
                D.REVENUE_ENGINE,
                {
                    "bank_observed_collections_ltm_zar": observed(
                        "bank_observed_collections_ltm"
                    ),
                    "collections_yoy_change": (
                        by_concept.get("bank_observed_collections_yoy_change").ratio_value
                        if "bank_observed_collections_yoy_change" in by_concept
                        else None
                    ),
                    "audited_revenue_available": "revenue" in by_concept
                    or "insurance_revenue" in by_concept
                    or "gross_rental_income" in by_concept,
                },
                assumptions=[
                    "Bank-observed collections are a lower bound on total client inflows."
                ],
            )
        )

        # 2 cost engine
        components.append(
            self._build_component(
                entity_id,
                D.COST_ENGINE,
                {
                    "bank_observed_payments_ltm_zar": observed(
                        "bank_observed_payments_ltm"
                    ),
                    "payments_yoy_change": (
                        by_concept.get("bank_observed_payments_yoy_change").ratio_value
                        if "bank_observed_payments_yoy_change" in by_concept
                        else None
                    ),
                    "audited_cost_base_available": "operating_cost_base" in by_concept,
                },
                assumptions=[
                    "Bank-observed supplier payments are a lower bound on the total cost base."
                ],
            )
        )

        # 3 working-capital cycle
        components.append(
            self._build_component(
                entity_id,
                D.WORKING_CAPITAL_CYCLE,
                {
                    "bank_observed_trade_finance_ltm_zar": observed(
                        "bank_observed_trade_finance_ltm"
                    ),
                    "trade_events_next_90d": counted(
                        "bank_observed_trade_events_next_90d"
                    ),
                    "working_capital_intensity_index": (
                        by_concept.get(
                            "bank_observed_working_capital_intensity_index"
                        ).ratio_value
                        if "bank_observed_working_capital_intensity_index" in by_concept
                        else None
                    ),
                },
            )
        )

        # 4 funding structure
        components.append(
            self._build_component(
                entity_id,
                D.FUNDING_STRUCTURE,
                {
                    "financing_need_index": (
                        by_concept.get("bank_observed_financing_need_index").ratio_value
                        if "bank_observed_financing_need_index" in by_concept
                        else None
                    ),
                    "audited_debt_disclosure_available": any(
                        concept in by_concept
                        for concept in (
                            "current_debt",
                            "term_finance",
                            "current_liabilities",
                            "insurance_liabilities",
                        )
                    ),
                    "dated_maturity_window_available": "current_debt_maturity_window"
                    in by_concept,
                },
                assumptions=[
                    "Only current borrowings and disclosed short-term facilities are "
                    "visible; the full maturity ladder is not public."
                ],
                missing=["full debt maturity ladder by instrument and tenor"],
            )
        )

        # 5 liquidity and cash buffer
        components.append(
            self._build_component(
                entity_id,
                D.LIQUIDITY_AND_BUFFER,
                {
                    "bank_observed_liquidity_ltm_zar": observed(
                        "bank_observed_liquidity_ltm"
                    ),
                    "liquidity_volatility_index": (
                        by_concept.get(
                            "bank_observed_liquidity_volatility_index"
                        ).ratio_value
                        if "bank_observed_liquidity_volatility_index" in by_concept
                        else None
                    ),
                },
                missing=["undrawn committed facility headroom"],
            )
        )

        # 6 operating model
        operating_model_claim = by_concept.get("sector_operating_model")
        components.append(
            self._build_component(
                entity_id,
                D.OPERATING_MODEL,
                {
                    "operating_model_statement": operating_model_claim.text_value
                    if operating_model_claim
                    else SECTOR_OPERATING_MODEL.get(sector),
                    "bank_product_relationship_breadth": counted(
                        "bank_observed_product_relationship_breadth"
                    ),
                    "operating_scale_index": (
                        by_concept.get("bank_observed_operating_scale_index").ratio_value
                        if "bank_observed_operating_scale_index" in by_concept
                        else None
                    ),
                    "relationship_complexity_index": (
                        by_concept.get(
                            "bank_observed_relationship_complexity_index"
                        ).ratio_value
                        if "bank_observed_relationship_complexity_index" in by_concept
                        else None
                    ),
                },
                assumptions=[
                    "The operating-model statement is a governed sector description, "
                    "not a client-specific disclosure."
                ],
                missing=["client-specific ERP, shared-service and treasury system detail"],
            )
        )

        # 7 geographic exposure
        corridors = [
            claim
            for claim in claims
            if claim.concept == "bank_observed_corridor_country"
        ]
        corridor_values = [
            claim
            for claim in claims
            if claim.concept == "bank_observed_corridor_value"
        ]
        components.append(
            self._build_component(
                entity_id,
                D.GEOGRAPHIC_EXPOSURE,
                {
                    "active_country_count": counted(
                        "bank_observed_active_country_count"
                    ),
                    "top_corridors": [
                        claim.categorical_value for claim in corridors
                    ],
                    "top_corridor_values_zar": [
                        claim.money_value for claim in corridor_values
                    ],
                    "international_exposure_index": (
                        by_concept.get(
                            "bank_observed_international_exposure_index"
                        ).ratio_value
                        if "bank_observed_international_exposure_index" in by_concept
                        else None
                    ),
                },
                assumptions=[
                    "Corridors reflect bank-observed flow only; corridors served by "
                    "other banks are not visible."
                ],
            )
        )

        # 8 currency and commodity exposure
        currencies = [
            claim for claim in claims if claim.concept == "bank_observed_currency_pair"
        ]
        commodity_exposed = sector in ("mining",)
        components.append(
            self._build_component(
                entity_id,
                D.CURRENCY_AND_COMMODITY_EXPOSURE,
                {
                    "top_currency_pairs": [
                        claim.categorical_value for claim in currencies
                    ],
                    "bank_observed_cross_border_fx_ltm_zar": observed(
                        "bank_observed_cross_border_fx_ltm"
                    ),
                    "audited_fx_exposure_available": "fx_exposure" in by_concept,
                    "commodity_linked_sector": commodity_exposed,
                },
                assumptions=[
                    "Cross-border turnover is gross; the signed inflow/outflow split "
                    "and the hedge ratio are not observable."
                ],
                missing=["hedge ratio", "signed currency inflow/outflow split"]
                + ([] if not commodity_exposed else ["commodity hedge programme detail"]),
            )
        )

        # 9 projects, subsidiaries and SPVs
        components.append(
            self._build_component(
                entity_id,
                D.PROJECTS_SUBSIDIARIES_SPVS,
                {},
                force_status=ComponentStatus.UNKNOWN,
                missing=[
                    "reviewed legal-entity, subsidiary and SPV topology",
                    "project pipeline with financial-close dates",
                ],
            )
        )

        # 10 stakeholder responsibility model
        responsibility_claim = by_concept.get("stakeholder_responsibility_model")
        components.append(
            self._build_component(
                entity_id,
                D.STAKEHOLDER_RESPONSIBILITY,
                {
                    "model": responsibility_claim.text_value
                    if responsibility_claim
                    else None,
                    "role_personas_only": True,
                    "named_contacts_resolved": False,
                    "example_ownership": {
                        problem.value: RESPONSIBILITY_MATRIX[problem].primary.value
                        for problem in (
                            BusinessProblem.FX_EXPOSURE,
                            BusinessProblem.REFINANCING_CLIFF,
                            BusinessProblem.WORKING_CAPITAL_PRESSURE,
                        )
                    },
                },
                assumptions=[
                    "Responsibility is assigned by governed matrix, not by an "
                    "unvalidated person-ranking model."
                ],
                missing=["client-confirmed decision authority and mandate limits"],
            )
        )

        # 11 business and financial risks
        components.append(
            self._build_component(
                entity_id,
                D.BUSINESS_AND_FINANCIAL_RISKS,
                {
                    "representative_sector_risks": list(
                        SECTOR_PRIMARY_RISKS.get(sector, ())
                    ),
                    "client_specific_risk_disclosure_extracted": False,
                },
                assumptions=[
                    "Risks are representative sector risks, not extracted client "
                    "risk-report statements."
                ],
                missing=["client risk-report extraction"],
            )
        )

        # 12 strategy, corporate actions and ESG
        components.append(
            self._build_component(
                entity_id,
                D.STRATEGY_ACTIONS_AND_ESG,
                {
                    "event_intensity_index": (
                        by_concept.get("bank_observed_event_intensity_index").ratio_value
                        if "bank_observed_event_intensity_index" in by_concept
                        else None
                    ),
                },
                assumptions=[
                    "Event intensity is a bank-observed activity signal, not a "
                    "disclosed corporate-action calendar."
                ],
                missing=[
                    "announced corporate actions",
                    "evidence-based ESG activity and transition targets",
                ],
            )
        )

        approved = self.registry.approved_claims_for(entity_id)
        supported = sum(
            1
            for component in components
            if component.status
            in (ComponentStatus.SUPPORTED, ComponentStatus.INFERRED)
        )
        return BusinessTwinSnapshot(
            snapshot_id=f"twin:{entity_id}:{self.as_of.isoformat()}:{V31_VERSION}",
            entity_id=entity_id,
            entity_name=client["entity_name"],
            sector=sector,
            as_of=self.as_of,
            snapshot_version=V31_VERSION,
            legal_entity_ids=[entity_id],
            components=components,
            evidence_gaps=self.registry.gaps_for(entity_id),
            claim_count=len(claims),
            approved_claim_count=len(approved),
            supported_domain_count=supported,
            watermark=WATERMARK,
            artifacts=ArtifactReference(
                model_version=TWIN_VERSION,
                dataset_version=self.registry.version,
                prior_version="v31-governed-policy-3.1.0",
                transformation_version=TWIN_VERSION,
                schema_version="3.1.0",
            ),
        )

    def build_all(self) -> Dict[str, BusinessTwinSnapshot]:
        return {entity_id: self.build(entity_id) for entity_id in sorted(self.clients)}
