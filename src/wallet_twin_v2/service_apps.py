"""Deployable service boundaries for the composed V3 microservice topology.

The reference build deliberately shares one Python distribution so contract and
control code cannot drift. Each EKS deployment selects one ASGI object below;
only routes owned by that service are registered in its OpenAPI document.
Service-owned persistence remains an adapter concern and cross-service database
access is prohibited by the deployment policies in ``infra``.
"""

from __future__ import annotations

from typing import Iterable

from fastapi import FastAPI
from fastapi.routing import APIRoute

from .api import app as canonical_app
from wallet_twin_v3.api import router as v3_router


SERVICE_ROUTES = {
    "ingestion": ("/v1/ingestion",),
    "evidence": ("/v1/evidence",),
    "economics": ("/v1/economics",),
    "wallet-model": ("/v1/clients", "/v1/models"),
    "timing": ("/v1/timing",),
    "recommendation": (
        "/v1/opportunities",
        "/v1/recommendations",
        "/v1/scenarios",
        "/v3",
    ),
    "experiment": ("/v1/outcomes", "/v1/events", "/v1/pilot"),
    "genai": ("/v1/genai",),
    "entitlement": ("/v1/access",),
    "workbench-bff": (
        "/v1/opportunities",
        "/v1/clients",
        "/v1/models",
        "/v1/sensitivity",
        "/v1/scenarios",
        "/v3",
    ),
}


def create_service_app(service_name: str, prefixes: Iterable[str]) -> FastAPI:
    service = FastAPI(
        title=f"Corporate Wallet Digital Twin V3 — {service_name}",
        version="3.0.0",
        docs_url=None,
        redoc_url=None,
    )

    @service.get("/health", tags=["operational"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": service_name, "version": "3.0.0"}

    @service.get("/ready", tags=["operational"])
    def ready() -> dict:
        from fastapi import HTTPException

        from .runtime_config import RuntimeConfig

        report = RuntimeConfig.from_env().validate()
        if not report["valid"]:
            raise HTTPException(status_code=503, detail=report)
        return report

    allowed = tuple(prefixes)
    for route in canonical_app.routes:
        if isinstance(route, APIRoute) and route.path != "/health" and route.path.startswith(allowed):
            service.router.routes.append(route)
    if "/v3" in allowed:
        for route in v3_router.routes:
            if isinstance(route, APIRoute):
                service.router.routes.append(route)
    return service


ingestion_app = create_service_app("ingestion", SERVICE_ROUTES["ingestion"])
evidence_app = create_service_app("evidence", SERVICE_ROUTES["evidence"])
economics_app = create_service_app("economics", SERVICE_ROUTES["economics"])
wallet_model_app = create_service_app("wallet-model", SERVICE_ROUTES["wallet-model"])
timing_app = create_service_app("timing", SERVICE_ROUTES["timing"])
recommendation_app = create_service_app("recommendation", SERVICE_ROUTES["recommendation"])
experiment_app = create_service_app("experiment", SERVICE_ROUTES["experiment"])
genai_app = create_service_app("genai", SERVICE_ROUTES["genai"])
entitlement_app = create_service_app("entitlement", SERVICE_ROUTES["entitlement"])
workbench_bff_app = create_service_app("workbench-bff", SERVICE_ROUTES["workbench-bff"])
