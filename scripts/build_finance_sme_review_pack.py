"""Build the governed four-eyes pack for the 51 pending public facts.

This script performs prioritisation and packaging only.  It cannot change an
approval status and deliberately emits blank, human-owned decision columns.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from wallet_twin_v2.canonical import artifact_timestamp
from wallet_twin_v2.evidence_qa import write_review_pack


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "audit"
VALIDATION_DIR = ROOT / "outputs" / "v2_validation"


def build() -> dict:
    qa = write_review_pack(VALIDATION_DIR)
    wallet = json.loads(
        (ROOT / "dashboard" / "app" / "data" / "wallet-v311-fixture.json").read_text(encoding="utf-8")
    )["projection"]

    entity_value: dict[str, float] = defaultdict(float)
    entity_name: dict[str, str] = {}
    for cell in wallet["cells"]:
        if cell["approval_state"] == "APPROVED":
            continue
        entity_value[cell["entity_id"]] += float(cell["scenario_contribution"]["median"])
        entity_name[cell["entity_id"]] = cell["entity_name"]

    ranked = sorted(entity_value, key=lambda entity_id: (-entity_value[entity_id], entity_id))
    total = sum(entity_value.values())
    cumulative = 0.0
    priority_entities: list[str] = []
    portfolio_priority = []
    for rank, entity_id in enumerate(ranked, start=1):
        value = entity_value[entity_id]
        cumulative += value
        share = cumulative / total if total else 0.0
        if len(priority_entities) < 10 and (not priority_entities or portfolio_priority[-1]["cumulative_value_share"] < 0.80):
            priority_entities.append(entity_id)
        portfolio_priority.append(
            {
                "rank": rank,
                "entity_id": entity_id,
                "entity_name": entity_name[entity_id],
                "prior_led_scenario_contribution_median_zar": round(value, 2),
                "cumulative_value_share": round(share, 6),
                "in_review_priority": entity_id in priority_entities,
            }
        )

    fact_rows = []
    for item in qa["facts_detail"]:
        fact_rows.append(
            {
                **item,
                "portfolio_priority_rank": ranked.index(item["entity_id"]) + 1,
                "in_80pct_review_priority": item["entity_id"] in priority_entities,
                "finance_sme_decision": "",
                "finance_sme_name": "",
                "finance_sme_decided_at": "",
                "independent_approver_decision": "",
                "independent_approver_name": "",
                "independent_approver_decided_at": "",
                "review_comment": "",
            }
        )

    report = {
        "version": "finance-sme-review-pack-3.1.1",
        "generated_at": artifact_timestamp(),
        "as_of": wallet["as_of"],
        "purpose": "Four-eyes review of pending public evidence candidates; no automated promotion is possible.",
        "approval_boundary": {
            "developer_qa_state": "DEVELOPER_VERIFIED means deterministic source/point-in-time QA passed.",
            "approval_state": "All 51 records remain PENDING_REVIEW until both accountable human decisions are recorded in the source-of-truth workflow.",
            "anchor_effect": "Pending or rejected records cannot activate anchors, alter wallet estimates, or support banker-facing claims.",
        },
        "source_facts": {"total": 82, "approved": 31, "pending": 51},
        "active_wallet_state": {"approved_anchor_cells": 15, "prior_led_cells": 85},
        "qa": {
            "pending_candidates": qa["facts"],
            "developer_verified": qa["developer_verified"],
            "failures": qa["fact_failures"],
            "human_approvals_completed": 0,
        },
        "portfolio_prioritisation": {
            "basis": "Corrected V3.1.1 prior-led scenario contribution P50; prioritisation is workflow triage, not evidence approval.",
            "total_prior_led_scenario_contribution_median_zar": round(total, 2),
            "target_cumulative_share": 0.80,
            "cap_clients": 10,
            "selected_clients": priority_entities,
            "selected_client_count": len(priority_entities),
            "achieved_cumulative_share": next(
                item["cumulative_value_share"]
                for item in portfolio_priority
                if item["entity_id"] == priority_entities[-1]
            ),
            "ranking": portfolio_priority,
        },
        "facts": fact_rows,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "V3.1.1-Finance-SME-Review-Pack.json"
    csv_path = OUTPUT_DIR / "V3.1.1-Finance-SME-Review-Pack.csv"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    csv_fields = [
        "portfolio_priority_rank", "in_80pct_review_priority", "fact_id", "entity_id", "entity_name",
        "concept", "value", "currency", "unit", "page", "source_url", "source_hash",
        "automated_status", "developer_qa_state", "approval_status", "finance_sme_decision",
        "finance_sme_name", "finance_sme_decided_at", "independent_approver_decision",
        "independent_approver_name", "independent_approver_decided_at", "review_comment",
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for row in sorted(fact_rows, key=lambda item: (item["portfolio_priority_rank"], item["entity_id"], item["fact_id"])):
            writer.writerow({field: row.get(field, "") for field in csv_fields})

    return {"json": str(json_path), "csv": str(csv_path), **report["qa"], **report["portfolio_prioritisation"]}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
