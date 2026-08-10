from __future__ import annotations

import argparse
import csv
import io
import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .briefs import brief_summary, build_banker_brief
from .model import (
    OpportunityInput,
    clamp,
    estimate_opportunity,
    growth_rate,
    percentile_rank,
    safe_div,
    seasonal_naive_backtest,
    synthetic_recovery,
)


DATASETS = {
    "transactional_banking.csv": "transactional",
    "cross_border_payments.csv": "cross_border",
    "trade_finance.csv": "trade_finance",
}
PRODUCTS = ["Collections", "Payments", "Liquidity", "Cross-border FX", "Trade finance"]


def month_key(value: str) -> str:
    return value[:7]


def iter_months(start: str, end: str) -> list[str]:
    year, month = map(int, start.split("-"))
    end_year, end_month = map(int, end.split("-"))
    result = []
    while (year, month) <= (end_year, end_month):
        result.append(f"{year:04d}-{month:02d}")
        month += 1
        if month == 13:
            year += 1
            month = 1
    return result


def previous_month(month: str, count: int) -> str:
    year, mon = map(int, month.split("-"))
    serial = year * 12 + mon - 1 - count
    return f"{serial // 12:04d}-{serial % 12 + 1:02d}"


def next_month(month: str, count: int) -> str:
    year, mon = map(int, month.split("-"))
    serial = year * 12 + mon - 1 + count
    return f"{serial // 12:04d}-{serial % 12 + 1:02d}"


def quantile(values: Iterable[float], q: float) -> float:
    items = list(values)
    return float(np.quantile(items, q)) if items else 0.0


