"""Export the promotion readiness fixture the workbench renders.

Shaped for the view rather than dumping the full readiness payload: the
workbench needs one row per gate with both track verdicts side by side, and
building that in TypeScript would put the projection logic somewhere the Python
tests cannot reach it.

**No composite promotability figure is emitted, and that is enforced rather than
observed.** A single percentage is exactly the summary a reader would take away
instead of the substance, and it would let a fully-rehearsed system read as
nearly production-ready. ``assert_no_composite_score`` runs over the payload
before it is written.

    python scripts/export_v32_workbench_fixture.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.canonical import write_canonical_json  # noqa: E402
from wallet_twin_v32 import (  # noqa: E402
    CATALOGUE_VERSION,
    GATES_BY_ID,
    STATE_MACHINE_VERSION,
    assert_no_composite_score,
)
from wallet_twin_v32.catalogue import severity_weight  # noqa: E402
from wallet_twin_v32.repository import PromotionRepository  # noqa: E402
from wallet_twin_v32.scoring import score_breakdown  # noqa: E402
from wallet_twin_v32.states import PROMOTION_ORDER, TRANSITION_IDS, rank  # noqa: E402

FIXTURE = ROOT / "dashboard" / "app" / "data" / "promotion-fixture.json"

#: Four states a cell can be in, and what each means. Deliberately four rather
#: than a red/green pair: "the bank passed this" and "the rehearsal passed this"
#: are different facts, and "nobody has looked" is different again from "this
#: failed".
PROJECTION_LEGEND = {
    "real-pass": "The bank has satisfied this gate with admissible evidence.",
    "rehearsal-pass": "The machinery works. The bank has not satisfied this.",
    "waiting": "Not yet evaluated on either track.",
    "failed": "Evaluated and failed.",
}


def _projection(real_outcome: str, rehearsal_outcome: str) -> str:
    if real_outcome in {"PASS", "NOT_REQUIRED", "WAIVED"}:
        return "real-pass"
    if real_outcome == "FAIL" or rehearsal_outcome == "FAIL":
        return "failed"
    if rehearsal_outcome in {"PASS", "NOT_REQUIRED", "WAIVED"}:
        return "rehearsal-pass"
    return "waiting"


def _repository() -> PromotionRepository:
    """A fresh repository, never the module-level singleton.

    ``wallet_twin_v32.repository.repository`` is process-wide and the promotion
    service tests write to it through the API. Exporting from it made this
    artifact depend on which tests had already run — the committed fixture and a
    rebuild disagreed, and the byte-reproducibility gate would have failed in CI
    for a reason that had nothing to do with the fixture.
    """
    return PromotionRepository()


def gate_rows(repository: PromotionRepository) -> List[Dict[str, Any]]:
    breakdown = score_breakdown(repository.evaluations)
    envelopes = {item.evidence_id: item for item in repository.envelopes()}
    evidence = {item.evidence_id: item for item in repository.evidence()}

    rows: List[Dict[str, Any]] = []
    for gate_id, row in breakdown.items():
        definition = GATES_BY_ID[gate_id]
        evidence_id = f"ev-{gate_id}"
        item = evidence.get(evidence_id)
        envelope = envelopes.get(evidence_id)
        rows.append(
            {
                "gate_id": gate_id,
                "title": definition.title,
                "transition_id": definition.transition_id,
                "severity": definition.severity.value,
                "severity_weight": severity_weight(definition),
                "blocking": definition.blocking,
                "requirement": definition.requirement,
                "consequence_if_failed": definition.consequence_if_failed,
                "real_outcome": row["real_outcome"],
                "rehearsal_outcome": row["rehearsal_outcome"],
                "projection": _projection(
                    str(row["real_outcome"]), str(row["rehearsal_outcome"])
                ),
                "evidence_mode": row["real_evidence_mode"]
                or (item.mode.value if item else None),
                "minimum_real_evidence_mode": definition.minimum_real_evidence_mode.value,
                "artifact_sha256": item.content_sha256 if item else None,
                "signature_status": envelope.signature_status if envelope else "UNSIGNED",
                "signing_key_id": envelope.key_id if envelope else None,
                "trust_domain": envelope.trust_domain if envelope else None,
                "owner_role": definition.owner_role,
                "approver_role": definition.approver_role,
                "freshness_days": definition.freshness_days,
                "expires_at": item.expires_at.isoformat() if item and item.expires_at else None,
                "what_would_make_real_pass": definition.what_would_make_real_pass,
                "failure_injection_verified": row["failure_injection_verified"],
                "ber_contribution": row["ber_contribution"],
            }
        )
    return rows


def build_fixture() -> Dict[str, Any]:
    repository = _repository()
    decision = repository.decision()
    clock = repository.clock()
    readiness = repository.readiness()

    rows = gate_rows(repository)
    by_transition = {
        transition: [row for row in rows if row["transition_id"] == transition]
        for transition in TRANSITION_IDS
    }

    fixture: Dict[str, Any] = {
        "fixture_version": "v32-promotion-workbench-fixture-1.0.0",
        "catalogue_version": CATALOGUE_VERSION,
        "state_machine_version": STATE_MACHINE_VERSION,
        "as_of": decision.as_of.isoformat(),
        "generated_at": decision.generated_at.isoformat(),
        # The summary strip. Two scores, never one.
        "summary": {
            "real_state": decision.real_state.value,
            "rehearsed_state": decision.rehearsed_state.value,
            "bank_shadow_authorized": decision.bank_shadow_authorized,
            "promotion_machinery_readiness": decision.score.promotion_machinery_readiness,
            "bank_evidence_readiness": decision.score.bank_evidence_readiness,
            "synthetic_weight_excluded_from_ber": decision.score.synthetic_weight_excluded_from_ber,
            "pmr_weight_available": decision.score.pmr_weight_available,
            "package_status": "SHADOW_DEPLOYMENT_PACKAGE_READY",
            "bank_production_status": "NOT_PROMOTABLE",
        },
        "states": [
            {
                "state": state.value,
                "index": index,
                "real_attained": rank(decision.real_state) >= rank(state),
                "rehearsed_attained": rank(decision.rehearsed_state) >= rank(state),
            }
            for index, state in enumerate(PROMOTION_ORDER)
        ],
        "transitions": [
            {
                **row,
                "gates": by_transition[row["transition_id"]],
            }
            for row in readiness["transitions"]
        ],
        "capabilities": readiness["capabilities"],
        "clock": {
            "rehearsal_days_elapsed": clock.rehearsal_days_elapsed,
            "consecutive_clean_rehearsal_days": clock.consecutive_clean_rehearsal_days,
            # Published beside the rehearsal count everywhere it appears. The
            # workbench renders them as a pair for the same reason.
            "elapsed_bank_shadow_days": clock.elapsed_bank_shadow_days,
            "incidents_injected": clock.incidents_injected,
            "last_reset_reason": clock.last_reset_reason,
        },
        "signing": {
            "executed": readiness["signing"]["executed"],
            "not_executed": readiness["signing"]["not_executed"],
            "real_bank_signing_available": readiness["signing"][
                "real_bank_signing_available"
            ],
        },
        "projection_legend": dict(PROJECTION_LEGEND),
        "gates_without_failure_injection": readiness["gates_without_failure_injection"],
        "event_counts": readiness["event_counts"],
        "why_no_single_percentage": (
            "PMR and BER are published separately and never combined. A single "
            "promotability figure is the number a reader would take away instead "
            "of the substance, and it would let a fully-rehearsed system with no "
            "bank evidence read as nearly production-ready."
        ),
    }

    # Enforced, not observed. This is the one property of the view that a later
    # refactor could undo without anybody noticing.
    assert_no_composite_score(fixture)
    assert_no_composite_score(fixture["summary"])
    return fixture


def main() -> int:
    fixture = build_fixture()
    write_canonical_json(FIXTURE, fixture)
    print(
        f"wrote {FIXTURE.relative_to(ROOT)} "
        f"({sum(len(item['gates']) for item in fixture['transitions'])} gates, "
        f"real={fixture['summary']['real_state']}, "
        f"rehearsed={fixture['summary']['rehearsed_state']}, "
        f"PMR={fixture['summary']['promotion_machinery_readiness']}, "
        f"BER={fixture['summary']['bank_evidence_readiness']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
