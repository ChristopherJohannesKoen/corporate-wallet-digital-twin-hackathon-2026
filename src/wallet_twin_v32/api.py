"""V3.2 promotion API.

Twelve ``/v3/promotion/*`` routes. ``/v3`` stays the API major: a dotted
``/v3.2`` would force every consumer to re-integrate for what is an additive
change.

Three rules, applied uniformly:

- **Reads require ``as_of``.** A promotion position without a date is
  unfalsifiable — it cannot be checked against the evidence that was available
  then.
- **Mutations require ``Idempotency-Key``.** Promotion events are immutable, so
  a retried request must resolve to the same event rather than a second one.
- **Fixture mode rejects real-track writes.** Enforced in the repository and
  surfaced here as 409, because a demonstration fixture producing bank
  authorisation is the worst failure this service could have.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from wallet_twin_v2.api import authorize, principal
from wallet_twin_v2.contracts import EntitlementContext, StrictModel

from .catalogue import CATALOGUE_VERSION, GATES_BY_ID, catalogue_summary
from .contracts import (
    GateEvaluation,
    GateEvidence,
    IncidentInjection,
    PromotionApproval,
    RehearsalScenario,
)
from .engine import capability_register, transition_report
from .events import PromotionEventType
from .modes import DecisionTrack, is_synthetic
from .repository import ApprovalBindingError, FixtureModeError, repository
from .rehearsal import rehearsal_report
from .scoring import score_breakdown
from .signers import signer_capability_report
from .states import (
    TRANSITION_IDS,
    PromotionState,
    is_legal_transition,
    next_state,
    transition_id as make_transition_id,
)

_MUTATION_CACHE: Dict[str, Dict[str, Any]] = {}
_REHEARSAL_RUNS: Dict[str, Dict[str, Any]] = {}
_REHEARSAL_INCIDENTS: Dict[str, list[Dict[str, Any]]] = {}

router = APIRouter(prefix="/v3/promotion", tags=["V3.2 promotion readiness"])


def _require_idempotency(key: Optional[str]) -> str:
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required for mutating requests",
        )
    return key


def _cached(operation: str, key: str) -> Optional[Dict[str, Any]]:
    return _MUTATION_CACHE.get(f"{operation}:{key}")


def _remember(operation: str, key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    _MUTATION_CACHE[f"{operation}:{key}"] = payload
    return payload


def _guard_fixture(track: DecisionTrack) -> None:
    if repository.fixture_mode and track is DecisionTrack.REAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "fixture mode refuses real-track writes; a demonstration "
                "fixture must never be able to produce bank authorisation"
            ),
        )


class EvaluationRequest(StrictModel):
    evaluation: GateEvaluation


class ApprovalRequest(StrictModel):
    approval: PromotionApproval


class EvidenceRequest(StrictModel):
    evidence: GateEvidence


class DecisionEvaluationRequest(StrictModel):
    as_of: date
    target_state: Optional[PromotionState] = None


class TransitionRequest(StrictModel):
    source_state: PromotionState
    track: DecisionTrack
    rationale: str


class RehearsalRequest(StrictModel):
    scenario: RehearsalScenario


class IncidentRequest(StrictModel):
    incident: IncidentInjection


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


@router.get("/state")
def promotion_state(
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """The published promotion position, both tracks."""
    authorize(
        context,
        action="v32:promotion-state:read",
        resource_type="promotion-decision",
        resource_id=as_of.isoformat(),
    )
    return repository.decision(as_of).model_dump(mode="json")


@router.get("/readiness")
def promotion_readiness(
    as_of: date = Query(...),
    target_state: Optional[PromotionState] = Query(default=None),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Everything the workbench renders, in one call."""
    authorize(
        context,
        action="v32:promotion-readiness:read",
        resource_type="promotion-readiness",
        resource_id=as_of.isoformat(),
    )
    payload = repository.readiness()
    payload["requested_target_state"] = target_state.value if target_state else None
    return payload


