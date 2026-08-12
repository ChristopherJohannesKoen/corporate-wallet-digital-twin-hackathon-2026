"""Export the V3.1 JSON Schemas, OpenAPI document and validation artifacts.

Run after any contract change:

    python scripts/export_v31_contracts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.api import app  # noqa: E402
from wallet_twin_v31.contracts import (  # noqa: E402
    BusinessEvent,
    BusinessEvidenceClaim,
    BusinessGraphSnapshot,
    BusinessTwinSnapshot,
    ChangeDigest,
    ClientAnswer,
    ClientValue,
    ConversationBrief,
    ConversationCandidate,
    CoveragePlan,
    EvidenceGap,
    ExplanationPath,
    FeasibilityAssessment,
    FundingRouteProjection,
    IndicatorValue,
    InformationQuestion,
    ProblemHypothesis,
    SolutionEstimate,
    StakeholderResolution,
    ProviderBriefEvaluation,
    WalletOpportunityDetail,
    WalletPortfolioCell,
    WalletPortfolioProjection,
)
from wallet_twin_v31.events import V31EventEnvelope  # noqa: E402
from wallet_twin_v31.repository import repository  # noqa: E402
from wallet_twin_v2.canonical import write_canonical_json

CONTRACTS = ROOT / "contracts"
SCHEMAS = CONTRACTS / "jsonschema"
OUTPUTS = ROOT / "outputs" / "v31"
DASHBOARD_FIXTURE = ROOT / "dashboard" / "app" / "data" / "v31-fixture.json"

MODELS = {
    "v31-business-evidence-claim": BusinessEvidenceClaim,
    "v31-evidence-gap": EvidenceGap,
    "v31-indicator-value": IndicatorValue,
    "v31-business-twin-snapshot": BusinessTwinSnapshot,
    "v31-business-graph-snapshot": BusinessGraphSnapshot,
    "v31-business-event": BusinessEvent,
    "v31-change-digest": ChangeDigest,
    "v31-problem-hypothesis": ProblemHypothesis,
    "v31-stakeholder-resolution": StakeholderResolution,
    "v31-solution-estimate": SolutionEstimate,
    "v31-funding-route-projection": FundingRouteProjection,
    "v31-client-value": ClientValue,
    "v31-feasibility-assessment": FeasibilityAssessment,
    "v31-explanation-path": ExplanationPath,
    "v31-conversation-candidate": ConversationCandidate,
    "v31-conversation-brief": ConversationBrief,
    "v31-coverage-plan": CoveragePlan,
    "v31-information-question": InformationQuestion,
    "v31-client-answer": ClientAnswer,
    "v31-event-envelope": V31EventEnvelope,
    "v311-wallet-portfolio-cell": WalletPortfolioCell,
    "v311-wallet-portfolio-projection": WalletPortfolioProjection,
    "v311-wallet-opportunity-detail": WalletOpportunityDetail,
    "v311-provider-brief-evaluation": ProviderBriefEvaluation,
}


def write_json(path: Path, payload: Any) -> None:
    """Write at the governed published precision.

    The V3.1 exporter was written fresh and never inherited the canonicaliser the
    V2/V3 exporters use, so its artifacts carried full binary float precision
    against a byte-exact CI reproducibility gate.
    """
    write_canonical_json(path, payload)


def main() -> int:
    for name, model in MODELS.items():
        write_json(SCHEMAS / f"{name}.schema.json", model.model_json_schema())

    openapi = app.openapi()
    write_json(CONTRACTS / "openapi-v31.json", openapi)
    # ``openapi.json`` is the canonical composed contract consumed by platform
    # tooling.  The versioned copy remains available for explicit drift review.
    write_json(CONTRACTS / "openapi.json", openapi)

    write_json(
        OUTPUTS / "v31_validation_report.json",
        {
            "metadata": repository.metadata,
            "validation": repository.validation,
            "evidence_coverage": repository.evidence_coverage,
            "policy": repository.policy,
            "event_topics": repository.events_store.counts_by_topic(),
            "release": repository.release,
        },
    )
    write_json(
        OUTPUTS / "v31_coverage_plan.json",
        repository.plan.model_dump(mode="json"),
    )
    write_json(
        OUTPUTS / "v31_conversation_summaries.json",
        [
            repository.conversation_summary(item)
            for item in repository.conversation_list
        ],
    )
    write_json(
        OUTPUTS / "v31_business_twins.json",
        {
            entity_id: twin.model_dump(mode="json")
            for entity_id, twin in repository.twins.items()
        },
    )
    write_json(
        OUTPUTS / "v31_solution_estimates.json",
        {
            entity_id: {
                solution.value: estimate.model_dump(mode="json")
                for solution, estimate in estimates.items()
            }
            for entity_id, estimates in repository.estimates.items()
        },
    )
    write_json(
        OUTPUTS / "v31_business_evidence_claims.json",
        [claim.model_dump(mode="json") for claim in repository.registry.claims],
    )
    write_json(
        DASHBOARD_FIXTURE,
        {
            "projection": repository.decision_twin(
                repository.as_of, repository.week_start
            ),
            "conversations": {
                item.conversation_id: item.model_dump(mode="json")
                for item in repository.conversation_list
            },
            "briefs": {
                conversation_id: brief.model_dump(mode="json")
                for conversation_id, brief in repository.briefs.items()
            },
            "business_twins": {
                entity_id: twin.model_dump(mode="json")
                for entity_id, twin in repository.twins.items()
            },
            "business_graphs": {
                entity_id: graph.model_dump(mode="json")
                for entity_id, graph in repository.graphs.items()
            },
            "change_digests": {
                entity_id: digest.model_dump(mode="json")
                for entity_id, digest in repository.digests.items()
            },
            "funding_routes": {
                entity_id: route.model_dump(mode="json")
                for entity_id, route in repository.routes.items()
            },
        },
    )
    write_json(
        ROOT / "dashboard" / "app" / "data" / "wallet-v311-fixture.json",
        {
            "projection": repository.wallet_portfolio(repository.as_of).model_dump(mode="json"),
            "details": {
                cell.opportunity_id: repository.wallet_opportunity(
                    cell.opportunity_id, repository.as_of
                ).model_dump(mode="json")
                for cell in repository.wallet_portfolio(repository.as_of).cells
            },
        },
    )

    print(f"exported {len(MODELS)} JSON Schemas to {SCHEMAS.relative_to(ROOT)}")
    print(f"exported OpenAPI to {(CONTRACTS / 'openapi-v31.json').relative_to(ROOT)}")
    print(f"exported workbench fixture to {DASHBOARD_FIXTURE.relative_to(ROOT)}")
    print(f"exported validation artifacts to {OUTPUTS.relative_to(ROOT)}")
    summary = {
        "conversations": repository.validation["conversation_candidates"],
        "solution_projections": repository.validation["solution_projections"],
        "business_evidence_claims": repository.validation["business_evidence_claims"],
        "coverage_plan_size": repository.validation["coverage_plan_size"],
        "solver_status": repository.validation["coverage_solver_status"],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
