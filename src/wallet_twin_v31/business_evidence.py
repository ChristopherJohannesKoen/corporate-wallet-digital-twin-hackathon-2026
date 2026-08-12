"""Typed business evidence for the V3.1 Business Model Twin.

Three honest sources feed this registry, and they are never blended:

1. **E1 audited public facts** — the 82 point-in-time facts already curated in
   V2.  They are migrated and re-linked to Business Twin domains, not
   re-derived and never invented.  31 are finance-SME approved; 51 remain
   ``PENDING_REVIEW`` and therefore cannot support an eligible client-facing
   conversation.
2. **E0 bank-observed claims** — quantities the bank genuinely holds in its own
   books, taken from the Syn Bank simulation: product flows, corridor and
   currency exposures, relationship breadth and dated trade events.  These are
   ``OBSERVED`` claims with ``SYNTHETIC_SIMULATION`` provenance.
3. **E0 representative structural claims** — sector operating-model and
   responsibility statements derived from governed policy, marked ``INFERRED``
   and ``REPRESENTATIVE_PUBLIC``.

Anything a document does not say is recorded as an :class:`EvidenceGap`.  No
number is fabricated to fill a domain, and no claim is upgraded past the tier
its source can support.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from wallet_twin_v2.contracts import (
    ApprovalStatus,
    ClaimClass,
    CuratedMetadata,
    DataProvenanceClass,
    EvidenceTier,
    QualityStatus,
)
from wallet_twin_v2.public_evidence import PublicEvidenceRegistry, PublicFact

from .contracts import BusinessEvidenceClaim, EvidenceGap
from .taxonomy import (
    BusinessClaimKind,
    BusinessProblem,
    BusinessTwinDomain as D,
    RESPONSIBILITY_MATRIX,
    RESPONSIBILITY_MATRIX_VERSION,
)

ROOT = Path(__file__).resolve().parents[2]
V1_BASELINE = ROOT / "legacy" / "v1" / "fixtures" / "portfolio.json"

EVIDENCE_VERSION = "v31-business-evidence-3.1.0"
REVIEWER_FINANCE_SME = "finance-sme-01"
REVIEWER_COVERAGE = "coverage-analytics-01"

#: Minimum curation thresholds from the V3.1 plan.  ``min_e1_claims`` is
#: reported honestly: the real audited public evidence base does not reach 15
#: E1 claims for every client, and that shortfall is a blocking gate rather
#: than something to paper over with invented facts.
MIN_CLAIMS_PER_CLIENT = 15
MIN_DOMAINS_PER_CLIENT = 9
MIN_E1_CLAIMS_PER_CLIENT = 15
MIN_TOTAL_CLAIMS = 300


CONCEPT_DOMAINS: Mapping[str, Tuple[D, ...]] = {
    "revenue": (D.REVENUE_ENGINE,),
    "insurance_revenue": (D.REVENUE_ENGINE,),
    "gross_rental_income": (D.REVENUE_ENGINE,),
    "operating_cost_base": (D.COST_ENGINE,),
    "trade_payables": (D.COST_ENGINE, D.WORKING_CAPITAL_CYCLE),
    "trade_payables_open": (D.COST_ENGINE, D.WORKING_CAPITAL_CYCLE),
    "trade_payables_close": (D.COST_ENGINE, D.WORKING_CAPITAL_CYCLE),
    "trade_receivables_open": (D.REVENUE_ENGINE, D.WORKING_CAPITAL_CYCLE),
    "trade_receivables_close": (D.REVENUE_ENGINE, D.WORKING_CAPITAL_CYCLE),
    "inventories_open": (D.WORKING_CAPITAL_CYCLE,),
    "inventories_close": (D.WORKING_CAPITAL_CYCLE,),
    "current_debt": (D.FUNDING_STRUCTURE,),
    "term_finance": (D.FUNDING_STRUCTURE,),
    "short_term_facilities": (D.FUNDING_STRUCTURE, D.LIQUIDITY_AND_BUFFER),
    "current_liabilities": (D.FUNDING_STRUCTURE,),
    "insurance_liabilities": (D.FUNDING_STRUCTURE,),
    "cash_and_cash_equivalents": (D.LIQUIDITY_AND_BUFFER,),
    "fx_exposure": (D.CURRENCY_AND_COMMODITY_EXPOSURE,),
}

#: Facts that sit on the critical path of at least one client-facing problem.
CRITICAL_PATH_CONCEPTS = frozenset(
    {
        "revenue",
        "insurance_revenue",
        "gross_rental_income",
        "operating_cost_base",
        "current_debt",
        "term_finance",
        "short_term_facilities",
        "cash_and_cash_equivalents",
        "fx_exposure",
        "trade_receivables_close",
        "trade_payables_close",
        "inventories_close",
    }
)

PRODUCT_DOMAINS: Mapping[str, Tuple[D, ...]] = {
    "Collections": (D.REVENUE_ENGINE, D.WORKING_CAPITAL_CYCLE),
    "Payments": (D.COST_ENGINE, D.WORKING_CAPITAL_CYCLE),
    "Liquidity": (D.LIQUIDITY_AND_BUFFER,),
    "Cross-border FX": (D.CURRENCY_AND_COMMODITY_EXPOSURE, D.GEOGRAPHIC_EXPOSURE),
    "Trade finance": (D.WORKING_CAPITAL_CYCLE, D.OPERATING_MODEL),
}

LATENT_STATE_DOMAINS: Mapping[str, Tuple[D, str]] = {
    "operating_scale": (D.OPERATING_MODEL, "Relative operating scale index"),
    "working_capital_intensity": (
        D.WORKING_CAPITAL_CYCLE,
        "Working-capital intensity index",
    ),
    "liquidity_volatility": (D.LIQUIDITY_AND_BUFFER, "Observed liquidity volatility"),
    "international_exposure": (D.GEOGRAPHIC_EXPOSURE, "International exposure index"),
    "financing_need": (D.FUNDING_STRUCTURE, "Modelled financing-need index"),
    "event_intensity": (D.STRATEGY_ACTIONS_AND_ESG, "Corporate-event intensity index"),
    "relationship_complexity": (
        D.OPERATING_MODEL,
        "Banking-relationship complexity index",
    ),
}

SECTOR_OPERATING_MODEL: Mapping[str, str] = {
    "mining": "Multi-jurisdiction extractive operator with commodity-linked revenue, long-cycle capex and joint-venture structures.",
    "consumer": "High-frequency retail/distribution operator with dense supplier payment cycles and inventory-led working capital.",
    "industrials_pharma": "Manufacturing and distribution operator with regulated product flows and cross-border input sourcing.",
    "telecoms": "Capital-intensive network operator with recurring subscriber collections and multi-country licence obligations.",
    "tech": "Platform/holding operator with international investment holdings and treasury-managed portfolio cash.",
    "insurance": "Regulated underwriter with premium collections, claims payment cycles and investment-portfolio liquidity.",
    "real_estate": "Property owner-operator with rental collections, asset-level debt and development capex cycles.",
}

SECTOR_PRIMARY_RISKS: Mapping[str, Tuple[str, ...]] = {
    "mining": ("commodity price volatility", "jurisdictional and permitting risk", "capex overrun"),
    "consumer": ("supplier concentration", "consumer demand cyclicality", "cross-border sourcing cost"),
    "industrials_pharma": ("regulatory approval risk", "input cost inflation", "supply-chain continuity"),
    "telecoms": ("licence and spectrum cost", "currency translation on multi-country earnings", "capex funding"),
    "tech": ("portfolio valuation volatility", "cross-border capital mobility", "translation exposure"),
    "insurance": ("claims volatility", "investment-portfolio duration", "regulatory capital"),
    "real_estate": ("interest-rate sensitivity of asset-level debt", "tenant concentration", "development funding"),
}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _metadata(
    key: str,
    as_of: date,
    owner: str,
    domain: str,
    *,
    quality: QualityStatus = QualityStatus.VALID,
    source_hash: Optional[str] = None,
) -> CuratedMetadata:
    timestamp = datetime.combine(as_of, datetime.min.time(), tzinfo=timezone.utc)
    return CuratedMetadata(
        business_key=key,
        source_system_key=f"v31-business-evidence:{key}",
        event_time=timestamp,
        valid_from=timestamp,
        ingestion_time=timestamp,
        source_hash=source_hash or _hash(key),
        transformation_version=EVIDENCE_VERSION,
        quality_status=quality,
        data_owner=owner,
        entitlement_domain=f"client:{key.split(':')[0]}",
    )


class BusinessEvidenceRegistry:
    """Point-in-time typed business evidence for all 20 demonstration clients."""

    version = EVIDENCE_VERSION

    def __init__(self, as_of: date) -> None:
        self.as_of = as_of
        self._public = PublicEvidenceRegistry(as_of)
        baseline = json.loads(V1_BASELINE.read_text(encoding="utf-8"))
        self._clients: Dict[str, Dict[str, Any]] = {
            item["entity_id"]: item for item in baseline["clients"]
        }
        self.claims: List[BusinessEvidenceClaim] = []
        self.gaps: List[EvidenceGap] = []
        self._by_entity: Dict[str, List[BusinessEvidenceClaim]] = {}
        self._by_id: Dict[str, BusinessEvidenceClaim] = {}
        self._build()

    # -- construction -----------------------------------------------------
    def _build(self) -> None:
        for entity_id in sorted(self._clients):
            client = self._clients[entity_id]
            claims: List[BusinessEvidenceClaim] = []
            claims.extend(self._migrate_public_facts(entity_id, client))
            claims.extend(self._bank_observed_claims(entity_id, client))
            claims.extend(self._structural_claims(entity_id, client))
            claims = [claim for claim in claims if claim.available_date <= self.as_of]
            self._by_entity[entity_id] = claims
            self.claims.extend(claims)
            self.gaps.extend(self._gap_records(entity_id, claims))
        self._by_id = {claim.claim_id: claim for claim in self.claims}

    def _migrate_public_facts(
        self, entity_id: str, client: Dict[str, Any]
    ) -> List[BusinessEvidenceClaim]:
        """Re-link the existing E1 facts; values, sources and pages are untouched."""
        migrated: List[BusinessEvidenceClaim] = []
        for fact in self._public.facts_for(entity_id):
            domains = CONCEPT_DOMAINS.get(fact.concept)
            if domains is None:
                continue
            approved = fact.approval_status == "APPROVED"
            migrated.append(
                BusinessEvidenceClaim(
                    claim_id=f"bec:{fact.fact_id}",
                    entity_id=entity_id,
                    domains=list(domains),
                    kind=BusinessClaimKind.MONEY,
                    concept=fact.concept,
                    money_value=fact.value,
                    currency=fact.currency,
                    unit=fact.unit,
                    period_start=fact.period_start,
                    period_end=fact.period_end,
                    source_date=fact.available_date,
                    available_date=fact.available_date,
                    source_title=fact.source_title,
                    source_url=fact.source_url,
                    source_hash=fact.document_hash,
                    page=fact.page,
                    supporting_text=None,
                    extraction_method="migrated V2 audited public fact (value unchanged)",
                    tier=EvidenceTier.E1,
                    claim_class=ClaimClass.OBSERVED,
                    provenance=DataProvenanceClass.PUBLIC_AUDITED,
                    approval_status=ApprovalStatus.APPROVED
                    if approved
                    else ApprovalStatus.PENDING_REVIEW,
                    reviewer_id=REVIEWER_FINANCE_SME if approved else None,
                    reviewer_role="Finance SME" if approved else None,
                    reviewed_at=datetime.combine(
                        fact.available_date, datetime.min.time(), tzinfo=timezone.utc
                    )
                    if approved
                    else None,
                    material=True,
                    critical_path=fact.concept in CRITICAL_PATH_CONCEPTS,
                    legacy_fact_id=fact.fact_id,
                    metadata=_metadata(
                        f"{entity_id}:public:{fact.fact_id}",
                        self.as_of,
                        "Evidence Review",
                        entity_id,
                        source_hash=fact.document_hash,
                    ),
                )
            )
        return migrated

    def _bank_observed_claims(
        self, entity_id: str, client: Dict[str, Any]
    ) -> List[BusinessEvidenceClaim]:
        claims: List[BusinessEvidenceClaim] = []
        period_start = date(self.as_of.year - 1, self.as_of.month, 1)

        def observed(
            key: str,
            concept: str,
            domains: Sequence[D],
            kind: BusinessClaimKind,
            *,
            money: Optional[float] = None,
            ratio: Optional[float] = None,
            count: Optional[int] = None,
            categorical: Optional[str] = None,
            unit: str = "ZAR",
            critical: bool = False,
            text: Optional[str] = None,
        ) -> BusinessEvidenceClaim:
            claim_key = f"{entity_id}:obs:{key}"
            return BusinessEvidenceClaim(
                claim_id=f"bec:{claim_key}",
                entity_id=entity_id,
                domains=list(domains),
                kind=kind,
                concept=concept,
                money_value=money,
                currency="ZAR" if money is not None else None,
                unit=unit,
                ratio_value=ratio,
                count_value=count,
                categorical_value=categorical,
                text_value=text,
                period_start=period_start,
                period_end=self.as_of,
                source_date=self.as_of,
                available_date=self.as_of,
                source_title="Syn Bank transaction and relationship simulation",
                source_url="internal://syn-bank/simulation/ltm",
                source_hash=_hash(claim_key),
                extraction_method="deterministic aggregation of bank-held flows",
                tier=EvidenceTier.E0,
                claim_class=ClaimClass.OBSERVED,
                provenance=DataProvenanceClass.SYNTHETIC_SIMULATION,
                approval_status=ApprovalStatus.APPROVED,
                reviewer_id=REVIEWER_COVERAGE,
                reviewer_role="Coverage Analytics",
                reviewed_at=datetime.combine(
                    self.as_of, datetime.min.time(), tzinfo=timezone.utc
                ),
                material=True,
                critical_path=critical,
                metadata=_metadata(
                    claim_key, self.as_of, "Coverage Analytics", entity_id
                ),
            )

        monthly: Dict[str, List[Dict[str, Any]]] = client["monthly"]
        for product, series in monthly.items():
            values = [float(item["value_zar"]) for item in series]
            ltm = sum(values[-12:])
            prior = sum(values[-24:-12]) or 1.0
            domains = PRODUCT_DOMAINS[product]
            slug = product.lower().replace(" ", "-")
            claims.append(
                observed(
                    f"flow:{slug}",
                    f"bank_observed_{slug.replace('-', '_')}_ltm",
                    domains,
                    BusinessClaimKind.MONEY,
                    money=ltm,
                    critical=True,
                )
            )
            claims.append(
                observed(
                    f"trend:{slug}",
                    f"bank_observed_{slug.replace('-', '_')}_yoy_change",
                    domains,
                    BusinessClaimKind.RATIO,
                    ratio=round(ltm / prior - 1.0, 6),
                    unit="ratio",
                )
            )

        for index, country in enumerate(client.get("top_countries", [])[:3]):
            claims.append(
                observed(
                    f"corridor:{index}",
                    "bank_observed_corridor_value",
                    (D.GEOGRAPHIC_EXPOSURE,),
                    BusinessClaimKind.MONEY,
                    money=float(country["value_zar"]),
                    critical=index == 0,
                )
            )
            claims.append(
                observed(
                    f"corridor-name:{index}",
                    "bank_observed_corridor_country",
                    (D.GEOGRAPHIC_EXPOSURE,),
                    BusinessClaimKind.CATEGORICAL,
                    categorical=str(country["name"]),
                    unit="country",
                )
            )

        for index, currency in enumerate(client.get("top_currencies", [])[:3]):
            claims.append(
                observed(
                    f"currency:{index}",
                    "bank_observed_currency_pair_value",
                    (D.CURRENCY_AND_COMMODITY_EXPOSURE,),
                    BusinessClaimKind.MONEY,
                    money=float(currency["value_zar"]),
                    critical=index == 0,
                )
            )
            claims.append(
                observed(
                    f"currency-pair:{index}",
                    "bank_observed_currency_pair",
                    (D.CURRENCY_AND_COMMODITY_EXPOSURE,),
                    BusinessClaimKind.CATEGORICAL,
                    categorical=str(currency["name"]),
                    unit="currency_pair",
                )
            )

        claims.append(
            observed(
                "country-count",
                "bank_observed_active_country_count",
                (D.GEOGRAPHIC_EXPOSURE,),
                BusinessClaimKind.COUNT,
                count=int(client.get("country_count", 0)),
                unit="countries",
                critical=True,
            )
        )
        claims.append(
            observed(
                "relationship-breadth",
                "bank_observed_product_relationship_breadth",
                (D.OPERATING_MODEL,),
                BusinessClaimKind.COUNT,
                count=int(client.get("relationship_breadth", 0)),
                unit="products",
                critical=True,
            )
        )

        for name, value in client.get("latent_state", {}).items():
            domain, label = LATENT_STATE_DOMAINS[name]
            claims.append(
                observed(
                    f"latent:{name}",
                    f"bank_observed_{name}_index",
                    (domain,),
                    BusinessClaimKind.RATIO,
                    ratio=round(float(value) / 100.0, 6),
                    unit="index_0_1",
                    text=None,
                )
            )

        timing = client.get("timing", {})
        if "trade_events_next_90d" in timing:
            claims.append(
                observed(
                    "events:trade-90d",
                    "bank_observed_trade_events_next_90d",
                    (D.OPERATING_MODEL, D.WORKING_CAPITAL_CYCLE),
                    BusinessClaimKind.COUNT,
                    count=int(timing["trade_events_next_90d"]),
                    unit="events",
                    critical=True,
                )
            )
        if "trade_events_value_zar" in timing:
            claims.append(
                observed(
                    "events:trade-90d-value",
                    "bank_observed_trade_events_value_next_90d",
                    (D.WORKING_CAPITAL_CYCLE,),
                    BusinessClaimKind.MONEY,
                    money=float(timing["trade_events_value_zar"]),
                )
            )

        anchor = client.get("debt_maturity_anchor")
        if anchor:
            claim_key = f"{entity_id}:maturity:current-debt"
            fact_ids = list(anchor.get("fact_ids", []))
            underlying = [
                fact
                for fact in self._public.facts_for(entity_id)
                if fact.fact_id in fact_ids
            ]
            approved = bool(underlying) and all(
                fact.approval_status == "APPROVED" for fact in underlying
            )
            available = (
                max(fact.available_date for fact in underlying)
                if underlying
                else date.fromisoformat(anchor["available_date"])
            )
            period_end = date.fromisoformat(anchor["period_end"])
            claims.append(
                BusinessEvidenceClaim(
                    claim_id=f"bec:{claim_key}",
                    entity_id=entity_id,
                    domains=[D.FUNDING_STRUCTURE, D.LIQUIDITY_AND_BUFFER],
                    kind=BusinessClaimKind.DATE_OR_MATURITY,
                    concept="current_debt_maturity_window",
                    money_value=float(anchor["base_zar"]),
                    currency="ZAR",
                    unit="ZAR",
                    maturity_window_start=period_end,
                    maturity_window_end=date(period_end.year + 1, period_end.month, 1),
                    date_value=period_end,
                    period_start=date(period_end.year - 1, period_end.month, 1),
                    period_end=period_end,
                    source_date=available,
                    available_date=available,
                    source_title=anchor.get("name", "Audited debt-maturity anchor"),
                    source_url=underlying[0].source_url
                    if underlying
                    else "internal://v1/debt-maturity-anchor",
                    source_hash=underlying[0].document_hash
                    if underlying
                    else _hash(claim_key),
                    page=underlying[0].page if underlying else None,
                    supporting_text=anchor.get("formula"),
                    extraction_method="audited current borrowings and disclosed short-term facilities",
                    tier=EvidenceTier.E1 if underlying else EvidenceTier.E0,
                    claim_class=ClaimClass.IDENTIFIED_BOUND,
                    provenance=DataProvenanceClass.PUBLIC_AUDITED
                    if underlying
                    else DataProvenanceClass.REPRESENTATIVE_PUBLIC,
                    approval_status=ApprovalStatus.APPROVED
                    if approved
                    else ApprovalStatus.PENDING_REVIEW,
                    reviewer_id=REVIEWER_FINANCE_SME if approved else None,
                    reviewer_role="Finance SME" if approved else None,
                    reviewed_at=datetime.combine(
                        available, datetime.min.time(), tzinfo=timezone.utc
                    )
                    if approved
                    else None,
                    material=True,
                    critical_path=True,
                    legacy_fact_id=fact_ids[0] if fact_ids else None,
                    metadata=_metadata(
                        claim_key, self.as_of, "Evidence Review", entity_id
                    ),
                )
            )
        return claims

    def _structural_claims(
        self, entity_id: str, client: Dict[str, Any]
    ) -> List[BusinessEvidenceClaim]:
        """Representative operating-model, responsibility and risk statements."""
        sector = client["sector"]
        claims: List[BusinessEvidenceClaim] = []

        def structural(
            key: str,
            concept: str,
            domains: Sequence[D],
            kind: BusinessClaimKind,
            *,
            text: Optional[str] = None,
            categorical: Optional[str] = None,
            subject: Optional[str] = None,
            predicate: Optional[str] = None,
            obj: Optional[str] = None,
        ) -> BusinessEvidenceClaim:
            claim_key = f"{entity_id}:struct:{key}"
            return BusinessEvidenceClaim(
                claim_id=f"bec:{claim_key}",
                entity_id=entity_id,
                domains=list(domains),
                kind=kind,
                concept=concept,
                text_value=text,
                categorical_value=categorical,
                relationship_subject=subject,
                relationship_predicate=predicate,
                relationship_object=obj,
                unit="statement",
                period_start=date(self.as_of.year - 1, self.as_of.month, 1),
                period_end=self.as_of,
                source_date=self.as_of,
                available_date=self.as_of,
                source_title="Governed sector operating-model and responsibility policy",
                source_url="internal://v31/governed-policy",
                source_hash=_hash(claim_key),
                extraction_method="governed policy lookup (no document extraction)",
                tier=EvidenceTier.E0,
                claim_class=ClaimClass.SCENARIO,
                provenance=DataProvenanceClass.REPRESENTATIVE_PUBLIC,
                approval_status=ApprovalStatus.APPROVED,
                reviewer_id=REVIEWER_COVERAGE,
                reviewer_role="Coverage Analytics",
                reviewed_at=datetime.combine(
                    self.as_of, datetime.min.time(), tzinfo=timezone.utc
                ),
                material=False,
                critical_path=False,
                metadata=_metadata(
                    claim_key, self.as_of, "Coverage Analytics", entity_id
                ),
            )

        claims.append(
            structural(
                "operating-model",
                "sector_operating_model",
                (D.OPERATING_MODEL,),
                BusinessClaimKind.TEXTUAL,
                text=SECTOR_OPERATING_MODEL.get(
                    sector, "Diversified corporate operating model."
                ),
            )
        )
        for index, risk in enumerate(SECTOR_PRIMARY_RISKS.get(sector, ())):
            claims.append(
                structural(
                    f"risk:{index}",
                    "sector_primary_risk",
                    (D.BUSINESS_AND_FINANCIAL_RISKS,),
                    BusinessClaimKind.CATEGORICAL,
                    categorical=risk,
                )
            )
        claims.append(
            structural(
                "responsibility-model",
                "stakeholder_responsibility_model",
                (D.STAKEHOLDER_RESPONSIBILITY,),
                BusinessClaimKind.TEXTUAL,
                text=(
                    "Responsibility is assigned by role persona using governed matrix "
                    f"{RESPONSIBILITY_MATRIX_VERSION}. Named individuals are not resolved "
                    "in the demonstration and require CRM entitlement checks in production."
                ),
            )
        )
        for problem in (
            BusinessProblem.FX_EXPOSURE,
            BusinessProblem.REFINANCING_CLIFF,
            BusinessProblem.WORKING_CAPITAL_PRESSURE,
        ):
            rule = RESPONSIBILITY_MATRIX[problem]
            claims.append(
                structural(
                    f"responsibility:{problem.value.lower()}",
                    "problem_role_ownership",
                    (D.STAKEHOLDER_RESPONSIBILITY,),
                    BusinessClaimKind.STRUCTURE_RELATIONSHIP,
                    subject=problem.value,
                    predicate="IS_OWNED_BY_ROLE",
                    obj=rule.primary.value,
                )
            )
        return claims

    def _gap_records(
        self, entity_id: str, claims: Sequence[BusinessEvidenceClaim]
    ) -> List[EvidenceGap]:
        covered = {domain for claim in claims for domain in claim.domains}
        gaps: List[EvidenceGap] = []
        specs: Mapping[D, Tuple[str, Tuple[BusinessProblem, ...], str]] = {
            D.PROJECTS_SUBSIDIARIES_SPVS: (
                "No reviewed subsidiary, SPV or project-level disclosure is available for this client; "
                "ownership must not be inferred from name similarity.",
                (
                    BusinessProblem.PROJECT_MOBILISATION,
                    BusinessProblem.GUARANTEE_OR_COLLATERAL_REQUIREMENT,
                ),
                "GLEIF/registry resolution with deterministic matching and human review",
            ),
            D.STRATEGY_ACTIONS_AND_ESG: (
                "No reviewed strategy, corporate-action or ESG-activity disclosure has been extracted.",
                (
                    BusinessProblem.ESG_TRANSITION_FUNDING,
                    BusinessProblem.MA_OR_STRATEGIC_EVENT,
                ),
                "annual-report narrative extraction with finance-SME review",
            ),
            D.BUSINESS_AND_FINANCIAL_RISKS: (
                "No client-specific risk disclosure has been extracted; only representative sector risks exist.",
                (BusinessProblem.OPERATIONAL_RESILIENCE,),
                "risk-report extraction with finance-SME review",
            ),
            D.COST_ENGINE: (
                "No audited cost base is available for this client.",
                (BusinessProblem.WORKING_CAPITAL_PRESSURE,),
                "annual-report extraction with finance-SME review",
            ),
            D.WORKING_CAPITAL_CYCLE: (
                "No audited receivables/payables/inventory cycle is available for this client.",
                (BusinessProblem.WORKING_CAPITAL_PRESSURE,),
                "annual-report extraction with finance-SME review",
            ),
            D.FUNDING_STRUCTURE: (
                "No audited debt or facility disclosure is available for this client.",
                (BusinessProblem.REFINANCING_CLIFF,),
                "annual-report extraction with finance-SME review",
            ),
        }
        approved_domains = {
            domain
            for claim in claims
            for domain in claim.domains
            if claim.approval_status is ApprovalStatus.APPROVED
            and claim.tier is EvidenceTier.E1
        }
        for domain, (reason, problems, route) in specs.items():
            missing_entirely = domain not in covered
            missing_audited = domain not in approved_domains and domain in (
                D.COST_ENGINE,
                D.WORKING_CAPITAL_CYCLE,
                D.FUNDING_STRUCTURE,
            )
            if missing_entirely or missing_audited:
                gaps.append(
                    EvidenceGap(
                        gap_id=f"gap:{entity_id}:{domain.value}",
                        entity_id=entity_id,
                        domain=domain,
                        reason=reason
                        if missing_entirely
                        else f"No approved E1 evidence supports this domain. {reason}",
                        material=True,
                        blocking_problems=list(problems),
                        acquisition_route=route,
                    )
                )
        return gaps

    # -- access -----------------------------------------------------------
    def claims_for(self, entity_id: str) -> List[BusinessEvidenceClaim]:
        return list(self._by_entity.get(entity_id, ()))

    def approved_claims_for(self, entity_id: str) -> List[BusinessEvidenceClaim]:
        return [
            claim
            for claim in self._by_entity.get(entity_id, ())
            if claim.approval_status is ApprovalStatus.APPROVED
        ]

    def claims_in_domain(
        self, entity_id: str, domain: D, *, approved_only: bool = False
    ) -> List[BusinessEvidenceClaim]:
        source = (
            self.approved_claims_for(entity_id)
            if approved_only
            else self.claims_for(entity_id)
        )
        return [claim for claim in source if domain in claim.domains]

    def by_concept(
        self, entity_id: str, concept: str, *, approved_only: bool = False
    ) -> Optional[BusinessEvidenceClaim]:
        matches = [
            claim
            for claim in (
                self.approved_claims_for(entity_id)
                if approved_only
                else self.claims_for(entity_id)
            )
            if claim.concept == concept
        ]
        if not matches:
            return None
        return max(matches, key=lambda claim: (claim.period_end, claim.available_date))

    def get(self, claim_id: str) -> Optional[BusinessEvidenceClaim]:
        return self._by_id.get(claim_id)

    def gaps_for(self, entity_id: str) -> List[EvidenceGap]:
        return [gap for gap in self.gaps if gap.entity_id == entity_id]

    def public_fact(self, fact_id: str) -> Optional[PublicFact]:
        for fact in self._public.facts:
            if fact.fact_id == fact_id:
                return fact
        return None

    # -- curation report --------------------------------------------------
    def coverage_report(self) -> Dict[str, Any]:
        """Honest curation report against the V3.1 minimum thresholds."""
        per_client: Dict[str, Dict[str, Any]] = {}
        for entity_id, claims in sorted(self._by_entity.items()):
            domains = {domain for claim in claims for domain in claim.domains}
            e1 = [claim for claim in claims if claim.tier is EvidenceTier.E1]
            e1_approved = [
                claim
                for claim in e1
                if claim.approval_status is ApprovalStatus.APPROVED
            ]
            critical_approved = [
                claim
                for claim in claims
                if claim.critical_path
                and claim.approval_status is ApprovalStatus.APPROVED
            ]
            per_client[entity_id] = {
                "claims": len(claims),
                "approved_claims": len(
                    [
                        claim
                        for claim in claims
                        if claim.approval_status is ApprovalStatus.APPROVED
                    ]
                ),
                "e1_claims": len(e1),
                "e1_approved_claims": len(e1_approved),
                "e1_pending_claims": len(e1) - len(e1_approved),
                "domains_covered": len(domains),
                "approved_critical_path_claims": len(critical_approved),
                "gaps": len(self.gaps_for(entity_id)),
                "meets_claim_threshold": len(claims) >= MIN_CLAIMS_PER_CLIENT,
                "meets_domain_threshold": len(domains) >= MIN_DOMAINS_PER_CLIENT,
                "meets_e1_threshold": len(e1_approved) >= MIN_E1_CLAIMS_PER_CLIENT,
                "has_approved_critical_path_fact": bool(critical_approved),
            }
        tiers = Counter(claim.tier.value for claim in self.claims)
        approvals = Counter(claim.approval_status.value for claim in self.claims)
        kinds = Counter(claim.kind.value for claim in self.claims)
        e1_shortfall = sorted(
            entity_id
            for entity_id, row in per_client.items()
            if not row["meets_e1_threshold"]
        )
        return {
            "evidence_version": self.version,
            "as_of": self.as_of.isoformat(),
            "total_claims": len(self.claims),
            "total_gaps": len(self.gaps),
            "clients": len(per_client),
            "per_client": per_client,
            "tier_counts": dict(tiers),
            "approval_counts": dict(approvals),
            "kind_counts": dict(kinds),
            "thresholds": {
                "min_total_claims": MIN_TOTAL_CLAIMS,
                "min_claims_per_client": MIN_CLAIMS_PER_CLIENT,
                "min_domains_per_client": MIN_DOMAINS_PER_CLIENT,
                "min_e1_claims_per_client": MIN_E1_CLAIMS_PER_CLIENT,
            },
            "meets_total_claim_threshold": len(self.claims) >= MIN_TOTAL_CLAIMS,
            "all_clients_meet_claim_threshold": all(
                row["meets_claim_threshold"] for row in per_client.values()
            ),
            "all_clients_meet_domain_threshold": all(
                row["meets_domain_threshold"] for row in per_client.values()
            ),
            "all_clients_have_approved_critical_path_fact": all(
                row["has_approved_critical_path_fact"] for row in per_client.values()
            ),
            "all_clients_meet_e1_threshold": not e1_shortfall,
            "e1_threshold_shortfall_clients": e1_shortfall,
            "e1_threshold_status": (
                "MET"
                if not e1_shortfall
                else "BLOCKING_GATE_OPEN_INSUFFICIENT_AUDITED_PUBLIC_EVIDENCE"
            ),
            "e1_threshold_note": (
                "The V3.1 plan targets 15 reviewed E1 claims per client. The real audited "
                "public evidence base does not reach that depth for every client, and no "
                "audited figure has been invented to close the gap. The shortfall is "
                "reported as an open curation gate and every affected client-facing problem "
                "falls back to a discovery conversation."
            ),
            "legacy_facts_migrated": len(
                {
                    claim.legacy_fact_id
                    for claim in self.claims
                    if claim.legacy_fact_id
                }
            ),
            "claims_relinked_to_legacy_facts": len(
                [claim for claim in self.claims if claim.legacy_fact_id]
            ),
            "pending_review_claims_cannot_support_eligibility": True,
        }

    def as_payloads(self, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
        claims = self.claims_for(entity_id) if entity_id else self.claims
        return [claim.model_dump(mode="json") for claim in claims]


def domains_covered(claims: Iterable[BusinessEvidenceClaim]) -> set:
    return {domain for claim in claims for domain in claim.domains}