def load_assumptions(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_public_facts(path: Path, as_of: str, assumptions: dict[str, Any]) -> list[dict[str, Any]]:
    """Read only facts that were public by the model cut-off and translate to ZAR.

    The source value is preserved. Currency translation is explicitly marked as
    a model assumption so an audited USD disclosure is never relabelled as an
    audited ZAR fact.
    """

    facts: list[dict[str, Any]] = []
    if not path.exists():
        return facts
    currency_rates = assumptions["public_anchor_model"]["currency_to_zar"]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("entity_id") and (not row.get("available_date") or row["available_date"] <= as_of):
                value = float(row["value"])
                unit_multiplier = 1_000_000.0 if row.get("unit", "").lower() == "million" else 1.0
                currency = row.get("currency", "ZAR").upper()
                fx_to_zar = float(currency_rates[currency])
                facts.append(
                    {
                        **row,
                        "value": value,
                        "confidence": float(row.get("confidence") or 0.0),
                        "fx_to_zar": fx_to_zar,
                        "value_zar": value * unit_multiplier * fx_to_zar,
                        "translation_basis": (
                            "identity: source currency is ZAR"
                            if currency == "ZAR"
                            else assumptions["public_anchor_model"]["currency_translation_note"]
                        ),
                    }
                )
    return facts


def derive_public_anchors(
    facts: list[dict[str, Any]],
    assumptions: dict[str, Any],
    sectors: dict[str, str],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Turn audited point facts into bounded annual activity anchors.

    Collections and payments use transparent accounting identities. FX turns a
    disclosed point exposure/notional into an annual flow range. Current debt
    anchors liquidity/refinancing need. Trade-finance utilisation is deliberately
    exposed as a sector assumption rather than smuggled in as a public fact.
    """

    grouped: defaultdict[str, defaultdict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for fact in facts:
        grouped[fact["entity_id"]][fact["concept"]].append(fact)

    anchor_cfg = assumptions["public_anchor_model"]
    accounting_bounds = tuple(anchor_cfg["accounting_bounds"])
    anchors: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    debt_anchors: dict[str, dict[str, Any]] = {}

    def one(entity_id: str, concept: str) -> dict[str, Any] | None:
        rows = grouped[entity_id].get(concept, [])
        return rows[0] if rows else None

    def fact_bundle(entity_id: str, concepts: list[str]) -> list[dict[str, Any]]:
        return [fact for concept in concepts for fact in grouped[entity_id].get(concept, [])]

    def add_anchor(
        entity_id: str,
        product: str,
        name: str,
        low: float,
        base: float,
        high: float,
        formula: str,
        evidence: list[dict[str, Any]],
        assumption: str,
    ) -> None:
        if not evidence or base <= 0:
            return
        anchors[entity_id][product] = {
            "product": product,
            "name": name,
            "low_zar": max(0.0, low),
            "base_zar": max(0.0, base),
            "high_zar": max(0.0, high),
            "weight": anchor_cfg["anchor_weight"],
            "formula": formula,
            "transformation_assumption": assumption,
            "fact_ids": [fact["fact_id"] for fact in evidence],
            "source_pages": sorted({f"{fact['source_title']} p.{fact['page']}" for fact in evidence}),
            "period_end": max(fact["period_end"] for fact in evidence),
            "available_date": max(fact["available_date"] for fact in evidence),
            "audit_status": "audited" if all(fact.get("audit_status") == "audited" for fact in evidence) else "mixed",
        }

    for entity_id in grouped:
        revenue = one(entity_id, "revenue")
        ar_open = one(entity_id, "trade_receivables_open")
        ar_close = one(entity_id, "trade_receivables_close")
        if revenue and ar_open and ar_close:
            base = revenue["value_zar"] + ar_open["value_zar"] - ar_close["value_zar"]
            evidence = [revenue, ar_open, ar_close]
            add_anchor(
                entity_id,
                "Collections",
                "Audited cash-collections identity",
                base * accounting_bounds[0],
                base,
                base * accounting_bounds[2],
                "Revenue + opening trade receivables - closing trade receivables",
                evidence,
                f"Accounting proxy bounded at {accounting_bounds[0]:.0%}/{accounting_bounds[2]:.0%} to allow non-cash and classification effects.",
            )

        cost = one(entity_id, "operating_cost_base")
        inv_open = one(entity_id, "inventories_open")
        inv_close = one(entity_id, "inventories_close")
        ap_open = one(entity_id, "trade_payables_open")
        ap_close = one(entity_id, "trade_payables_close")
        if cost and inv_open and inv_close and ap_open and ap_close:
            base = (
                cost["value_zar"]
                + inv_close["value_zar"]
                - inv_open["value_zar"]
                + ap_open["value_zar"]
                - ap_close["value_zar"]
            )
            evidence = [cost, inv_open, inv_close, ap_open, ap_close]
            add_anchor(
                entity_id,
                "Payments",
                "Audited supplier-payments identity",
                base * accounting_bounds[0],
                base,
                base * accounting_bounds[2],
                "Cost base + closing inventory - opening inventory + opening trade payables - closing trade payables",
                evidence,
                f"Accounting proxy bounded at {accounting_bounds[0]:.0%}/{accounting_bounds[2]:.0%}; BHP's cost base is expenses excluding net finance costs.",
            )

            trade_range = anchor_cfg["trade_utilisation_by_sector"].get(
                sectors.get(entity_id, ""), anchor_cfg["trade_utilisation_by_sector"]["default"]
            )
            add_anchor(
                entity_id,
                "Trade finance",
                "Audited payments base × trade-utilisation range",
                base * trade_range[0],
                base * trade_range[1],
                base * trade_range[2],
                "Audited supplier-payments proxy × declared sector trade-finance utilisation",
                evidence,
                f"Sector utilisation low/base/high = {trade_range[0]:.1%}/{trade_range[1]:.1%}/{trade_range[2]:.1%}.",
            )

        fx = one(entity_id, "fx_exposure")
        if fx:
            multiples = anchor_cfg["fx_turnover_multiples"]
            add_anchor(
                entity_id,
                "Cross-border FX",
                "Audited FX exposure/notional turnover range",
                fx["value_zar"] * multiples[0],
                fx["value_zar"] * multiples[1],
                fx["value_zar"] * multiples[2],
                "Audited FX point exposure or hedge notional × annual turnover multiple",
                [fx],
                f"Annual turnover low/base/high = {multiples[0]:.1f}x/{multiples[1]:.1f}x/{multiples[2]:.1f}x the disclosed point exposure/notional.",
            )

        debt_facts = fact_bundle(entity_id, ["current_debt", "short_term_facilities"])
        if debt_facts:
            debt_base = sum(fact["value_zar"] for fact in debt_facts)
            multiples = anchor_cfg["debt_liquidity_multiples"]
            debt_anchor = {
                "name": "Audited current debt-maturity/refinancing anchor",
                "base_zar": debt_base,
                "low_zar": debt_base * multiples[0],
                "high_zar": debt_base * multiples[2],
                "fact_ids": [fact["fact_id"] for fact in debt_facts],
                "source_pages": sorted({f"{fact['source_title']} p.{fact['page']}" for fact in debt_facts}),
                "period_end": max(fact["period_end"] for fact in debt_facts),
                "available_date": max(fact["available_date"] for fact in debt_facts),
                "audit_status": "audited",
                "formula": "Current borrowings + disclosed short-term facilities",
            }
            debt_anchors[entity_id] = debt_anchor
            add_anchor(
                entity_id,
                "Liquidity",
                "Audited debt-maturity liquidity range",
                debt_anchor["low_zar"],
                debt_anchor["base_zar"],
                debt_anchor["high_zar"],
                "Current debt maturity/refinancing amount × declared liquidity multiple",
                debt_facts,
                f"Liquidity low/base/high = {multiples[0]:.2f}x/{multiples[1]:.2f}x/{multiples[2]:.2f}x current debt and facilities.",
            )

    return dict(anchors), debt_anchors


def build_sensitivity(
    opportunity_inputs: dict[str, OpportunityInput],
    assumptions: dict[str, Any],
) -> dict[str, Any]:
    sensitivity_cfg = assumptions["sensitivity"]
    scenarios: list[dict[str, Any]] = []
    rate_index = {"low": 0, "base": 1, "high": 2}

    for prior_case, prior_multiplier in sensitivity_cfg["prior_multipliers"].items():
        for rate_case in sensitivity_cfg["rate_cases"]:
            ranked: list[dict[str, Any]] = []
            for opportunity_id, op_input in opportunity_inputs.items():
                selected_rate = op_input.economic_rate_bps[rate_index[rate_case]]
                scenario_input = replace(
                    op_input,
                    share_prior_mean=clamp(op_input.share_prior_mean * prior_multiplier, 0.08, 0.78),
                    economic_rate_bps=(selected_rate, selected_rate, selected_rate),
                )
                result, _ = estimate_opportunity(
                    scenario_input,
                    assumptions["sensitivity_draws"],
                    seed_suffix=f"sensitivity-{prior_case}-{rate_case}",
                )
                ranked.append(
                    {
                        "opportunity_id": opportunity_id,
                        "entity_id": result["entity_id"],
                        "product": result["product"],
                        "priority_score": result["priority_score"],
                        "gap_p50_zar": result["revenue_gap_zar"]["p50"],
                    }
                )
            ranked.sort(key=lambda item: item["priority_score"], reverse=True)
            top10 = ranked[:10]
            trade_count = sum(item["product"] == "Trade finance" for item in top10)
            scenarios.append(
                {
                    "prior_case": prior_case,
                    "prior_multiplier": prior_multiplier,
                    "rate_case": rate_case,
                    "top_product": top10[0]["product"],
                    "top_opportunity_id": top10[0]["opportunity_id"],
                    "trade_finance_top10_count": trade_count,
                    "trade_finance_top10_share": trade_count / 10.0,
                    "trade_finance_dominant": trade_count >= 5,
                    "portfolio_gap_p50_zar": sum(item["gap_p50_zar"] for item in ranked),
                    "top10": top10,
                    "rates_bps_by_product": {
                        product: assumptions["products"][product]["economic_rate_bps"][rate_index[rate_case]]
                        for product in PRODUCTS
                    },
                }
            )

    dominant = sum(scenario["trade_finance_dominant"] for scenario in scenarios)
    return {
        "definition": sensitivity_cfg["dominance_definition"],
        "scenario_count": len(scenarios),
        "trade_finance_dominant_scenarios": dominant,
        "trade_finance_dominant_share": safe_div(dominant, len(scenarios)),
        "conclusion": (
            f"Trade finance remains dominant in {dominant} of {len(scenarios)} rate/prior scenarios."
            if dominant
            else f"Trade finance is not dominant in any of the {len(scenarios)} rate/prior scenarios."
        ),
        "scenarios": scenarios,
    }


class Aggregates:
    def __init__(self) -> None:
        self.entities: dict[str, dict[str, str]] = {}
        self.monthly: defaultdict[tuple[str, str, str], dict[str, float]] = defaultdict(lambda: {"value": 0.0, "count": 0.0})
        self.txn_direction: defaultdict[tuple[str, str, str], float] = defaultdict(float)
        self.countries: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.currencies: defaultdict[str, Counter[str]] = defaultdict(Counter)
        self.trade_events: list[tuple[str, date, float, str, str]] = []
        self.quality: dict[str, dict[str, float]] = {}
        self.entity_duplicates: Counter[str] = Counter()
        self.min_date = "9999-12-31"
        self.max_date = "0000-01-01"

    def entity(self, row: dict[str, str]) -> None:
        entity_id = row["entity_id"]
        self.entities[entity_id] = {
            "entity_id": entity_id,
            "entity_name": row["entity_name"],
            "sector": row["sector"].strip().lower(),
        }

    def add_monthly(self, entity_id: str, product: str, month: str, value: float) -> None:
        point = self.monthly[(entity_id, product, month)]
        point["value"] += value
        point["count"] += 1


def ingest(zip_path: Path) -> Aggregates:
    agg = Aggregates()
    with zipfile.ZipFile(zip_path) as archive:
        for filename, kind in DATASETS.items():
            metrics = Counter()
            seen_ids: set[str] = set()
            with archive.open(filename) as raw:
                text = io.TextIOWrapper(raw, encoding="cp1252", newline="")
                for row in csv.DictReader(text):
                    metrics["rows_raw"] += 1
                    record_id = row["transaction_id"] if "transaction_id" in row else row["instrument_id"]
                    entity_id = row.get("entity_id", "")
                    if record_id in seen_ids:
                        metrics["duplicate_id_rows"] += 1
                        agg.entity_duplicates[entity_id] += 1
                        continue
                    seen_ids.add(record_id)
                    metrics["rows_modelled"] += 1
                    agg.entity(row)
                    row_date = row["date"]
                    agg.min_date = min(agg.min_date, row_date)
                    agg.max_date = max(agg.max_date, row_date)
                    month = month_key(row_date)

                    if not row.get("memo"):
                        metrics["missing_memo"] += 1
                    if kind in {"cross_border", "trade_finance"} and not row.get("counterparty_country"):
                        metrics["missing_country"] += 1

                    if kind == "transactional":
                        currency = row.get("currency", "")
                        if currency and currency != currency.upper():
                            metrics["noncanonical_currency"] += 1
                        value = float(row["amount_zar"])
                        leg = row["leg_type"].strip().lower()
                        direction = row["direction"].strip().lower()
                        product = "Collections" if leg == "collections" else "Payments"
                        agg.add_monthly(entity_id, product, month, value)
                        agg.txn_direction[(entity_id, month, direction)] += value

                    elif kind == "cross_border":
                        value = float(row["value_zar"])
                        agg.add_monthly(entity_id, "Cross-border FX", month, value)
                        country = row.get("counterparty_country", "").strip() or "Unknown"
                        currency = row.get("currency_pair", "Unknown").strip().upper()
                        agg.countries[entity_id][country] += value
                        agg.currencies[entity_id][currency] += value

                    else:
                        value = float(row["value_zar"])
                        agg.add_monthly(entity_id, "Trade finance", month, value)
                        country = row.get("counterparty_country", "").strip() or "Unknown"
                        agg.countries[entity_id][country] += value
                        if row.get("instrument_type") == "export_collections" and row.get("direction") == "import":
                            metrics["direction_semantic_flags"] += 1
                        start = date.fromisoformat(row_date)
                        due = start + timedelta(days=int(float(row.get("tenor_days") or 0)))
                        agg.trade_events.append((entity_id, due, value, row.get("instrument_type", ""), row.get("status", "")))

            agg.quality[kind] = {key: float(value) for key, value in metrics.items()}

    # No balances are supplied. Liquidity is a transparent flow proxy, not an observed balance wallet.
    for entity_id in agg.entities:
        months = {month for ent, month, _ in agg.txn_direction if ent == entity_id}
        for month in months:
            inbound = agg.txn_direction.get((entity_id, month, "inbound"), 0.0)
            outbound = agg.txn_direction.get((entity_id, month, "outbound"), 0.0)
            liquidity_proxy = min(inbound, outbound) + 0.50 * abs(inbound - outbound)
            agg.monthly[(entity_id, "Liquidity", month)] = {"value": liquidity_proxy, "count": 1.0}
    return agg


def source_quality(agg: Aggregates) -> tuple[float, dict[str, Any]]:
    raw = sum(item.get("rows_raw", 0) for item in agg.quality.values())
    modelled = sum(item.get("rows_modelled", 0) for item in agg.quality.values())
    duplicate_rate = safe_div(raw - modelled, raw)
    country_expected = sum(item.get("rows_modelled", 0) for key, item in agg.quality.items() if key != "transactional")
    missing_country = sum(item.get("missing_country", 0) for item in agg.quality.values())
    data_quality = clamp(1.0 - duplicate_rate - 0.30 * safe_div(missing_country, country_expected), 0.0, 1.0)
    return data_quality, {
        "rows_raw": int(raw),
        "rows_modelled_after_id_deduplication": int(modelled),
        "duplicate_id_rows_excluded": int(raw - modelled),
        "duplicate_rate": duplicate_rate,
        "missing_country_rate_cross_border_and_trade": safe_div(missing_country, country_expected),
        "noncanonical_currency_rows": int(sum(item.get("noncanonical_currency", 0) for item in agg.quality.values())),
        "trade_direction_semantic_flags": int(sum(item.get("direction_semantic_flags", 0) for item in agg.quality.values())),
        "modelling_data_quality_score": data_quality,
        "dataset_detail": agg.quality,
    }


def annual_value(agg: Aggregates, entity_id: str, product: str, months: list[str]) -> float:
    return sum(agg.monthly[(entity_id, product, month)]["value"] for month in months)


def model_portfolio(
    agg: Aggregates,
    assumptions: dict[str, Any],
    public_facts: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    data_quality, quality_summary = source_quality(agg)
    all_months = iter_months(month_key(agg.min_date), month_key(agg.max_date))
    ltm_months = all_months[-12:]
    as_of = agg.max_date
    as_of_date = date.fromisoformat(as_of)
    target_cfg = assumptions["target_share"]
    target_share = (target_cfg["low"], target_cfg["base"], target_cfg["high"])
    public_fact_counts = Counter(fact["entity_id"] for fact in public_facts)
    facts_by_entity: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in public_facts:
        facts_by_entity[fact["entity_id"]].append(fact)
    public_anchors, debt_anchors = derive_public_anchors(
        public_facts,
        assumptions,
        {entity_id: entity["sector"] for entity_id, entity in agg.entities.items()},
    )

    observed_by_product: dict[str, list[float]] = {
        product: [annual_value(agg, entity_id, product, ltm_months) for entity_id in agg.entities]
        for product in PRODUCTS
    }
    active_products = {
        entity_id: sum(annual_value(agg, entity_id, product, ltm_months) > 0 for product in PRODUCTS)
        for entity_id in agg.entities
    }

    clients: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []
    priority_samples: dict[str, np.ndarray] = {}
    opportunity_inputs: dict[str, OpportunityInput] = {}
    validation_backtests = []

    for entity_id, entity in sorted(agg.entities.items()):
        breadth = active_products[entity_id] / len(PRODUCTS)
        observed_ltm_total = sum(annual_value(agg, entity_id, product, ltm_months) for product in PRODUCTS if product != "Liquidity")
        country_count = sum(country != "Unknown" for country in agg.countries[entity_id])
        trade_events = [event for event in agg.trade_events if event[0] == entity_id and as_of_date < event[1] <= as_of_date + timedelta(days=90)]

        product_series: dict[str, list[float]] = {}
        forecasts: dict[str, list[dict[str, float | str]]] = {}
        entity_opps: list[dict[str, Any]] = []
        recurrence_values = []
        next_quarter_total = 0.0

        for product in PRODUCTS:
            values = [agg.monthly[(entity_id, product, month)]["value"] for month in all_months]
            counts = [agg.monthly[(entity_id, product, month)]["count"] for month in all_months]
            product_series[product] = values
            recurrence = sum(count > 0 for count in counts[-12:]) / 12.0
            recurrence_values.append(recurrence)
            current = sum(values[-12:])
            prior = sum(values[-24:-12])
            trend = growth_rate(current, prior)

            backtest = seasonal_naive_backtest(values)
            validation_backtests.append({"entity_id": entity_id, "product": product, **backtest})

            trend_factor = clamp(safe_div(sum(values[-6:]), sum(values[-18:-12]), 1.0), 0.75, 1.25)
            product_forecast = []
            for offset in range(1, 4):
                future_month = next_month(all_months[-1], offset)
                seasonal_source = previous_month(future_month, 12)
                seasonal_value = agg.monthly[(entity_id, product, seasonal_source)]["value"]
                forecast_value = seasonal_value * trend_factor
                product_forecast.append({"month": future_month, "value_zar": forecast_value, "method": "seasonal_naive_with_capped_trend"})
            forecasts[product] = product_forecast
            forecast_sum = sum(item["value_zar"] for item in product_forecast)
            next_quarter_total += forecast_sum if product != "Liquidity" else 0.0
            trailing_quarter = sum(values[-3:])
            timing_ratio = safe_div(forecast_sum, trailing_quarter, 1.0)
            product_anchor = public_anchors.get(entity_id, {}).get(product)
            event_boost = min(0.18, len(trade_events) * 0.03) if product == "Trade finance" else 0.0
            if product == "Liquidity" and entity_id in debt_anchors:
                event_boost += 0.10
            elif product == "Trade finance" and product_anchor:
                event_boost += 0.05
            timing = clamp(0.58 + 0.24 * (timing_ratio - 1.0) + event_boost, 0.35, 0.95)

            product_cfg = assumptions["products"][product]
            public_coverage = min(1.0, public_fact_counts.get(entity_id, 0) / 8.0)
            # Bank data strongly supports observed activity, but not competitor
            # share or total wallet. Public facts can lift coverage; an empty
            # public-facts table deliberately caps opportunity confidence.
            evidence_coverage_before_anchor = clamp(
                0.38 + 0.22 * recurrence + 0.10 * data_quality,
                0.0,
                1.0,
            )
            evidence_coverage = clamp(
                0.38
                + 0.22 * recurrence
                + 0.15 * public_coverage
                + 0.10 * data_quality
                + (0.08 if product_anchor else 0.0),
                0.0,
                1.0,
            )
            fit = assumptions["sector_fit"].get(entity["sector"], {}).get(product, 0.75)
            op_input = OpportunityInput(
                entity_id=entity_id,
                product=product,
                observed_activity=current,
                recurrence=recurrence,
                relationship_breadth=breadth,
                scale_percentile=percentile_rank(observed_by_product[product], current),
                trend=trend,
                data_quality=data_quality,
                evidence_coverage=evidence_coverage,
                fit=fit,
                timing=timing,
                share_prior_mean=product_cfg["share_prior_mean"],
                share_prior_concentration=product_cfg["share_prior_concentration"],
                economic_rate_bps=tuple(product_cfg["economic_rate_bps"]),
                target_share=target_share,
                anchor_low=product_anchor["low_zar"] if product_anchor else None,
                anchor_base=product_anchor["base_zar"] if product_anchor else None,
                anchor_high=product_anchor["high_zar"] if product_anchor else None,
                anchor_weight=product_anchor["weight"] if product_anchor else 0.0,
                anchor_name=product_anchor["name"] if product_anchor else None,
                anchor_fact_ids=tuple(product_anchor["fact_ids"]) if product_anchor else (),
                evidence_coverage_before_anchor=evidence_coverage_before_anchor,
            )
            opportunity, samples = estimate_opportunity(op_input, assumptions["monte_carlo_draws"])
            if product == "Liquidity":
                opportunity["provenance"]["observed_activity_zar"] = "accounting-derived"
            opportunity["opportunity_id"] = f"{entity_id}-{product.lower().replace(' ', '-')}"
            opportunity["entity_name"] = entity["entity_name"]
            opportunity["sector"] = entity["sector"]
            opportunity["top10_probability"] = 0.0
            opportunity["forecast_next_quarter_zar"] = forecast_sum
            opportunity["public_anchor"] = product_anchor
            opportunities.append(opportunity)
            entity_opps.append(opportunity)
            priority_samples[opportunity["opportunity_id"]] = samples
            opportunity_inputs[opportunity["opportunity_id"]] = op_input

        inbound = sum(agg.txn_direction[(entity_id, month, "inbound")] for month in ltm_months)
        outbound = sum(agg.txn_direction[(entity_id, month, "outbound")] for month in ltm_months)
        net_monthly = [
            agg.txn_direction[(entity_id, month, "inbound")] - agg.txn_direction[(entity_id, month, "outbound")]
            for month in ltm_months
        ]
        scale_values = [sum(annual_value(agg, other, product, ltm_months) for product in PRODUCTS if product != "Liquidity") for other in agg.entities]
        cross_border = annual_value(agg, entity_id, "Cross-border FX", ltm_months)
        trade = annual_value(agg, entity_id, "Trade finance", ltm_months)
        gross_txn = inbound + outbound
        liquidity_volatility = safe_div(float(np.std(net_monthly)), safe_div(gross_txn, 12), 0.0)
        debt_base = debt_anchors.get(entity_id, {}).get("base_zar", 0.0)
        latent_state = {
            "operating_scale": round(100 * percentile_rank(scale_values, observed_ltm_total), 1),
            "working_capital_intensity": round(100 * safe_div(annual_value(agg, entity_id, "Collections", ltm_months) + annual_value(agg, entity_id, "Payments", ltm_months), observed_ltm_total), 1),
            "liquidity_volatility": round(100 * clamp(liquidity_volatility, 0.0, 1.0), 1),
            "international_exposure": round(100 * clamp(safe_div(cross_border + trade, observed_ltm_total), 0.0, 1.0), 1),
            "financing_need": round(
                100
                * clamp(
                    0.40 * safe_div(trade, observed_ltm_total)
                    + 0.30 * liquidity_volatility
                    + 0.30 * safe_div(debt_base, max(observed_ltm_total, 1.0)),
                    0.0,
                    1.0,
                ),
                1,
            ),
            "event_intensity": round(100 * clamp(len(trade_events) / 10.0 + safe_div(sum(event[2] for event in trade_events), max(1.0, trade)), 0.0, 1.0), 1),
            "relationship_complexity": round(100 * clamp(0.65 * breadth + 0.35 * min(country_count / 12.0, 1.0), 0.0, 1.0), 1),
        }
        top_countries = [{"name": name, "value_zar": value} for name, value in agg.countries[entity_id].most_common(5)]
        top_currencies = [{"name": name, "value_zar": value} for name, value in agg.currencies[entity_id].most_common(5)]
        top_entity_opportunity = max(entity_opps, key=lambda item: item["priority_score"])
        if entity_id in debt_anchors:
            reason = (
                f"Audited current debt and facilities of ZAR {debt_base / 1e9:.1f}bn create a dated refinancing/liquidity anchor; "
                f"{top_entity_opportunity['product']} is the strongest modelled window."
            )
        elif trade_events:
            reason = f"{len(trade_events)} trade maturities fall inside 90 days."
        else:
            reason = f"Seasonal-naive activity indicates {top_entity_opportunity['product']} is the strongest near-term window."
        client = {
            **entity,
            "observed_ltm_zar": observed_ltm_total,
            "relationship_breadth": active_products[entity_id],
            "country_count": country_count,
            "top_countries": top_countries,
            "top_currencies": top_currencies,
            "monthly": {product: [{"month": month, "value_zar": product_series[product][idx]} for idx, month in enumerate(all_months)] for product in PRODUCTS},
            "forecasts": forecasts,
            "latent_state": latent_state,
            "public_facts": facts_by_entity.get(entity_id, []),
            "public_anchors": public_anchors.get(entity_id, {}),
            "debt_maturity_anchor": debt_anchors.get(entity_id),
            "timing": {
                "trade_events_next_90d": len(trade_events),
                "trade_events_value_zar": sum(event[2] for event in trade_events),
                "next_quarter_forecast_zar": next_quarter_total,
                "reason": reason,
            },
            "evidence_summary": {
                "overall_recurrence": sum(recurrence_values) / len(recurrence_values),
                "public_facts_available": public_fact_counts.get(entity_id, 0),
                "active_public_anchors": len(public_anchors.get(entity_id, {})),
                "data_quality_score": data_quality,
                "minimum_evidence_met": top_entity_opportunity["confidence"] >= assumptions["minimum_evidence_to_recommend"],
            },
        }
        clients.append(client)

    # Probabilistic top-10 membership, preserving ranking uncertainty.
    keys = list(priority_samples)
    rank_draws = min(assumptions["rank_draws"], min(len(priority_samples[key]) for key in keys))
    top_counts = Counter()
    matrix = np.vstack([priority_samples[key][:rank_draws] for key in keys])
    for idx in range(rank_draws):
        top_indices = np.argpartition(matrix[:, idx], -10)[-10:]
        top_counts.update(keys[row] for row in top_indices)
    for opportunity in opportunities:
        opportunity["top10_probability"] = top_counts[opportunity["opportunity_id"]] / rank_draws

    # Add compact banker briefs only after rank probabilities are known.
    by_entity = defaultdict(list)
    for opportunity in opportunities:
        by_entity[opportunity["entity_id"]].append(opportunity)
    for client in clients:
        client["brief"] = brief_summary(client, by_entity[client["entity_id"]])

    opportunities.sort(key=lambda item: item["priority_score"], reverse=True)
    clients.sort(key=lambda item: max(item["priority_score"] for item in by_entity[item["entity_id"]]), reverse=True)
    sensitivity = build_sensitivity(opportunity_inputs, assumptions)

    anchored_opportunities = [item for item in opportunities if item["anchor_impact"]["active"]]
    anchor_impact_summary = {
        "showcase_clients": sorted(public_anchors),
        "audited_public_facts": len(public_facts),
        "active_product_anchors": len(anchored_opportunities),
        "median_relative_interval_width_reduction": quantile(
            (item["anchor_impact"]["relative_interval_width_reduction"] for item in anchored_opportunities), 0.50
        ),
        "median_confidence_lift": quantile(
            (item["anchor_impact"]["confidence_lift"] for item in anchored_opportunities), 0.50
        ),
        "before_high_confidence_opportunities": sum(
            item["anchor_impact"]["confidence_before"] >= 0.75 for item in opportunities
        ),
        "after_high_confidence_opportunities": sum(item["confidence_label"] == "High" for item in opportunities),
        "by_client": {
            entity_id: {
                "entity_name": agg.entities[entity_id]["entity_name"],
                "facts": public_fact_counts[entity_id],
                "active_anchors": len(public_anchors.get(entity_id, {})),
                "median_interval_reduction": quantile(
                    (
                        item["anchor_impact"]["relative_interval_width_reduction"]
                        for item in anchored_opportunities
                        if item["entity_id"] == entity_id
                    ),
                    0.50,
                ),
                "median_confidence_lift": quantile(
                    (
                        item["anchor_impact"]["confidence_lift"]
                        for item in anchored_opportunities
                        if item["entity_id"] == entity_id
                    ),
                    0.50,
                ),
            }
            for entity_id in sorted(public_anchors)
        },
    }

    valid_backtests = [item for item in validation_backtests if item["wape"] is not None]
    validation = {
        "forecasting": {
            "method": "12-month seasonal naive",
            "client_product_series": len(valid_backtests),
            "median_wape": quantile((item["wape"] for item in valid_backtests), 0.50),
            "p90_wape": quantile((item["wape"] for item in valid_backtests), 0.90),
        },
        "synthetic_latent_recovery": synthetic_recovery(),
        "accounting_consistency": {
            "observed_not_greater_than_modelled_wallet": all(item["observed_activity_zar"] <= item["total_wallet_zar"]["p10"] + 1e-6 for item in opportunities),
            "shares_in_unit_interval": all(0.0 <= item["current_share"]["p10"] <= item["current_share"]["p90"] <= 1.0 for item in opportunities),
            "nonnegative_revenue_gaps": all(item["revenue_gap_zar"]["p10"] >= 0 for item in opportunities),
        },
        "known_limitations": [
            "Audited public statements are activated for three showcase clients only; the other 17 clients remain prior-led.",
            "Liquidity is a flow-derived opportunity proxy, not a deposit-balance estimate.",
            "Share and total wallet remain partially identified; public anchors narrow but do not eliminate model sensitivity.",
            "USD-to-ZAR translation uses one declared point-in-time rate and is not an audited ZAR restatement of BHP or Glencore.",
            "Opportunity ranking estimates economic gap and timing, not causal conversion uplift.",
        ],
    }

    portfolio = {
        "metadata": {
            "title": "Corporate Wallet Digital Twin",
            "model_version": assumptions["model_version"],
            "as_of": as_of,
            "period_start": agg.min_date,
            "period_end": agg.max_date,
            "generated_from": "supplied synthetic banking datasets plus point-in-time audited public facts for three showcase clients",
            "currency": "ZAR",
        },
        "summary": {
            "clients": len(clients),
            "opportunities": len(opportunities),
            "observed_ltm_zar": sum(client["observed_ltm_zar"] for client in clients),
            "contestable_revenue_p50_zar": sum(item["revenue_gap_zar"]["p50"] for item in opportunities),
            "contestable_revenue_p10_zar": sum(item["revenue_gap_zar"]["p10"] for item in opportunities),
            "contestable_revenue_p90_zar": sum(item["revenue_gap_zar"]["p90"] for item in opportunities),
            "high_confidence_opportunities": sum(item["confidence_label"] == "High" for item in opportunities),
            "medium_confidence_opportunities": sum(item["confidence_label"] == "Medium" for item in opportunities),
            "low_confidence_opportunities": sum(item["confidence_label"] == "Low" for item in opportunities),
            "audited_public_facts": len(public_facts),
            "active_public_anchors": len(anchored_opportunities),
        },
        "data_quality": quality_summary,
        "methodology": {
            "identity": "A = qT",
            "economic_gap": "G = T x economic_rate x max(target_share - q, 0)",
            "priority": "median(G) x confidence x sector fit x timing",
            "identification": "partial-identification envelope shown separately from model-based posterior",
            "timing": "seasonal-naive forecasts plus scheduled trade maturities",
            "public_anchors": "accounting identities, disclosed FX exposure/notional, and current debt maturity; all transformations are explicit",
        },
        "public_evidence": {
            "facts": public_facts,
            "anchor_impact": anchor_impact_summary,
        },
        "sensitivity": sensitivity,
        "clients": clients,
        "opportunities": opportunities,
        "validation": validation,
    }
    return portfolio, priority_samples


def write_outputs(portfolio: dict[str, Any], output_dir: Path, dashboard_data: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dashboard_data.mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(exist_ok=True)
    (output_dir / "evidence").mkdir(exist_ok=True)
    (output_dir / "briefs").mkdir(exist_ok=True)

    serialized = json.dumps(portfolio, indent=2)
    (output_dir / "data" / "portfolio.json").write_text(serialized, encoding="utf-8")
    (dashboard_data / "portfolio.json").write_text(serialized, encoding="utf-8")
    (output_dir / "validation.json").write_text(json.dumps(portfolio["validation"], indent=2), encoding="utf-8")

    opp_fields = [
        "rank", "opportunity_id", "entity_id", "entity_name", "sector", "product", "observed_activity_zar",
        "share_p50", "wallet_p10_zar", "wallet_p50_zar", "wallet_p90_zar", "gap_p10_zar", "gap_p50_zar",
        "gap_p90_zar", "confidence", "confidence_label", "timing_score", "fit_score", "top10_probability", "priority_score",
        "anchor_active", "anchor_name", "anchor_fact_ids", "prior_wallet_p10_zar", "prior_wallet_p50_zar",
        "prior_wallet_p90_zar", "prior_relative_interval_width", "anchored_relative_interval_width",
        "relative_interval_width_reduction", "confidence_before_anchor", "confidence_lift",
    ]
    with (output_dir / "opportunity_register.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=opp_fields)
        writer.writeheader()
        for rank, item in enumerate(portfolio["opportunities"], start=1):
            writer.writerow({
                "rank": rank,
                "opportunity_id": item["opportunity_id"],
                "entity_id": item["entity_id"],
                "entity_name": item["entity_name"],
                "sector": item["sector"],
                "product": item["product"],
                "observed_activity_zar": round(item["observed_activity_zar"], 2),
                "share_p50": round(item["current_share"]["p50"], 6),
                "wallet_p10_zar": round(item["total_wallet_zar"]["p10"], 2),
                "wallet_p50_zar": round(item["total_wallet_zar"]["p50"], 2),
                "wallet_p90_zar": round(item["total_wallet_zar"]["p90"], 2),
                "gap_p10_zar": round(item["revenue_gap_zar"]["p10"], 2),
                "gap_p50_zar": round(item["revenue_gap_zar"]["p50"], 2),
                "gap_p90_zar": round(item["revenue_gap_zar"]["p90"], 2),
                "confidence": round(item["confidence"], 6),
                "confidence_label": item["confidence_label"],
                "timing_score": round(item["timing_score"], 6),
                "fit_score": round(item["fit_score"], 6),
                "top10_probability": round(item["top10_probability"], 6),
                "priority_score": round(item["priority_score"], 2),
                "anchor_active": item["anchor_impact"]["active"],
                "anchor_name": item["anchor_impact"]["anchor_name"] or "",
                "anchor_fact_ids": "|".join(item["anchor_impact"]["fact_ids"]),
                "prior_wallet_p10_zar": round(item["anchor_impact"]["prior_only_total_wallet_zar"]["p10"], 2),
                "prior_wallet_p50_zar": round(item["anchor_impact"]["prior_only_total_wallet_zar"]["p50"], 2),
                "prior_wallet_p90_zar": round(item["anchor_impact"]["prior_only_total_wallet_zar"]["p90"], 2),
                "prior_relative_interval_width": round(item["anchor_impact"]["prior_relative_interval_width"], 6),
                "anchored_relative_interval_width": round(item["anchor_impact"]["anchored_relative_interval_width"], 6),
                "relative_interval_width_reduction": round(item["anchor_impact"]["relative_interval_width_reduction"], 6),
                "confidence_before_anchor": round(item["anchor_impact"]["confidence_before"], 6),
                "confidence_lift": round(item["anchor_impact"]["confidence_lift"], 6),
            })

    sensitivity_fields = [
        "prior_case", "prior_multiplier", "rate_case", "top_opportunity_id", "top_product",
        "trade_finance_top10_count", "trade_finance_top10_share", "trade_finance_dominant",
        "portfolio_gap_p50_zar",
    ]
    with (output_dir / "sensitivity_register.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sensitivity_fields)
        writer.writeheader()
        for scenario in portfolio["sensitivity"]["scenarios"]:
            writer.writerow({field: scenario[field] for field in sensitivity_fields})

    by_entity: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in portfolio["opportunities"]:
        by_entity[item["entity_id"]].append(item)
    for client in portfolio["clients"]:
        entity_id = client["entity_id"]
        evidence = {
            "metadata": portfolio["metadata"],
            "client": client,
            "opportunities": sorted(by_entity[entity_id], key=lambda item: item["priority_score"], reverse=True),
            "claim_policy": "Use only supplied fields; cite evidence IDs; label inference; abstain when evidence is missing.",
        }
        (output_dir / "evidence" / f"{entity_id}.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        brief = build_banker_brief(client, by_entity[entity_id], portfolio["metadata"]["as_of"])
        (output_dir / "briefs" / f"{entity_id}.md").write_text(brief, encoding="utf-8")


def run_pipeline(input_path: Path, output_dir: Path, dashboard_data: Path, assumptions_path: Path, public_facts_path: Path) -> dict[str, Any]:
    assumptions = load_assumptions(assumptions_path)
    aggregates = ingest(input_path)
    public_facts = read_public_facts(public_facts_path, aggregates.max_date, assumptions)
    portfolio, _ = model_portfolio(aggregates, assumptions, public_facts)
    write_outputs(portfolio, output_dir, dashboard_data)
    return portfolio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Corporate Wallet Digital Twin analytical outputs")
    parser.add_argument("--input", type=Path, default=Path("ref/Data Sets/Data.zip"))
    parser.add_argument("--output", type=Path, default=Path("legacy/v1/outputs/runtime"))
    parser.add_argument("--dashboard-data", type=Path, default=Path("legacy/v1/outputs/runtime/dashboard-data"))
    parser.add_argument("--assumptions", type=Path, default=Path("legacy/v1/config/assumptions.json"))
    parser.add_argument("--public-facts", type=Path, default=Path("data/public_facts.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    portfolio = run_pipeline(args.input, args.output, args.dashboard_data, args.assumptions, args.public_facts)
    print(json.dumps({"status": "ok", "as_of": portfolio["metadata"]["as_of"], **portfolio["summary"]}, indent=2))


if __name__ == "__main__":
    main()
