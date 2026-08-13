"""Deployable service boundaries for the composed V3.1 microservice topology.

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
from wallet_twin_v31.api import router as v31_router
from wallet_twin_v32.api import router as v32_router
SERVICE_ROUTES = {
    "ingestion": ("/v1/ingestion",),
    "evidence": ("/v1/evidence",),
    "economics": ("/v1/economics",),
    "wallet-model": ("/v1/clients", "/v1/models"),
    "business-twin": (
        "/v3/decision-twin",
        "/v3/clients",
        "/v3/funding-routes",
        "/v3/models/v31-validation",
    ),
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
    # The twelfth service. Promotion owns its own Postgres schema and outbox
    # (infra/sql/002_promotion_schemas.sql) and never reads another service's
    # tables. The workbench-bff also surfaces these routes, which is what a BFF
    # is for; the promotion deployment is the one that owns the writes.
    "promotion": ("/v3/promotion",),
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
        title=f"Corporate Wallet Digital Twin V3.1.1 — {service_name}",
        version="3.1.1",
        docs_url=None,
        redoc_url=None,
    )

    @service.get("/health", tags=["operational"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": service_name, "version": "3.1.1"}

    @service.get("/ready", tags=["operational"])
    def ready() -> dict:
        from fastapi import HTTPException

        from .runtime_config import RuntimeConfig

        report = RuntimeConfig.from_env().validate()
        if not report["valid"]:
            raise HTTPException(status_code=503, detail=report)
        return report

    allowed = tuple(prefixes)
    registered = {route.path for route in service.routes if isinstance(route, APIRoute)}
    for route in canonical_app.routes:
        if isinstance(route, APIRoute) and route.path != "/health" and route.path.startswith(allowed):
            service.router.routes.append(route)
            registered.add(route.path)
    # The composed API imports additive routers at the end of its module.  An
    # explicit owned-router pass makes service construction insensitive to
    # Python's circular-import order and keeps duplicate paths out of OpenAPI.
    if "/v3" in allowed or any(prefix.startswith("/v3") for prefix in allowed):
        for owned_router in (v3_router, v31_router, v32_router):
            for route in owned_router.routes:
                if (
                    isinstance(route, APIRoute)
                    and route.path.startswith(allowed)
                    and route.path not in registered
                ):
                    service.router.routes.append(route)
                    registered.add(route.path)
    return service


ingestion_app = create_service_app("ingestion", SERVICE_ROUTES["ingestion"])
evidence_app = create_service_app("evidence", SERVICE_ROUTES["evidence"])
economics_app = create_service_app("economics", SERVICE_ROUTES["economics"])
wallet_model_app = create_service_app("wallet-model", SERVICE_ROUTES["wallet-model"])
business_twin_app = create_service_app("business-twin", SERVICE_ROUTES["business-twin"])
timing_app = create_service_app("timing", SERVICE_ROUTES["timing"])
recommendation_app = create_service_app("recommendation", SERVICE_ROUTES["recommendation"])
experiment_app = create_service_app("experiment", SERVICE_ROUTES["experiment"])
genai_app = create_service_app("genai", SERVICE_ROUTES["genai"])
entitlement_app = create_service_app("entitlement", SERVICE_ROUTES["entitlement"])
promotion_app = create_service_app("promotion", SERVICE_ROUTES["promotion"])
workbench_bff_app = create_service_app("workbench-bff", SERVICE_ROUTES["workbench-bff"])
