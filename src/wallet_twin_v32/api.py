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
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from wallet_twin_v2.api import authorize, principal
from wallet_twin_v2.contracts import EntitlementContext, StrictModel

from .catalogue import CATALOGUE_VERSION, GATES_BY_ID, catalogue_summary
from .contracts import GateEvaluation, PromotionApproval
from .engine import capability_register, transition_report
from .events import PromotionEventType
from .modes import DecisionTrack
from .repository import FixtureModeError, repository
from .scoring import score_breakdown
from .signers import signer_capability_report
from .states import TRANSITION_IDS

router = APIRouter(prefix="/v3/promotion", tags=["V3.2 promotion readiness"])


def _require_idempotency(key: Optional[str]) -> str:
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required for mutating requests",
        )
    return key


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
    context: EntitlementContext = Depends(principal),
) -> dict:
    """Everything the workbench renders, in one call."""
    authorize(
        context,
        action="v32:promotion-readiness:read",
        resource_type="promotion-readiness",
        resource_id=as_of.isoformat(),
    )
    return repository.readiness()


@router.get("/gates")
def promotion_gates(
    as_of: date = Query(...),
    transition_id: Optional[str] = Query(default=None),
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
    gates = [
        gate.model_dump(mode="json")
        for gate in GATES_BY_ID.values()
        if transition_id is None or gate.transition_id == transition_id
    ]
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
    _require_idempotency(idempotency_key)
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
    return recorded.model_dump(mode="json")


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
    _require_idempotency(idempotency_key)
    authorize(
        context,
        action="v32:promotion-approval:write",
        resource_type="promotion-approval",
        resource_id=request.approval.transition_id,
    )
    _guard_fixture(request.approval.track)
    try:
        recorded = repository.record_approval(request.approval)
    except FixtureModeError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    return recorded.model_dump(mode="json")


__all__ = ["router"]