@router.get("/gates")
def promotion_gates(
    as_of: date = Query(...),
    transition_id: Optional[str] = Query(default=None),
    target_state: Optional[PromotionState] = Query(default=None),
    real_status: Optional[str] = Query(default=None),
    rehearsal_status: Optional[str] = Query(default=None),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """The gate catalogue as governed data."""
    authorize(
        context,
        action="v32:promotion-gates:read",
        resource_type="promotion-catalogue",
        resource_id=transition_id or "all",
    )
    if transition_id is not None and transition_id not in TRANSITION_IDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown transition_id: {transition_id}",
        )
    if target_state is not None and target_state is not PromotionState.OFFLINE_CANDIDATE:
        inferred_source = list(PromotionState)[list(PromotionState).index(target_state) - 1]
        expected_transition = make_transition_id(inferred_source, target_state)
        if transition_id is not None and transition_id != expected_transition:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="transition_id and target_state identify different transitions",
            )
        transition_id = expected_transition
    breakdown = score_breakdown(repository.evaluations)
    gates = [
        {
            **gate.model_dump(mode="json"),
            "real_status": breakdown[gate.gate_id]["real_outcome"],
            "rehearsal_status": breakdown[gate.gate_id]["rehearsal_outcome"],
        }
        for gate in GATES_BY_ID.values()
        if transition_id is None or gate.transition_id == transition_id
    ]
    if real_status is not None:
        gates = [gate for gate in gates if gate["real_status"] == real_status]
    if rehearsal_status is not None:
        gates = [gate for gate in gates if gate["rehearsal_status"] == rehearsal_status]
    return {
        "catalogue_version": CATALOGUE_VERSION,
        "summary": catalogue_summary(),
        "gates": gates,
    }


@router.get("/gates/{gate_id}")
def promotion_gate_detail(
    gate_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """One gate with both track verdicts and what would make the real one pass."""
    authorize(
        context,
        action="v32:promotion-gates:read",
        resource_type="promotion-gate",
        resource_id=gate_id,
    )
    gate = GATES_BY_ID.get(gate_id)
    if gate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown gate: {gate_id}"
        )
    breakdown = score_breakdown(repository.evaluations)
    return {"definition": gate.model_dump(mode="json"), "evaluation": breakdown[gate_id]}


