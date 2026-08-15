"""Export the canonical V3.2 hackathon submission facts.

Judging surfaces used to restate live-provider, wallet and promotion status by
hand.  This exporter makes those statements data: the deck, PDF, notebook,
workbench and consistency tests all consume the same compact, public-safe
projection.  It never stores credentials or full provider request payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wallet_twin_v2.canonical import write_canonical_json

ROOT = Path(__file__).resolve().parents[1]
VERSION = "3.2.0"
AS_OF = "2026-06-30"

LIVE_REPORT = ROOT / "outputs/v2_validation/live_provider_comparison.json"
WALLET_FIXTURE = ROOT / "dashboard/app/data/wallet-v311-fixture.json"
V31_FIXTURE = ROOT / "dashboard/app/data/v31-fixture.json"
PROMOTION_FIXTURE = ROOT / "dashboard/app/data/promotion-fixture.json"
SENSITIVITY_FIXTURE = ROOT / "dashboard/app/data/shadow-fixture.json"
MEASUREMENT_SENSITIVITY = ROOT / "outputs/v2_validation/measurement_policy_sensitivity.json"

TARGETS = (
    ROOT / "data/v2/submission_truth_v3.2.0.json",
    ROOT / "dashboard/app/data/submission-truth-v3.2.0.json",
)


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def accepted_projection(item: dict[str, Any]) -> dict[str, Any]:
    """Retain only publication-safe evidence for an accepted provider run."""

    return {
        "evaluation_id": item["evaluation_id"],
        "entity_id": item["entity_id"],
        "entity_name": item["entity_name"],
        "provider": item["provider"],
        "canonical_model_id": item["canonical_model_id"],
        "model_resolution": item["model_resolution"],
        "execution_status": item["execution_status"],
        "acceptance_status": item["acceptance_status"],
        "pack_hash": item["pack_hash"],
        "prompt_version": item["prompt_version"],
        "schema_version": item["schema_version"],
        "validation_metrics": item["validation_metrics"],
        "latency_ms": item["latency_ms"],
        "input_tokens": item["input_tokens"],
        "output_tokens": item["output_tokens"],
        "estimated_cost_usd": item["estimated_cost_usd"],
        "accepted_narrative": item["accepted_narrative"],
        "deterministic_fallback": item["deterministic_fallback"],
        "data_classification": item["data_classification"],
        "credential_retained": item["credential_retained"],
        "request_payload_retained": item["request_payload_retained"],
    }


def build_truth() -> dict[str, Any]:
    report = load(LIVE_REPORT)
    wallet_envelope = load(WALLET_FIXTURE)
    wallet = wallet_envelope["projection"]
    details = wallet_envelope["details"]
    v31 = load(V31_FIXTURE)["projection"]
    promotion = load(PROMOTION_FIXTURE)
    sensitivity = load(SENSITIVITY_FIXTURE)["sensitivity"]
    measurement = load(MEASUREMENT_SENSITIVITY)

    accepted = [
        item for item in report["evaluations"]
        if item.get("acceptance_status") == "ACCEPTED"
    ]
    if len(accepted) != report["accepted_runs"]:
        raise RuntimeError("live provider accepted_runs disagrees with evaluations")

    showcase_choice = {"E01": "openai", "E02": "anthropic", "E09": "google"}
    showcase: dict[str, dict[str, Any]] = {}
    for entity_id, provider in showcase_choice.items():
        match = next(
            (
                item for item in accepted
                if item["entity_id"] == entity_id and item["provider"] == provider
            ),
            None,
        )
        if match is None:
            raise RuntimeError(f"missing accepted showcase brief: {entity_id}/{provider}")
        showcase[entity_id] = accepted_projection(match)

    blocked = [
        {
            "entity_id": item["entity_id"],
            "entity_name": item["entity_name"],
            "provider": item["provider"],
            "canonical_model_id": item["canonical_model_id"],
            "model_resolution": item["model_resolution"],
            "execution_status": item["execution_status"],
            "acceptance_status": item["acceptance_status"],
            "pack_hash": item["pack_hash"],
            "rejection_reason_codes": item.get("rejection_reason_codes", []),
            "violations": item.get("violations", []),
            "deterministic_fallback_retained": bool(item.get("deterministic_fallback")),
        }
        for item in report["evaluations"]
        if item.get("acceptance_status") != "ACCEPTED"
    ]

    cells = sorted(
        (cell for cell in wallet["cells"] if cell.get("rank") is not None),
        key=lambda item: item["rank"],
    )
    top_opportunities = [
        {
            "rank": cell["rank"],
            "opportunity_id": cell["opportunity_id"],
            "entity_id": cell["entity_id"],
            "entity_name": cell["entity_name"],
            "product": cell["product"],
            "scenario_contribution_median_zar": cell["scenario_contribution"]["median"],
            "evidence_tier": cell["evidence_tier"],
            "anchor_activation": cell["anchor_activation"],
            "timing_90d": cell["timing"]["probability_90d"],
            "timing_method": cell["timing"]["method"],
        }
        for cell in cells[:10]
    ]

    bhp = details["E01-trade-finance"]
    tf = sensitivity["product_summary"]["Trade finance"]
    arms = {
        weight: {
            "policy_version": measurement["arms"][weight]["policy_version"],
            "wallet_90_coverage": measurement["arms"][weight]["known_truth_diagnostics"]["wallet_90_coverage"],
            "wallet_scaled_crps": measurement["arms"][weight]["known_truth_diagnostics"]["wallet_scaled_crps"],
            "top10_share": measurement["arms"][weight]["trade_finance"]["top10_share"],
            "first_ranked": measurement["arms"][weight]["trade_finance"]["first_ranked"],
            "majority_dominant": measurement["arms"][weight]["trade_finance"]["majority_dominant"],
        }
        for weight in ("0.20", "0.35", "0.50")
    }

    summary = promotion["summary"]
    clock = promotion["clock"]
    evidence = v31["evidence_coverage"]
    return {
        "version": VERSION,
        "as_of": AS_OF,
        "story": "Syn Bank activity + approved public evidence -> wallet/share intervals -> contestable gap -> stakeholder conversation -> grounded briefing",
        "wallet": {
            "clients": 20,
            "products": 5,
            "cells": len(wallet["cells"]),
            "approved_anchor_cells": wallet["approved_anchor_cells"],
            "prior_led_cells": wallet["prior_led_cells"],
            "public_source_facts": wallet["approved_source_facts"] + wallet["pending_source_facts"],
            "approved_source_facts": wallet["approved_source_facts"],
            "pending_source_facts": wallet["pending_source_facts"],
            "governed_analytical_claims": evidence["total_claims"],
            "governed_claims_approved": evidence["approval_counts"]["APPROVED"],
            "governed_claims_pending": evidence["approval_counts"]["PENDING_REVIEW"],
            "top_opportunities": top_opportunities,
            "bhp_trade_finance": {
                "rank": bhp["cell"]["rank"],
                "observed_activity_zar": bhp["explanation"]["A"]["value"],
                "wallet_interval_zar": bhp["explanation"]["T"],
                "share_interval": bhp["explanation"]["q"],
                "target_share": bhp["explanation"]["q_star"]["value"],
                "contestable_interval_zar": bhp["explanation"]["G"],
                "scenario_contribution_median_zar": bhp["cell"]["scenario_contribution"]["median"],
                "permitted_action": bhp["decision_twin_action"]["permitted_action"],
                "why_now": bhp["decision_twin_action"]["why_now"],
            },
        },
        "sensitivity": {
            "draws": sensitivity["draws"],
            "trade_finance_first_rank_frequency": tf["first_rank_frequency"],
            "trade_finance_majority_dominance_frequency": tf["majority_dominance_frequency"],
            "trade_finance_mean_top10_share": tf["mean_top10_share"],
            "trade_finance_absolute_economics_zar": tf["absolute_economics"],
            "e1_weight_arms": arms,
            "top8_invariant_across_e1_weights": measurement["top8_invariant"],
            "boundary": measurement["known_truth_boundary"],
        },
        "genai": {
            "evaluation_scope": "HACKATHON_EXTERNAL_PROVIDER_EVALUATION",
            "target_runs": report["target_runs"],
            "runs": report["runs"],
            "accepted_runs": report["accepted_runs"],
            "blocked_runs": report["runs"] - report["accepted_runs"],
            "submission_gate_passed": report["submission_gate_passed"],
            "accepted_providers": report["accepted_providers"],
            "accepted_clients": report["accepted_clients"],
            "showcase_briefs": showcase,
            "blocked_evaluations": blocked,
            "bank_authorized_live_genai": False,
            "claim_boundary": "Accepted provider outputs passed schema, numeric, citation, abstention and unsupported-claim controls; this does not constitute bank provider approval.",
        },
        "promotion": {
            "real_state": summary["real_state"],
            "rehearsed_state": summary["rehearsed_state"],
            "package_status": summary["package_status"],
            "promotion_machinery_readiness": summary["promotion_machinery_readiness"],
            "bank_evidence_readiness": summary["bank_evidence_readiness"],
            "bank_shadow_authorized": summary["bank_shadow_authorized"],
            "bank_production_status": summary["bank_production_status"],
            "shadow_rehearsal_days": clock["consecutive_clean_rehearsal_days"],
            "elapsed_bank_shadow_days": clock["elapsed_bank_shadow_days"],
            "claim_boundary": "Simulation proves the promotion machinery and refusal behavior; it contributes zero to real-bank authorization.",
        },
        "submission": {
            "hackathon_status": "HACKATHON_SUBMISSION_READY",
            "commercial_close": "See the wallet. Size the gap. Choose the conversation.",
            "bank_status": "NOT_PROMOTABLE",
        },
    }


def main() -> None:
    truth = build_truth()
    for target in TARGETS:
        write_canonical_json(target, truth)
    print(json.dumps({
        "status": "PASS",
        "version": VERSION,
        "targets": [path.relative_to(ROOT).as_posix() for path in TARGETS],
        "accepted_provider_runs": truth["genai"]["accepted_runs"],
        "rehearsed_state": truth["promotion"]["rehearsed_state"],
    }, indent=2))


if __name__ == "__main__":
    main()
