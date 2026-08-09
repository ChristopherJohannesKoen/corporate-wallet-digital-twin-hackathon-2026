"""Local-only identity and CRM doubles for contract and entitlement testing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field


app = FastAPI(title="Wallet Twin local integration doubles", version="1.0.0", docs_url=None, redoc_url=None)

LOCAL_IDENTITIES = {
    "local-owner-token": {
        "active": True,
        "user_id": "local-owner",
        "roles": ["RM", "EVIDENCE_REVIEWER"],
        "team": "shadow-team-01",
        "regions": ["ZA"],
        "client_ids": [f"E{index:02d}" for index in range(1, 21)],
        "products": ["Collections", "Payments", "Liquidity", "Cross-border FX", "Trade finance"],
        "mfa_authenticated": True,
        "environment": "SHADOW",
    },
    "local-denied-token": {
        "active": True,
        "user_id": "local-denied",
        "roles": ["RM"],
        "team": "unentitled-team",
        "regions": [],
        "client_ids": [],
        "products": [],
        "mfa_authenticated": True,
        "environment": "SHADOW",
    },
}


class CRMEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    recommendation_id: str
    event_type: Literal["EXPOSURE", "OPEN", "DISMISS", "ACTION", "OUTCOME"]
    occurred_at: datetime
    payload: Dict[str, str] = Field(default_factory=dict)


crm_events: List[CRMEvent] = []


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "LOCAL_MOCK_ONLY"}


@app.post("/mock/identity/introspect")
def introspect(authorization: str = Header(default="")) -> dict:
    token = authorization.removeprefix("Bearer ").strip()
    identity = LOCAL_IDENTITIES.get(token)
    if identity is None:
        return {"active": False}
    return identity


@app.post("/mock/crm/events", status_code=202)
def record_crm_event(event: CRMEvent, authorization: str = Header(default="")) -> dict:
    identity = introspect(authorization)
    if not identity.get("active"):
        raise HTTPException(status_code=401, detail="mock identity required")
    if any(existing.event_id == event.event_id for existing in crm_events):
        raise HTTPException(status_code=409, detail="duplicate event")
    crm_events.append(event)
    return {"accepted": True, "received_at": datetime.now(timezone.utc).isoformat()}


@app.get("/mock/crm/events")
def list_crm_events(authorization: str = Header(default="")) -> List[CRMEvent]:
    identity = introspect(authorization)
    if not identity.get("active"):
        raise HTTPException(status_code=401, detail="mock identity required")
    return list(crm_events)
