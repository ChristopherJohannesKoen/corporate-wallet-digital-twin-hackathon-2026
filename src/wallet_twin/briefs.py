from __future__ import annotations

from typing import Any


def format_money(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"R{value / 1_000_000_000:,.1f}bn"
    if absolute >= 1_000_000:
        return f"R{value / 1_000_000:,.1f}m"
    if absolute >= 1_000:
        return f"R{value / 1_000:,.1f}k"
    return f"R{value:,.0f}"


def format_pct(value: float) -> str:
    return f"{100 * value:.0f}%"


def build_banker_brief(client: dict[str, Any], opportunities: list[dict[str, Any]], as_of: str) -> str:
    ranked = sorted(opportunities, key=lambda item: item["priority_score"], reverse=True)
    top = ranked[0]
    evidence = client["evidence_summary"]
    timing = client["timing"]
    confidence_note = (
        "The evidence bar is met for a scenario-led conversation."
        if top["confidence"] >= 0.55
        else "Evidence is too thin for a product claim; use this as a discovery hypothesis only."
    )
    events = timing.get("trade_events_next_90d", 0)
    event_text = (
        f"{events} trade instruments with {format_money(timing.get('trade_events_value_zar', 0))} of value are scheduled to mature in the next 90 days."
        if events
        else "No trade-instrument maturity signal is present in the next 90 days."
    )
    public_facts = client.get("public_facts", [])
    anchor_impact = top.get("anchor_impact", {})
    public_note = (
        f"This showcase has {len(public_facts)} audited public facts and {client['evidence_summary'].get('active_public_anchors', 0)} active product anchors. "
        f"For {top['product']}, the evidence reduces relative P10-P90 interval width by "
        f"{format_pct(anchor_impact.get('relative_interval_width_reduction', 0))} and lifts confidence from "
        f"{format_pct(anchor_impact.get('confidence_before', top['confidence']))} to {format_pct(top['confidence'])}."
        if public_facts and anchor_impact.get("active")
        else "No audited public financial statement anchor is available for this relationship, so the wallet remains prior-led."
    )
    source_lines = [
        f"- [{fact['fact_id']}: {fact['source_title']}, p.{fact['page']}]({fact['source_url']}) "
        f"(period end {fact['period_end']}; public from {fact['available_date']})"
        for fact in public_facts
        if fact["fact_id"] in anchor_impact.get("fact_ids", [])
    ]

    lines = [
        f"# {client['entity_name']} - banker brief",
        "",
        f"**As of:** {as_of}  ",
        f"**Sector:** {client['sector'].replace('_', ' ').title()}  ",
        f"**Confidence:** {top['confidence_label']} ({format_pct(top['confidence'])})",
        "",
        "## Situation",
        f"The relationship shows {client['relationship_breadth']} active product signals and {client['country_count']} cross-border counterpart countries. "
        f"Observed last-12-month activity across the supplied views is {format_money(client['observed_ltm_zar'])}. [OBS-CLIENT-LTM]",
        "",
        "## Current relationship",
        f"Activity is recurrent in {format_pct(evidence['overall_recurrence'])} of possible client-product months. "
        f"The bank observation is broad enough to model a wallet, but it does not reveal competitor activity or an exact share. [DER-RELATIONSHIP]",
        "",
        "## Latent wallet and share",
        f"For {top['product']}, observed activity is {format_money(top['observed_activity_zar'])}. "
        f"The model-based total-wallet median is {format_money(top['total_wallet_zar']['p50'])}, with a P10-P90 range of "
        f"{format_money(top['total_wallet_zar']['p10'])} to {format_money(top['total_wallet_zar']['p90'])}. [MOD-{top['product'].upper().replace(' ', '-')}-WALLET]",
        f"Estimated current share is {format_pct(top['current_share']['p50'])}; this is a prior-conditioned estimate, not an observed fact. "
        f"The explicit identification envelope is {format_money(top['partial_identification_zar']['lower'])} to {format_money(top['partial_identification_zar']['upper'])}. [ASM-SHARE-PRIOR]",
        "",
        "## Contestable opportunity",
        f"The base target-share scenario is {format_pct(top['assumptions']['target_share']['base'])}. "
        f"At the declared economic-rate assumptions, the revenue-gap median is {format_money(top['revenue_gap_zar']['p50'])} "
        f"(P10 {format_money(top['revenue_gap_zar']['p10'])}; P90 {format_money(top['revenue_gap_zar']['p90'])}). [MOD-GAP]",
        "",
        "## Why now",
        f"The timing score is {format_pct(top['timing_score'])}. {event_text} "
        f"The seasonal-naive next-quarter signal is {format_money(timing.get('next_quarter_forecast_zar', 0))}. [DER-TIMING]",
        "",
        "## Evidence and confidence",
        f"{confidence_note} {public_note} The model still does not claim a fully identified wallet.",
        "",
        "### Public anchor citations",
        *(source_lines or ["- None available for this relationship."]),
        "",
        "## Client questions",
        f"1. What share of the client's {top['product'].lower()} activity sits outside Standard Bank today?",
        "2. Which entities, currencies, corridors, and legal mandates are in scope for a first move?",
        "3. What pricing, implementation, risk, or incumbent-bank constraint would prevent the target-share scenario?",
        "",
        "## Next action",
        f"Run a 30-minute discovery session on {top['product']}. Validate the activity perimeter and incumbent share before quoting economics. "
        "Record the recommendation, action, and outcome in `data/interventions.csv` so future versions can estimate uplift rather than propensity.",
    ]
    return "\n".join(lines) + "\n"


def brief_summary(client: dict[str, Any], opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    top = max(opportunities, key=lambda item: item["priority_score"])
    return {
        "product": top["product"],
        "headline": f"Validate {top['product'].lower()} share before proposing a {format_money(top['revenue_gap_zar']['p50'])} base-case gap.",
        "why_now": client["timing"]["reason"],
        "confidence": top["confidence_label"],
        "questions": [
            "What activity is held with other banks?",
            "Which entities and mandates can move first?",
            "What blocks the target-share scenario?",
        ],
    }