@router.get("/transitions")
def promotion_transitions(
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Per-transition, per-track status. Both tracks always present."""
    authorize(
        context,
        action="v32:promotion-transitions:read",
        resource_type="promotion-transitions",
        resource_id=as_of.isoformat(),
    )
    return {"transitions": transition_report(repository.evaluations)}


@router.get("/capabilities")
def promotion_capabilities(
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Every capability with its verdict, including the refused ones.

    Refusals are returned because a register of what is allowed, with refusals
    omitted, cannot be audited for whether the right things are refused.
    """
    authorize(
        context,
        action="v32:promotion-capabilities:read",
        resource_type="promotion-capabilities",
        resource_id=as_of.isoformat(),
    )
    return {"capabilities": capability_register(repository.decision(as_of))}


@router.get("/evidence")
def promotion_evidence(
    as_of: date = Query(...),
    gate_id: Optional[str] = Query(default=None),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Registered evidence and its envelopes."""
    authorize(
        context,
        action="v32:promotion-evidence:read",
        resource_type="promotion-evidence",
        resource_id=gate_id or "all",
    )
    items = [
        item.model_dump(mode="json")
        for item in repository.evidence()
        if gate_id is None or item.gate_id == gate_id
    ]
    return {
        "evidence": items,
        "envelopes": [item.model_dump(mode="json") for item in repository.envelopes()],
    }


@router.get("/signing")
def promotion_signing(
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Which signers actually ran, and the trust registry.

    Published so three listed signers cannot be read as three exercised ones.
    """
    authorize(
        context,
        action="v32:promotion-signing:read",
        resource_type="promotion-signing",
        resource_id=as_of.isoformat(),
    )
    return {
        "signers": signer_capability_report(),
        "trust_registry": repository.trust.as_document(),
    }


@router.get("/rehearsal-clock")
def promotion_rehearsal_clock(
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Simulated days and elapsed bank days, side by side.

    The second number is what keeps the first honest, so this route never
    returns one without the other.
    """
    authorize(
        context,
        action="v32:promotion-clock:read",
        resource_type="promotion-clock",
        resource_id=as_of.isoformat(),
    )
    return repository.clock().model_dump(mode="json")


@router.get("/events")
def promotion_events(
    as_of: date = Query(...),
    track: Optional[DecisionTrack] = Query(default=None),
    event_type: Optional[PromotionEventType] = Query(default=None),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """The promotion event stream, with per-track counts."""
    authorize(
        context,
        action="v32:promotion-events:read",
        resource_type="promotion-events",
        resource_id=as_of.isoformat(),
    )
    events = repository.events.list(track=track, event_type=event_type)
    return {
        "counts_by_type": repository.events.counts_by_type(),
        "counts_by_track": repository.events.counts_by_track(),
        "events": [item.model_dump(mode="json") for item in events],
    }


@router.get("/approvals")
def promotion_approvals(
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Four-eyes approvals recorded against promotions."""
    authorize(
        context,
        action="v32:promotion-approvals:read",
        resource_type="promotion-approvals",
        resource_id=as_of.isoformat(),
    )
    return {
        "approvals": [item.model_dump(mode="json") for item in repository.approvals()]
    }


@router.get("/decisions/{decision_id}")
def promotion_decision_detail(
    decision_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Resolve a DSSE-signed promotion decision by its stable identifier."""
    authorize(
        context,
        action="v32:promotion-decisions:read",
        resource_type="promotion-decision",
        resource_id=decision_id,
    )
    package = repository.signed_decision(as_of)
    decision = package["decision"]
    if decision["decision_id"] != decision_id:
        raise HTTPException(status_code=404, detail=f"unknown decision: {decision_id}")
    return package


@router.get("/rehearsals/{run_id}")
def promotion_rehearsal_detail(
    run_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v32:promotion-rehearsals:read",
        resource_type="promotion-rehearsal",
        resource_id=run_id,
    )
    if run_id == "v32-canonical-shadow-rehearsal":
        return rehearsal_report(as_of=as_of)
    run = _REHEARSAL_RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown rehearsal: {run_id}")
    return {**run, "incidents": _REHEARSAL_INCIDENTS.get(run_id, [])}


@router.get("/e3-sample-size-plan")
def promotion_e3_sample_size_plan(
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """The reproducible synthetic planning result, never an E3 observation."""
    authorize(
        context,
        action="v32:promotion-e3-plan:read",
        resource_type="promotion-simulation",
        resource_id=as_of.isoformat(),
    )
    from .laboratories.sample_size import plan_e3_readiness_sample_size

    return plan_e3_readiness_sample_size(as_of=as_of, replications=500)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


@router.post("/evaluations", status_code=status.HTTP_201_CREATED)
def record_evaluation(
    request: EvaluationRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Record a gate evaluation.

    The contract already refuses a synthetic real-track verdict; this adds the
    fixture-mode refusal, which is about *where* the write is happening rather
    than what it says.
    """
    key = _require_idempotency(idempotency_key)
    cached = _cached("evaluation", key)
    if cached is not None:
        return cached
    authorize(
        context,
        action="v32:promotion-evaluation:write",
        resource_type="promotion-evaluation",
        resource_id=request.evaluation.gate_id,
    )
    _guard_fixture(request.evaluation.track)
    try:
        recorded = repository.record_evaluation(request.evaluation)
    except FixtureModeError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return _remember("evaluation", key, recorded.model_dump(mode="json"))


@router.post("/approvals", status_code=status.HTTP_201_CREATED)
def submit_approval(
    request: ApprovalRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Submit a four-eyes promotion approval.

    Maker/checker separation is enforced by the ``PromotionApproval`` validator,
    so a self-approval fails at construction rather than being caught here.
    """
    key = _require_idempotency(idempotency_key)
    cached = _cached("approval", key)
    if cached is not None:
        return cached
    authorize(
        context,
        action="v32:promotion-approval:write",
        resource_type="promotion-approval",
        resource_id=request.approval.transition_id,
    )
    _guard_fixture(request.approval.track)
    try:
        recorded = repository.record_approval(request.approval)
    except (FixtureModeError, ApprovalBindingError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return _remember("approval", key, recorded.model_dump(mode="json"))


@router.post("/evidence", status_code=status.HTTP_201_CREATED)
def submit_promotion_evidence(
    request: EvidenceRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    key = _require_idempotency(idempotency_key)
    cached = _cached("evidence", key)
    if cached is not None:
        return cached
    authorize(
        context,
        action="v32:promotion-evidence:write",
        resource_type="promotion-evidence",
        resource_id=request.evidence.evidence_id,
    )
    if repository.fixture_mode and not is_synthetic(request.evidence.mode):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="fixture mode accepts rehearsal evidence only",
        )
    try:
        evidence = repository.register_evidence(request.evidence)
        envelope = repository.sign_evidence(evidence.evidence_id)
    except FixtureModeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return _remember(
        "evidence",
        key,
        {
            "evidence": evidence.model_dump(mode="json"),
            "envelope": envelope.model_dump(mode="json"),
            "effective_mode": envelope.mode.value,
        },
    )


@router.post("/decisions/evaluate")
def evaluate_promotion_decision(
    request: DecisionEvaluationRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    key = _require_idempotency(idempotency_key)
    cached = _cached("decision-evaluate", key)
    if cached is not None:
        return cached
    authorize(
        context,
        action="v32:promotion-decision:evaluate",
        resource_type="promotion-decision",
        resource_id=request.target_state.value if request.target_state else request.as_of.isoformat(),
    )
    package = repository.signed_decision(request.as_of)
    package["requested_target_state"] = (
        request.target_state.value if request.target_state else None
    )
    package["automatic_promotion"] = False
    return _remember("decision-evaluate", key, package)


@router.post("/decisions/{decision_id}/approvals", status_code=status.HTTP_201_CREATED)
def approve_promotion_decision(
    decision_id: str,
    request: ApprovalRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    current = repository.decision()
    if decision_id != current.decision_id:
        raise HTTPException(status_code=404, detail=f"unknown decision: {decision_id}")
    return submit_approval(request, idempotency_key, context)


@router.post("/transitions/{target_state}/requests", status_code=status.HTTP_202_ACCEPTED)
def request_promotion_transition(
    target_state: PromotionState,
    request: TransitionRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    key = _require_idempotency(idempotency_key)
    cached = _cached("transition-request", key)
    if cached is not None:
        return cached
    authorize(
        context,
        action="v32:promotion-transition:request",
        resource_type="promotion-transition",
        resource_id=target_state.value,
    )
    if target_state is not next_state(request.source_state) or not is_legal_transition(
        request.source_state, target_state
    ):
        raise HTTPException(status_code=409, detail="promotion states cannot be skipped")
    _guard_fixture(request.track)
    result = {
        "request_id": f"transition-request:{key}",
        "transition_id": make_transition_id(request.source_state, target_state),
        "track": request.track.value,
        "status": "PENDING_ACCOUNTABLE_APPROVAL",
        "automatic_promotion": False,
        "rationale": request.rationale,
    }
    return _remember("transition-request", key, result)


@router.post("/rehearsals", status_code=status.HTTP_201_CREATED)
def start_promotion_rehearsal(
    request: RehearsalRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    key = _require_idempotency(idempotency_key)
    cached = _cached("rehearsal", key)
    if cached is not None:
        return cached
    authorize(
        context,
        action="v32:promotion-rehearsal:write",
        resource_type="promotion-rehearsal",
        resource_id=request.scenario.scenario_id,
    )
    if not is_synthetic(request.scenario.mode):
        raise HTTPException(status_code=409, detail="rehearsals require a rehearsal-only mode")
    run_id = f"run:{request.scenario.scenario_id}"
    result = {
        "run_id": run_id,
        "scenario": request.scenario.model_dump(mode="json"),
        "track": DecisionTrack.REHEARSAL.value,
        "status": "REHEARSAL_RECORDED",
        "bank_authority_conferred": False,
    }
    _REHEARSAL_RUNS[run_id] = result
    _REHEARSAL_INCIDENTS.setdefault(run_id, [])
    return _remember("rehearsal", key, result)


@router.post("/rehearsals/{run_id}/incidents", status_code=status.HTTP_201_CREATED)
def inject_rehearsal_incident(
    run_id: str,
    request: IncidentRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    context: EntitlementContext = Depends(principal),
) -> dict:
    key = _require_idempotency(idempotency_key)
    cached = _cached("rehearsal-incident", key)
    if cached is not None:
        return cached
    authorize(
        context,
        action="v32:promotion-rehearsal:write",
        resource_type="promotion-rehearsal-incident",
        resource_id=run_id,
    )
    run = _REHEARSAL_RUNS.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown rehearsal: {run_id}")
    scenario_id = run["scenario"]["scenario_id"]
    if request.incident.scenario_id != scenario_id:
        raise HTTPException(status_code=409, detail="incident does not belong to rehearsal scenario")
    result = {
        "run_id": run_id,
        "incident": request.incident.model_dump(mode="json"),
        "real_track_affected": False,
        "rehearsal_counter_reset": request.incident.resets_rehearsal_counter,
    }
    _REHEARSAL_INCIDENTS.setdefault(run_id, []).append(result)
    return _remember("rehearsal-incident", key, result)


__all__ = ["router"]
