"""Additive V3.1 API surface.

``/v1`` and the existing ``/v3`` contracts stay operational and unchanged.  V3
remains the stable API major: there is deliberately no ``/v3.1`` route prefix,
because a dotted major would force every consumer to re-integrate for what is
an additive change.

All modelled reads require ``as_of``; ``since`` must not exceed ``as_of``.
Mutation endpoints require an idempotency key and create immutable events.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import Field

from wallet_twin_v2.api import authorize, principal
from wallet_twin_v2.contracts import EntitlementContext, StrictModel

from .briefs import compile_claim_pack
from .events import V31EventType, build_v31_event
from .feasibility import record_attestation
from .live_briefs import live_evaluation_summary, provider_brief_for_client
from .repository import repository
from .taxonomy import (
    BankingSolution,
    BusinessProblem,
    EligibilityDecision,
    FeasibilityGate,
    GateStatus,
    StakeholderRole,
)

router = APIRouter(prefix="/v3", tags=["V3.1 decision twin"])


def _require_idempotency(key: Optional[str]) -> str:
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required for mutating requests",
        )
    return key


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class ScenarioConversationRequest(StrictModel):
    conversation_id: str
    as_of: date
    policy_version: str
    economics_version: str
    need_probability_override: Optional[float] = Field(default=None, ge=0, le=1)
    client_value_multiplier: float = Field(default=1.0, gt=0, le=10)
    bank_value_multiplier: float = Field(default=1.0, gt=0, le=10)


class QuestionResponseRequest(StrictModel):
    answer_id: str
    answer_state_id: str
    respondent_role: StakeholderRole
    respondent_type: str = Field(min_length=2)
    consent_reference: str = Field(min_length=8)
    scope: str = Field(min_length=3)
    source: str = Field(min_length=3)
    free_text: Optional[str] = Field(default=None, max_length=2000)


class AttestationRequest(StrictModel):
    gate: FeasibilityGate
    status: GateStatus
    role: str = Field(min_length=2)
    reason: str = Field(min_length=8)


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
@router.get("/decision-twin")
def decision_twin(
    as_of: date = Query(...),
    week_start: Optional[date] = Query(default=None),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v31:decision-twin:read",
        resource_type="v31-projection",
        resource_id="decision-twin",
    )
    return repository.decision_twin(
        as_of, week_start or repository.week_start, context.client_ids
    )


@router.get("/wallet-portfolio")
def wallet_portfolio(
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v311:wallet-portfolio:read",
        resource_type="wallet-portfolio",
        resource_id=as_of.isoformat(),
    )
    return repository.wallet_portfolio(as_of, context.client_ids).model_dump(mode="json")


@router.get("/wallet-opportunities/{opportunity_id}")
def wallet_opportunity(
    opportunity_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    observation = repository.wallet_opportunity(opportunity_id, as_of, ["*"])
    authorize(
        context,
        action="v311:wallet-opportunity:read",
        resource_type="wallet-opportunity",
        resource_id=opportunity_id,
        client_id=observation.cell.entity_id,
        product=observation.cell.product,
        sensitive_economics=True,
    )
    return repository.wallet_opportunity(
        opportunity_id, as_of, context.client_ids
    ).model_dump(mode="json")


@router.get("/clients/{client_id}/briefing-notes")
def client_briefing_notes(
    client_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v311:briefing-notes:read",
        resource_type="client",
        resource_id=client_id,
        client_id=client_id,
    )
    items = [
        item for item in repository.conversations(as_of, context.client_ids)
        if item.entity_id == client_id
    ]
    items.sort(
        key=lambda item: (
            item.policy_rank.weekly_rank is None,
            item.policy_rank.weekly_rank or 10_000,
            -item.policy_rank.selection_stability,
        )
    )
    provider_brief = provider_brief_for_client(client_id)
    notes = []
    for item in items[:3]:
        deterministic = repository.brief(item.conversation_id, as_of, context.client_ids)
        notes.append({
            "conversation_id": item.conversation_id,
            "deterministic_brief": deterministic.model_dump(mode="json"),
            "accepted_provider_brief": provider_brief if not notes else None,
            "provider_evaluations": [provider_brief] if provider_brief and not notes else [],
            "live_provider_status": (
                "HACKATHON_EXTERNAL_PROVIDER_ACCEPTED"
                if provider_brief and not notes
                else "DETERMINISTIC_FALLBACK_AVAILABLE"
            ),
        })
    return {
        "entity_id": client_id,
        "as_of": as_of.isoformat(),
        "notes": notes,
        "live_evaluation": live_evaluation_summary(),
        "claim_boundary": (
            "Accepted provider briefs passed every critical hackathon validator. This is "
            "not bank-authorized LIVE_GENAI; deterministic output remains available beside it."
        ),
    }


@router.get("/clients/{client_id}/business-twin")
def business_twin(
    client_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v31:business-twin:read",
        resource_type="client",
        resource_id=client_id,
        client_id=client_id,
    )
    twin = repository.business_twin(client_id, as_of, context.client_ids)
    return {
        "business_twin": twin.model_dump(mode="json"),
        "indicators": {
            key: value.model_dump(mode="json")
            for key, value in repository.indicators[client_id].items()
        },
        "evidence_gaps": [gap.model_dump(mode="json") for gap in twin.evidence_gaps],
    }


@router.get("/clients/{client_id}/business-graph")
def business_graph(
    client_id: str,
    as_of: date = Query(...),
    explainable_only: bool = Query(default=True),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v31:business-graph:read",
        resource_type="client",
        resource_id=client_id,
        client_id=client_id,
    )
    graph = repository.business_graph(
        client_id, as_of, context.client_ids, explainable_only=explainable_only
    )
    paths = [
        item.explanation_path.model_dump(mode="json")
        for item in repository.conversations(as_of, context.client_ids)
        if item.entity_id == client_id
    ]
    return {
        "business_graph": graph.model_dump(mode="json"),
        "explanation_paths": paths[:20],
        "explainable_only": explainable_only,
    }


@router.get("/clients/{client_id}/change-digest")
def change_digest(
    client_id: str,
    as_of: date = Query(...),
    since: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    if since > as_of:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="since must not exceed as_of",
        )
    authorize(
        context,
        action="v31:change-digest:read",
        resource_type="client",
        resource_id=client_id,
        client_id=client_id,
    )
    digest = repository.change_digest(client_id, since, as_of, context.client_ids)
    return digest.model_dump(mode="json")


@router.get("/conversations")
def conversations(
    as_of: date = Query(...),
    client_id: Optional[str] = None,
    stakeholder_role: Optional[StakeholderRole] = None,
    problem: Optional[BusinessProblem] = None,
    solution: Optional[BankingSolution] = None,
    eligibility: Optional[EligibilityDecision] = None,
    frontier: Optional[str] = Query(default=None, pattern="^(client|portfolio)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v31:conversations:read",
        resource_type="v31-projection",
        resource_id="conversations",
    )
    items = repository.conversations(as_of, context.client_ids)
    if client_id:
        items = [item for item in items if item.entity_id == client_id]
    if stakeholder_role:
        items = [
            item for item in items if item.stakeholder.primary_role is stakeholder_role
        ]
    if problem:
        items = [item for item in items if item.problem.problem is problem]
    if solution:
        items = [
            item for item in items if solution in item.solution_bundle.solutions
        ]
    if eligibility:
        items = [item for item in items if item.eligibility is eligibility]
    if frontier == "client":
        items = [item for item in items if item.pareto_status.client_frontier_member]
    elif frontier == "portfolio":
        items = [item for item in items if item.pareto_status.portfolio_frontier_member]
    window = items[offset : offset + limit]
    return {
        "metadata": repository.metadata,
        "count": len(items),
        "offset": offset,
        "limit": limit,
        "items": [item.model_dump(mode="json") for item in window],
        "release": repository.release,
    }


@router.get("/conversations/{conversation_id}")
def conversation(
    conversation_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    item = repository.conversation(conversation_id, as_of, ["*"])
    authorize(
        context,
        action="v31:conversation:read",
        resource_type="conversation",
        resource_id=conversation_id,
        client_id=item.entity_id,
    )
    entitled = repository.conversation(conversation_id, as_of, context.client_ids)
    return {
        "conversation": entitled.model_dump(mode="json"),
        "questions": [
            question.model_dump(mode="json")
            for question in repository.questions_for(conversation_id)
        ],
    }


@router.get("/conversations/{conversation_id}/brief")
def brief(
    conversation_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    item = repository.conversation(conversation_id, as_of, ["*"])
    authorize(
        context,
        action="v31:brief:read",
        resource_type="conversation",
        resource_id=conversation_id,
        client_id=item.entity_id,
    )
    entitled = repository.conversation(conversation_id, as_of, context.client_ids)
    deterministic = repository.brief(conversation_id, as_of, context.client_ids)
    pack = compile_claim_pack(entitled, repository.registry)
    return {
        "brief": deterministic.model_dump(mode="json"),
        "claim_pack": pack,
        "llm_contract": {
            "allowed_input": "this claim pack only",
            "required_output": "schema-constrained prose preserving every number and citation",
            "external_tools": False,
            "autonomous_action": False,
            "publication": False,
            "fallback": "this deterministic brief",
        },
    }


@router.get("/coverage-plan")
def coverage_plan(
    as_of: date = Query(...),
    week_start: Optional[date] = Query(default=None),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v31:coverage-plan:read",
        resource_type="v31-coverage-plan",
        resource_id="current",
    )
    plan = repository.coverage_plan(
        as_of, week_start or repository.week_start, context.client_ids
    )
    return {
        "coverage_plan": plan.model_dump(mode="json"),
        "above_the_fold": [
            entry.model_dump(mode="json") for entry in plan.entries[: plan.above_the_fold]
        ],
        "diagnostics": {
            "solver": plan.solver,
            "solver_status": plan.solver_status,
            "degraded_fallback": plan.degraded_fallback,
            "objective_value": plan.objective_value,
            "expected_adjusted_benefit": plan.expected_adjusted_benefit,
            "cvar10_adjusted_benefit": plan.cvar10_adjusted_benefit,
            "scenario_draws": plan.scenario_draws,
            "weights_version": plan.weights_version,
            "constraints": plan.constraints,
            "constraint_report": plan.constraint_report,
        },
    }


@router.get("/funding-routes/{client_id}")
def funding_routes(
    client_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v31:funding-routes:read",
        resource_type="client",
        resource_id=client_id,
        client_id=client_id,
        sensitive_economics=True,
    )
    projection = repository.funding_routes(client_id, as_of, context.client_ids)
    return {
        "funding_routes": projection.model_dump(mode="json"),
        "challenger_gate": repository.policy["funding_route_challenger_gate"],
    }


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
@router.post("/scenarios/conversations/evaluate")
def evaluate_conversation_scenario(
    request: ScenarioConversationRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    key = _require_idempotency(idempotency_key)
    item = repository.conversation(request.conversation_id, request.as_of, ["*"])
    authorize(
        context,
        action="v31:scenario:evaluate",
        resource_type="conversation",
        resource_id=request.conversation_id,
        client_id=item.entity_id,
        sensitive_economics=True,
    )
    entitled = repository.conversation(
        request.conversation_id, request.as_of, context.client_ids
    )
    client_total = entitled.client_value.monetised_total
    bank_total = entitled.bank_value.direct_contribution
    return {
        "publishes": False,
        "idempotency_key": key,
        "policy_version": request.policy_version,
        "economics_version": request.economics_version,
        "conversation_id": entitled.conversation_id,
        "baseline": {
            "need_probability": entitled.problem.probability,
            "client_value_median": client_total.median if client_total else None,
            "bank_value_median": bank_total.median if bank_total else None,
        },
        "scenario": {
            "need_probability": request.need_probability_override
            if request.need_probability_override is not None
            else entitled.problem.probability,
            "client_value_median": (
                client_total.median * request.client_value_multiplier
                if client_total
                else None
            ),
            "bank_value_median": (
                bank_total.median * request.bank_value_multiplier
                if bank_total
                else None
            ),
        },
        "status": "NON_PUBLISHING_SCENARIO_EVALUATION",
        "watermark": entitled.watermark,
        "note": (
            "Scenario evaluation never alters a published snapshot, a coverage plan or "
            "an approved evidence version."
        ),
    }


@router.post("/questions/{question_id}/responses", status_code=201)
def submit_question_response(
    question_id: str,
    request: QuestionResponseRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    key = _require_idempotency(idempotency_key)
    question = None
    for candidate_id, items in repository.questions.items():
        for item in items:
            if item.question_id == question_id:
                question = item
                break
        if question is not None:
            break
    if question is None:
        raise HTTPException(status_code=404, detail=f"unknown question: {question_id}")
    authorize(
        context,
        action="v31:client-answer:create",
        resource_type="information-question",
        resource_id=question_id,
        client_id=question.entity_id,
    )
    answer = repository.answers.submit(
        answer_id=request.answer_id,
        question=question,
        answer_state_id=request.answer_state_id,
        respondent_role=request.respondent_role,
        respondent_type=request.respondent_type,
        consent_reference=request.consent_reference,
        scope=request.scope,
        source=request.source,
        free_text=request.free_text,
    )
    repository.events_store.append(
        build_v31_event(
            V31EventType.CLIENT_ANSWER_SUBMITTED,
            entity_id=answer.entity_id,
            as_of=repository.as_of,
            conversation_id=question.conversation_id,
            idempotency_key=key,
            payload={
                "question_id": question_id,
                "answer_id": answer.answer_id,
                "approval_status": answer.approval_status.value,
            },
        )
    )
    return {
        "answer": answer.model_dump(mode="json"),
        "status": "PENDING_REVIEW",
        "effect_on_approved_models": "NONE_UNTIL_APPROVED",
        "note": (
            "This creates a pending E2 evidence candidate. It cannot alter an approved "
            "snapshot, interval or coverage plan until a reviewer approves it."
        ),
    }


@router.post("/feasibility/{conversation_id}/attestations", status_code=201)
def record_feasibility_attestation(
    conversation_id: str,
    request: AttestationRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    key = _require_idempotency(idempotency_key)
    item = repository.conversation(conversation_id, repository.as_of, ["*"])
    authorize(
        context,
        action="v31:feasibility:attest",
        resource_type="conversation",
        resource_id=conversation_id,
        client_id=item.entity_id,
    )
    if request.status is GateStatus.UNKNOWN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="an attestation must resolve the gate, not restate the unknown",
        )
    result = record_attestation(
        request.gate,
        request.status,
        role=request.role,
        reason=request.reason,
    )
    repository.events_store.append(
        build_v31_event(
            V31EventType.STAKEHOLDER_ATTESTATION_RECORDED,
            entity_id=item.entity_id,
            as_of=repository.as_of,
            conversation_id=conversation_id,
            solution_bundle_id=item.solution_bundle.bundle_id,
            idempotency_key=key,
            payload={
                "gate": request.gate.value,
                "status": request.status.value,
                "role": request.role,
            },
        )
    )
    return {
        "attestation": result.model_dump(mode="json"),
        "conversation_id": conversation_id,
        "note": (
            "The attestation is recorded as an immutable event. The published snapshot is "
            "rebuilt on the next scheduled run, not mutated in place."
        ),
    }


@router.get("/models/v31-validation")
def validation(context: EntitlementContext = Depends(principal)) -> dict:
    authorize(
        context,
        action="v31:model-validation:read",
        resource_type="v31-model",
        resource_id="suite",
    )
    return {
        "metadata": repository.metadata,
        "validation": repository.validation,
        "evidence_coverage": repository.evidence_coverage,
        "policy": repository.policy,
        "event_topics": repository.events_store.counts_by_topic(),
        "release": repository.release,
    }
