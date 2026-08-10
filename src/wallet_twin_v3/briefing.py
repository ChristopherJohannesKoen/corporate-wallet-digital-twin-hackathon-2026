from __future__ import annotations

from typing import Any, Sequence

from wallet_twin_v2.contracts import OpportunityView

from .contracts import V3OpportunityView


def compile_decision_brief(
    opportunity: OpportunityView,
    v3: V3OpportunityView,
    facts: Sequence[dict[str, Any]],
    selected_for_portfolio: bool,
) -> dict[str, Any]:
    """Compile a provider-safe claim pack for the existing governed LLM gateway."""
    citations = [
        {
            "fact_id": fact["fact_id"],
            "label": f"{fact['source_title']} p.{fact['page']}",
            "url": fact["source_url"],
            "available_date": fact["available_date"],
            "approval_status": fact["approval_status"],
        }
        for fact in facts
    ]
    model_claims = [
        {
            "claim": f"Estimated latent external wallet is ZAR {v3.shadow_wallet.latent_external_wallet.median:,.0f} at the scenario median.",
            "claim_class": "SCENARIO",
            "support": v3.shadow_wallet.reconstruction_id,
        },
        {
            "claim": f"PU product-need probability is {v3.need.product_need_probability:.1%} under the SCAR assumption.",
            "claim_class": "POSTERIOR",
            "support": "pu-need-v3.0.0",
        },
        {
            "claim": f"Modelled wallet-leakage alarm probability is {v3.leakage.alarm_probability:.1%}.",
            "claim_class": "POSTERIOR",
            "support": "bocpd-leakage-v3.0.0",
        },
    ]
    return {
        "opportunity_id": opportunity.opportunity_id,
        "headline": f"{opportunity.entity_name} · {opportunity.product}",
        "decision": "Prioritise for governed RM review"
        if selected_for_portfolio
        else "Hold outside current RM capacity",
        "observed": {
            "activity_zar": float(opportunity.observed_activity.normalized_amount),
            "claim_class": "OBSERVED",
            "provenance": "SYN_BANK_SIMULATION",
        },
        "public_evidence": citations,
        "model_claims": model_claims,
        "missing_evidence": [
            "direct E3 multibank share observation",
            "approved bank economics",
            "qualified RM action and outcome history",
        ],
        "llm_contract": {
            "allowed_input": "this claim pack only",
            "required_output": "schema-constrained prose preserving every number and citation",
            "external_tools": False,
            "autonomous_action": False,
            "publication": False,
            "fallback": "this deterministic brief",
        },
        "prohibited_phrases": [
            "measured competitor share",
            "causal uplift",
            "optimal target share",
        ],
    }
