from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from wallet_twin_v2.api import authorize, principal
from wallet_twin_v2.contracts import EntitlementContext

from .repository import repository


router = APIRouter(prefix="/v3", tags=["V3 decision intelligence"])


@router.get("/decision-lab")
def decision_lab(
    as_of: date = Query(...), context: EntitlementContext = Depends(principal)
) -> dict:
    authorize(
        context,
        action="v3:decision-lab:read",
        resource_type="v3-portfolio",
        resource_id="decision-lab",
    )
    return repository.decision_lab(as_of, context.client_ids)


@router.get("/opportunities")
def opportunities(
    as_of: date = Query(...),
    client_id: Optional[str] = None,
    product: Optional[str] = None,
    limit: int = Query(100, ge=1, le=100),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v3:opportunities:read",
        resource_type="v3-portfolio",
        resource_id="decision-lab",
    )
    repository.check_as_of(as_of)
    values = repository.entitled_opportunities(context.client_ids)
    if client_id:
        values = [item for item in values if item.entity_id == client_id]
    if product:
        values = [item for item in values if item.product == product]
    return {
        "metadata": repository.metadata,
        "count": len(values),
        "items": [item.model_dump(mode="json") for item in values[:limit]],
        "release": repository.release,
    }


@router.get("/clients/{client_id}/latent-network")
def client_network(
    client_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v3:network:read",
        resource_type="client",
        resource_id=client_id,
        client_id=client_id,
    )
    return repository.client_network(client_id, as_of)


@router.get("/leakage")
def leakage(
    as_of: date = Query(...),
    limit: int = Query(20, ge=1, le=100),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(
        context,
        action="v3:leakage:read",
        resource_type="v3-portfolio",
        resource_id="leakage",
    )
    repository.check_as_of(as_of)
    values = sorted(
        repository.entitled_opportunities(context.client_ids),
        key=lambda item: (-item.leakage.alarm_probability, item.opportunity_id),
    )
    return {
        "measurement_status": "MODELLED_SIGNAL_NOT_CONFIRMED_LEAKAGE",
        "items": [item.leakage.model_dump(mode="json") for item in values[:limit]],
    }


@router.get("/action-portfolio")
def action_portfolio(
    as_of: date = Query(...), context: EntitlementContext = Depends(principal)
) -> dict:
    authorize(
        context,
        action="v3:portfolio:read",
        resource_type="v3-action-portfolio",
        resource_id="current",
    )
    repository.check_as_of(as_of)
    return repository.action_portfolio_projection(context.client_ids)


@router.get("/evidence-acquisition")
def evidence_acquisition(
    as_of: date = Query(...), context: EntitlementContext = Depends(principal)
) -> dict:
    authorize(
        context,
        action="v3:evidence-plan:read",
        resource_type="v3-evidence-plan",
        resource_id="current",
    )
    repository.check_as_of(as_of)
    return repository.evidence_acquisition_projection(context.client_ids)


@router.get("/opportunities/{opportunity_id}/brief")
def brief(
    opportunity_id: str,
    as_of: date = Query(...),
    context: EntitlementContext = Depends(principal),
) -> dict:
    item = repository.opportunity(opportunity_id, as_of)
    authorize(
        context,
        action="v3:brief:read",
        resource_type="opportunity",
        resource_id=opportunity_id,
        client_id=item.entity_id,
        product=item.product,
    )
    return repository.brief(opportunity_id, as_of)


@router.get("/models/validation")
def validation(context: EntitlementContext = Depends(principal)) -> dict:
    authorize(
        context,
        action="v3:model-validation:read",
        resource_type="v3-model",
        resource_id="suite",
    )
    return {
        "metadata": repository.metadata,
        "validation": repository.validation,
        "release": repository.release,
    }
