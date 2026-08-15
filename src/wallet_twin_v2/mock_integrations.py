"""Local-only identity and CRM doubles for contract and entitlement testing."""

from __future__ import annotations

from datetime import datetime, timezone
from datetime import date
import hashlib
from typing import Dict, List, Literal

from fastapi import FastAPI, Header, HTTPException, Response
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


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Minimal Prometheus exposition for the local bank-shaped harness."""
    payload = (
        "# HELP wallet_twin_mock_up Local integration-double availability.\n"
        "# TYPE wallet_twin_mock_up gauge\n"
        "wallet_twin_mock_up 1\n"
    )
    return Response(content=payload, media_type="text/plain; version=0.0.4")


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


@app.get("/mock/feeds/daily")
def synthetic_daily_feed(as_of: date) -> dict:
    """Deterministic aggregate feed for the bank-shaped shadow lab.

    No supplied transaction row is returned. Values are independently generated
    from stable identifiers so reconciliation and replay can be exercised.
    """
    rows = []
    products = ("Collections", "Payments", "Liquidity", "Cross-border FX", "Trade finance")
    for client_index in range(1, 21):
        for product_index, product in enumerate(products, start=1):
            seed = f"v32-feed:{as_of.isoformat()}:{client_index}:{product_index}"
            digest = hashlib.sha256(seed.encode()).hexdigest()
            amount = 1_000_000 + int(digest[:10], 16) % 250_000_000
            rows.append(
                {
                    "client_id": f"E{client_index:02d}",
                    "product": product,
                    "as_of": as_of.isoformat(),
                    "amount_zar": amount,
                    "source_mode": "SYNTHETIC_REHEARSAL",
                    "row_hash": digest,
                }
            )
    total = sum(row["amount_zar"] for row in rows)
    manifest = hashlib.sha256(
        "|".join(row["row_hash"] for row in rows).encode()
    ).hexdigest()
    return {
        "feed_version": "v32-synthetic-bank-feed-1.0.0",
        "as_of": as_of.isoformat(),
        "source_mode": "SYNTHETIC_REHEARSAL",
        "rows": rows,
        "row_count": len(rows),
        "control_total_zar": total,
        "manifest_sha256": manifest,
    }
