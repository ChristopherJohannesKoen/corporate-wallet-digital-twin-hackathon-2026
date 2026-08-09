from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
SEED_FACTS = ROOT / "data" / "public_facts.csv"
EXPANDED_FACTS = ROOT / "data" / "v2" / "public_facts_expanded.csv"
SOURCE_REGISTRY = ROOT / "data" / "v2" / "public_sources.json"


@dataclass(frozen=True)
class PublicFact:
    fact_id: str
    entity_id: str
    entity_name: str
    concept: str
    value: float
    unit: str
    currency: str
    period_start: date
    period_end: date
    available_date: date
    source_title: str
    source_url: str
    page: int
    document_hash: str
    approval_status: str
    confidence: float


@dataclass(frozen=True)
class PublicAnchor:
    entity_id: str
    product: str
    low_zar: float
    base_zar: float
    high_zar: float
    fact_ids: Tuple[str, ...]
    rule_id: str
    evidence_tier: str = "E1"
    approval_status: str = "PENDING_REVIEW"


class PublicEvidenceRegistry:
    """Point-in-time E1 fact loader and transparent anchor compiler.

    Public facts are observations. Product anchors remain noisy model inputs,
    never labels. FX rates and product conversion factors are E0 governed
    benchmark assumptions, and their identifiers are retained in every anchor.
    """

    version = "public-evidence-anchor-2.1.0"
    fx_policy_id = "FX-E0-PTI-2026-06-30"
    fx_to_zar = {"ZAR": 1.0, "USD": 17.86, "EUR": 20.90, "GBP": 24.45}

    _revenue_concepts = ("revenue", "insurance_revenue", "gross_rental_income")
    _cash_concepts = ("cash_and_cash_equivalents",)
    _debt_concepts = ("current_debt", "term_finance", "current_liabilities", "insurance_liabilities")
    _payable_concepts = ("trade_payables", "trade_payables_close", "operating_cost_base")

    trade_ratios = {
        "mining": (0.010, 0.030, 0.060),
        "consumer": (0.005, 0.015, 0.040),
        "industrials_pharma": (0.008, 0.025, 0.055),
        "telecoms": (0.003, 0.010, 0.025),
        "tech": (0.002, 0.008, 0.020),
        "insurance": (0.001, 0.004, 0.012),
        "real_estate": (0.001, 0.005, 0.015),
    }
    fx_ratios = {
        "mining": (0.30, 0.65, 1.20),
        "consumer": (0.08, 0.20, 0.45),
        "industrials_pharma": (0.15, 0.40, 0.80),
        "telecoms": (0.12, 0.35, 0.70),
        "tech": (0.25, 0.60, 1.10),
        "insurance": (0.05, 0.15, 0.35),
        "real_estate": (0.05, 0.15, 0.40),
    }

    def __init__(self, as_of: date) -> None:
        self.as_of = as_of
        self.sources = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
        self._source_hashes = {item["entity_id"]: item["sha256"] for item in self.sources["documents"]}
        self.facts = [fact for fact in self._load_all() if fact.available_date <= as_of]
        self.by_entity: Dict[str, List[PublicFact]] = {}
        for fact in self.facts:
            self.by_entity.setdefault(fact.entity_id, []).append(fact)

    @staticmethod
    def _parse_page(value: str) -> int:
        return int(str(value).split("-")[0])

    def _load_all(self) -> Iterable[PublicFact]:
        with SEED_FACTS.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                yield PublicFact(
                    fact_id=row["fact_id"],
                    entity_id=row["entity_id"],
                    entity_name=row["entity_name"],
                    concept=row["concept"],
                    value=float(row["value"]),
                    unit=row["unit"],
                    currency=row["currency"],
                    period_start=date.fromisoformat(row["period_start"]),
                    period_end=date.fromisoformat(row["period_end"]),
                    available_date=date.fromisoformat(row["available_date"]),
                    source_title=row["source_title"],
                    source_url=row["source_url"],
                    page=self._parse_page(row["page"]),
                    document_hash="seed-register-hash:" + row["fact_id"],
                    approval_status="APPROVED",
                    confidence=float(row["confidence"]),
                )
        with EXPANDED_FACTS.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                yield PublicFact(
                    fact_id=row["fact_id"],
                    entity_id=row["entity_id"],
                    entity_name=row["entity_name"],
                    concept=row["concept"],
                    value=float(row["value"]),
                    unit=row["unit"],
                    currency=row["currency"],
                    period_start=date.fromisoformat(row["period_start"]),
                    period_end=date.fromisoformat(row["period_end"]),
                    available_date=date.fromisoformat(row["available_date"]),
                    source_title=row["source_title"],
                    source_url=row["source_url"],
                    page=self._parse_page(row["page"]),
                    document_hash=row["source_sha256"],
                    approval_status=row["approval_status"],
                    confidence=float(row["confidence"]),
                )

    def facts_for(self, entity_id: str) -> List[PublicFact]:
        return list(self.by_entity.get(entity_id, ()))

    def _first(self, entity_id: str, concepts: Sequence[str]) -> Optional[PublicFact]:
        matches = [fact for fact in self.by_entity.get(entity_id, ()) if fact.concept in concepts]
        return max(matches, key=lambda fact: (fact.period_end, fact.confidence), default=None)

    def _zar(self, fact: PublicFact) -> float:
        if fact.currency not in self.fx_to_zar:
            raise ValueError(f"unsupported public-fact currency: {fact.currency}")
        unit = 1_000_000.0 if fact.unit.lower() == "million" else 1.0
        return fact.value * unit * self.fx_to_zar[fact.currency]

    @staticmethod
    def _ordered(raw: Sequence[float], observed: float) -> Tuple[float, float, float]:
        floor = max(observed, 1.0)
        low = max(float(raw[0]), floor)
        base = max(float(raw[1]), low * 1.01)
        high = max(float(raw[2]), base * 1.01)
        return low, base, high

    def anchor_for(self, entity_id: str, product: str, sector: str, observed: float) -> Optional[PublicAnchor]:
        revenue = self._first(entity_id, self._revenue_concepts)
        cash = self._first(entity_id, self._cash_concepts)
        debt = self._first(entity_id, self._debt_concepts)
        payable = self._first(entity_id, self._payable_concepts)
        fx_exposure = self._first(entity_id, ("fx_exposure",))

        raw: Optional[Tuple[float, float, float]] = None
        facts: List[PublicFact] = []
        rule = ""
        if product == "Collections" and revenue:
            value = self._zar(revenue)
            raw, facts, rule = (0.88 * value, value, 1.12 * value), [revenue], "ACCOUNTING_REVENUE_0.88_1.12"
        elif product == "Payments" and (payable or revenue):
            base_fact = payable or revenue
            value = self._zar(base_fact)
            multipliers = (0.88, 1.0, 1.12) if payable else (0.45, 0.65, 0.85)
            raw, facts, rule = tuple(value * item for item in multipliers), [base_fact], "PAYABLE_OR_REVENUE_COST_PROXY"
        elif product == "Liquidity" and (cash or debt):
            chosen = [fact for fact in (cash, debt) if fact is not None]
            value = sum(self._zar(fact) for fact in chosen)
            raw, facts, rule = (0.75 * value, value, 1.50 * value), chosen, "CASH_PLUS_MATURITY_0.75_1.50"
        elif product == "Cross-border FX" and (fx_exposure or revenue):
            if fx_exposure:
                value = self._zar(fx_exposure)
                raw, facts, rule = (value, 2.0 * value, 4.0 * value), [fx_exposure], "AUDITED_FX_EXPOSURE_TURNOVER"
            else:
                ratios = self.fx_ratios.get(sector, (0.08, 0.25, 0.55))
                value = self._zar(revenue)
                raw, facts, rule = tuple(value * item for item in ratios), [revenue], "SECTOR_FX_INTENSITY_E0"
        elif product == "Trade finance" and revenue:
            ratios = self.trade_ratios.get(sector, (0.005, 0.020, 0.050))
            value = self._zar(revenue)
            raw, facts, rule = tuple(value * item for item in ratios), [revenue], "SECTOR_TRADE_UTILISATION_E0"

        if raw is None:
            return None
        low, base, high = self._ordered(raw, observed)
        return PublicAnchor(
            entity_id=entity_id,
            product=product,
            low_zar=low,
            base_zar=base,
            high_zar=high,
            fact_ids=tuple(fact.fact_id for fact in facts),
            rule_id=f"{self.version}:{rule}:{self.fx_policy_id}",
            approval_status="APPROVED" if all(fact.approval_status == "APPROVED" for fact in facts) else "PENDING_REVIEW",
        )

    def fact_payload(self, fact: PublicFact) -> dict:
        return {
            "fact_id": fact.fact_id,
            "entity_id": fact.entity_id,
            "entity_name": fact.entity_name,
            "concept": fact.concept,
            "value": fact.value,
            "unit": fact.unit,
            "currency": fact.currency,
            "period_start": fact.period_start.isoformat(),
            "period_end": fact.period_end.isoformat(),
            "available_date": fact.available_date.isoformat(),
            "source_title": fact.source_title,
            "source_url": fact.source_url,
            "page": fact.page,
            "document_hash": fact.document_hash,
            "approval_status": fact.approval_status,
            "tier": "E1",
            "confidence": fact.confidence,
        }
