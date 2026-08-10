from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import date
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse

from .contracts import (
    AccessEvaluationRequest,
    ApprovalStatus,
    DeploymentEnvironment,
    EntitlementContext,
    EventEnvelope,
    EventType,
    ExtractionCandidate,
    FactReviewRequest,
    IngestionRecordRequest,
    InteractionRequest,
    NarrativeRequest,
    OutcomeRequest,
    PilotFeedbackRequest,
    PilotSessionRequest,
    ScenarioRequest,
    TimingRequest,
)
from .economics import EconomicsService
from .entitlements import EntitlementService
from .events import EventStore, new_event_id
from .evidence import EvidenceRegistry, EvidenceValidationError
from .genai_gateway import ProviderGateway
from .experiment_analysis import PilotStore, preregistration_manifest
from .release_gates import ReleaseMetrics, ShadowReleaseGate
from .repository import repository
from .runtime_config import RuntimeConfig
from .timing import TimingService


app = FastAPI(
    title="Corporate Wallet Digital Twin V3",
    version="3.0.0",
    description="Private, entitlement-aware latent-wallet reconstruction and decision-support API",
    docs_url="/internal/docs",
    redoc_url=None,
)
entitlements = EntitlementService()
economics = EconomicsService()
events = EventStore()
evidence_registry = EvidenceRegistry()
genai = ProviderGateway()
release_gate = ShadowReleaseGate()
timing_service = TimingService()
pilot_store = PilotStore()
runtime_config = RuntimeConfig.from_env()


def principal(
    x_user_id: Optional[str] = Header(default=None),
    x_user_roles: Optional[str] = Header(default=None),
    x_user_team: Optional[str] = Header(default=None),
    x_user_clients: Optional[str] = Header(default=None),
    x_user_products: Optional[str] = Header(default=None),
) -> EntitlementContext:
    mode = os.getenv("WALLET_DEPLOYMENT_MODE", "FIXTURE").upper()
    environment = DeploymentEnvironment(mode) if mode in DeploymentEnvironment.__members__ else DeploymentEnvironment.FIXTURE
    if not x_user_id:
        if environment != DeploymentEnvironment.FIXTURE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bank identity required")
        return EntitlementContext(
            user_id="demo-validator",
            roles=["SHADOW_OPERATOR", "MODEL_VALIDATOR", "EVIDENCE_REVIEWER", "PRODUCT_FINANCE"],
            team="demo-model-risk",
            regions=["*"],
            client_ids=["*"],
            products=["*"],
            environment=environment,
        )
    return EntitlementContext(
        user_id=x_user_id,
        roles=[item.strip() for item in (x_user_roles or "").split(",") if item.strip()],
        team=x_user_team or "unknown",
        regions=["*"],
        client_ids=[item.strip() for item in (x_user_clients or "").split(",") if item.strip()],
        products=[item.strip() for item in (x_user_products or "").split(",") if item.strip()],
        environment=environment,
    )


def authorize(
    context: EntitlementContext,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    client_id: Optional[str] = None,
    product: Optional[str] = None,
    sensitive_economics: bool = False,
) -> None:
    decision = entitlements.authorize(
        context=context,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        client_id=client_id,
        product=product,
        sensitive_economics=sensitive_economics,
        shadow_only=True,
    )
    events.append(
        EventEnvelope(
            event_id=new_event_id(),
            event_type=EventType.ACCESS_DECISION_LOGGED,
            entity_id=client_id,
            product=product,
            entitlement_context=context,
            reason_codes=decision.reason_codes,
            payload={"allowed": decision.allowed, "action": action, "resource_type": resource_type, "resource_id": resource_id},
        )
    )
    if not decision.allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"reason_codes": decision.reason_codes})


@app.exception_handler(KeyError)
async def key_error_handler(_, exc: KeyError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": app.version, "mode": repository.metadata["deployment_mode"]}


@app.get("/ready")
def readiness() -> JSONResponse:
    report = runtime_config.validate()
    return JSONResponse(status_code=200 if report["valid"] else 503, content=report)


@app.post("/v1/ingestion/records", status_code=202)
def validate_ingestion_record(
    request: IngestionRecordRequest,
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(context, action="ingestion:submit", resource_type="source-record", resource_id=request.record_id)
    reasons = [f"MISSING_REQUIRED_FIELD:{field}" for field in request.required_fields if request.payload.get(field) is None]
    canonical = json.dumps(request.payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != request.source_hash.lower():
        reasons.append("SOURCE_HASH_MISMATCH")
    if request.event_time.date() > request.as_of:
        reasons.append("FUTURE_EVENT_TIME")
    return {
        "record_id": request.record_id,
        "status": "QUARANTINED" if reasons else "ACCEPTED",
        "reason_codes": reasons,
        "contract_version": request.contract_version,
        "persisted": False,
    }


@app.get("/v1/opportunities")
def list_opportunities(
    as_of: date = Query(...),
    product: Optional[str] = None,
    client_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(context, action="opportunities:list", resource_type="portfolio", resource_id="shadow")
    values = repository.list_opportunities(as_of)
    values = [item for item in values if "*" in context.client_ids or item.entity_id in context.client_ids]
    if context.products and "*" not in context.products:
        values = [item for item in values if item.product in context.products]
    if product:
        values = [item for item in values if item.product == product]
    if client_id:
        values = [item for item in values if item.entity_id == client_id]
    total = len(values)
    page = values[offset:offset + limit]
    return {
        "metadata": repository.metadata,
        "count": total,
        "returned": len(page),
        "limit": limit,
        "offset": offset,
        "items": [item.model_dump(mode="json") for item in page],
        "evidence_coverage": repository.evidence_coverage,
        "release": repository.release,
    }


@app.get("/v1/clients/{client_id}/twin")
def client_twin(client_id: str, as_of: date = Query(...), context: EntitlementContext = Depends(principal)) -> dict:
    authorize(context, action="client-twin:read", resource_type="client", resource_id=client_id, client_id=client_id)
    client = repository.client(client_id, as_of)
    opportunities = [item for item in repository.list_opportunities(as_of) if item.entity_id == client_id]
    return {
        "client": client,
        "opportunities": [item.model_dump(mode="json") for item in opportunities],
        "recommendations_visible_to_rm": False,
        "shadow_notice": repository.metadata["watermark"],
    }


@app.get("/v1/opportunities/{opportunity_id}/explanation")
def explanation(opportunity_id: str, as_of: date = Query(...), context: EntitlementContext = Depends(principal)) -> dict:
    opportunity = repository.opportunity(opportunity_id, as_of)
    authorize(
        context,
        action="opportunity:explain",
        resource_type="opportunity",
        resource_id=opportunity_id,
        client_id=opportunity.entity_id,
        product=opportunity.product,
    )
    fact_payload = [repository.facts[fact_id] for fact_id in opportunity.evidence_fact_ids if fact_id in repository.facts]
    narrative, mode = genai.generate(
        opportunity,
        {fact["fact_id"]: f"{fact['source_title']} p.{fact['page']}" for fact in fact_payload},
        context.user_id,
    )
    return {
        "opportunity": opportunity.model_dump(mode="json"),
        "layers": {
            "observed": opportunity.observed_activity.model_dump(mode="json"),
            "identified_bound": opportunity.identification_bounds.model_dump(mode="json"),
            "posterior": opportunity.posterior_wallet.model_dump(mode="json"),
            "commercial_scenario": opportunity.commercial.model_dump(mode="json"),
            "causal": None,
        },
        "facts": fact_payload,
        "narrative": narrative.model_dump(mode="json"),
        "narrative_mode": mode,
        "missing_evidence": [item for item in [
            "E3 multibank observation" if opportunity.evidence_tier.value in {"E0", "E1", "E2"} else None,
            "approved bank economics" if opportunity.commercial.status.value in {"SIMULATED", "BLOCKED"} else None,
            "causal outcome history",
        ] if item is not None],
    }


@app.post("/v1/scenarios/evaluate")
def evaluate_scenario(request: ScenarioRequest, context: EntitlementContext = Depends(principal)) -> dict:
    opportunity = repository.opportunity(request.opportunity_id, request.as_of)
    authorize(
        context,
        action="scenario:evaluate",
        resource_type="opportunity",
        resource_id=request.opportunity_id,
        client_id=opportunity.entity_id,
        product=opportunity.product,
        sensitive_economics=True,
    )
    result = economics.evaluate(
        as_of=request.as_of,
        environment=context.environment,
        rate_card=repository.rate_cards.get(opportunity.product),
        observed_activity=float(opportunity.observed_activity.normalized_amount),
        wallet_median=opportunity.posterior_wallet.median,
        current_share=opportunity.share_interval.median,
        target_share=request.target_share,
        capacity=request.capacity,
    )
    return result.model_dump(mode="json")


@app.post("/v1/recommendations/{recommendation_id}/interactions")
def record_interaction(
    recommendation_id: str,
    request: InteractionRequest,
    context: EntitlementContext = Depends(principal),
) -> dict:
    allowed_types = {
        EventType.RECOMMENDATION_DISPLAYED,
        EventType.RECOMMENDATION_OPENED,
        EventType.RECOMMENDATION_DISMISSED,
        EventType.BANKER_ACTION_RECORDED,
        EventType.PIPELINE_MILESTONE_RECORDED,
    }
    if request.interaction_type not in allowed_types:
        raise HTTPException(status_code=422, detail="invalid interaction event type")
    opportunity = repository.opportunity(recommendation_id, repository.as_of)
    authorize(
        context,
        action="interaction:record",
        resource_type="recommendation",
        resource_id=recommendation_id,
        client_id=opportunity.entity_id,
        product=opportunity.product,
    )
    event = events.append(
        EventEnvelope(
            event_id=new_event_id(),
            event_type=request.interaction_type,
            occurred_at=request.occurred_at,
            entity_id=opportunity.entity_id,
            product=opportunity.product,
            recommendation_id=recommendation_id,
            rm_id=context.user_id,
            team_id=context.team,
            as_of=repository.as_of,
            evidence_tier=opportunity.evidence_tier,
            rank=opportunity.rank,
            reason_codes=[request.reason_code] if request.reason_code else [],
            artifacts=opportunity.artifacts,
            entitlement_context=context,
            payload=request.payload,
        )
    )
    return event.model_dump(mode="json")


@app.post("/v1/outcomes")
def record_outcome(request: OutcomeRequest, context: EntitlementContext = Depends(principal)) -> dict:
    authorize(
        context,
        action="outcome:record",
        resource_type="recommendation",
        resource_id=request.recommendation_id,
        client_id=request.entity_id,
        product=request.product,
    )
    event = events.append(
        EventEnvelope(
            event_id=new_event_id(),
            event_type=EventType.OUTCOME_RECORDED,
            occurred_at=request.outcome_at,
            entity_id=request.entity_id,
            product=request.product,
            recommendation_id=request.recommendation_id,
            rm_id=context.user_id,
            team_id=context.team,
            as_of=repository.as_of,
            entitlement_context=context,
            censor_date=request.censor_date,
            payload=request.model_dump(mode="json"),
        )
    )
    return event.model_dump(mode="json")


@app.post("/v1/pilot/sessions", status_code=201)
def start_pilot_session(
    request: PilotSessionRequest,
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(context, action="pilot:session:start", resource_type="rm-pilot", resource_id=context.user_id)
    if "PILOT_RM" not in context.roles and context.environment != DeploymentEnvironment.FIXTURE:
        raise HTTPException(status_code=403, detail="PILOT_RM role required")
    return pilot_store.start(
        context.user_id,
        context.team,
        request.task_ids,
        request.started_at,
        consent_reference=request.consent_reference,
        real_participant=context.environment in {DeploymentEnvironment.PILOT, DeploymentEnvironment.PRODUCTION},
    )


@app.post("/v1/pilot/sessions/{session_id}/feedback", status_code=201)
def record_pilot_feedback(
    session_id: str,
    request: PilotFeedbackRequest,
    context: EntitlementContext = Depends(principal),
) -> dict:
    authorize(context, action="pilot:feedback:record", resource_type="rm-pilot-session", resource_id=session_id)
    session = pilot_store.sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="pilot session not found")
    if session["rm_id"] != context.user_id and "PLATFORM_ADMIN" not in context.roles:
        raise HTTPException(status_code=403, detail="pilot session owner required")
    return pilot_store.record_feedback(session_id, request.model_dump(mode="json"))


@app.get("/v1/pilot/readiness")
def pilot_readiness(context: EntitlementContext = Depends(principal)) -> dict:
    authorize(context, action="pilot:readiness:read", resource_type="rm-pilot", resource_id="readiness")
    return {
        "readiness": pilot_store.readiness(),
        "preregistration": preregistration_manifest(),
        "recommendations_visible_to_rm": context.environment in {DeploymentEnvironment.PILOT, DeploymentEnvironment.PRODUCTION},
        "automated_customer_actions": False,
    }


@app.post("/v1/evidence/candidates", status_code=201)
def submit_candidate(candidate: ExtractionCandidate, context: EntitlementContext = Depends(principal)) -> dict:
    authorize(
        context,
        action="evidence:submit",
        resource_type="evidence-candidate",
        resource_id=candidate.candidate_id,
        client_id=candidate.entity_id,
    )
    try:
        state = evidence_registry.submit(candidate, submitted_by=context.user_id, as_of=repository.as_of)
    except EvidenceValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"candidate_id": candidate.candidate_id, "status": state.status.value, "review_count": 0}


@app.post("/v1/evidence/{fact_id}/reviews")
def review_candidate(fact_id: str, request: FactReviewRequest, context: EntitlementContext = Depends(principal)) -> dict:
    authorize(
        context,
        action="evidence:approve",
        resource_type="evidence-candidate",
        resource_id=fact_id,
    )
    if request.reviewer_id != context.user_id:
        raise HTTPException(status_code=403, detail="reviewer_id must match authenticated user")
    try:
        state = evidence_registry.review(fact_id, request)
    except (EvidenceValidationError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"candidate_id": fact_id, "status": state.status.value, "review_count": len(state.reviews)}


@app.get("/v1/models/{model_id}/validation")
def model_validation(model_id: str, context: EntitlementContext = Depends(principal)) -> dict:
    authorize(context, action="model:validation:read", resource_type="model", resource_id=model_id)
    metrics = ReleaseMetrics(
        point_in_time_violations=0,
        critical_reconciliation_rate=1.0,
        interval_coverage_90=0.0,
        crps_improvement=0.0,
        production_economics_approved_rate=0.0,
        genai_schema_compliance=1.0,
        genai_critical_fact_accuracy=1.0,
        genai_candidate_precision=0.0,
        genai_abstention_accuracy=0.0,
        genai_numeric_preservation=1.0,
        genai_unsupported_critical_claims=0,
        prompt_injection_successes=0,
        entitlement_negative_test_pass_rate=1.0,
        unresolved_high_critical_vulnerabilities=1,
        availability=0.0,
        p95_read_latency_ms=0.0,
        event_latency_seconds=0.0,
        refresh_completion_hour_sast=0.0,
        unresolved_sev1_sev2=0,
        consecutive_shadow_days=0,
    )
    results = release_gate.evaluate(metrics)
    return {
        "model_id": model_id,
        "status": "NOT_PROMOTABLE",
        "promotable": release_gate.promotable(results),
        "gates": [result.model_dump(mode="json") for result in results],
        "reason": "Empirical calibration, approved bank economics, operating history and golden-set volumes are unavailable.",
    }


@app.get("/v1/economics/rate-cards/{product}")
def rate_card(product: str, as_of: date = Query(...), context: EntitlementContext = Depends(principal)) -> dict:
    authorize(
        context,
        action="economics:rate-card:read",
        resource_type="rate-card",
        resource_id=product,
        product=product,
        sensitive_economics=True,
    )
    repository._check_as_of(as_of)
    card = repository.rate_cards[product]
    return card.model_dump(mode="json")


@app.get("/v1/economics/benchmark-packs")
def benchmark_economics(as_of: date = Query(...), context: EntitlementContext = Depends(principal)) -> dict:
    authorize(context, action="economics:benchmark:read", resource_type="benchmark-registry", resource_id="e0-packs")
    repository._check_as_of(as_of)
    return repository.benchmark_economics


@app.get("/v1/sensitivity")
def sensitivity(as_of: date = Query(...), context: EntitlementContext = Depends(principal)) -> dict:
    authorize(context, action="sensitivity:read", resource_type="portfolio", resource_id="shadow")
    repository._check_as_of(as_of)
    return {
        "global": repository.sensitivity,
        "legacy_grid": repository.legacy_sensitivity,
        "benchmark_economics": repository.benchmark_economics,
        "offline_validation": repository.offline_validation,
        "genai_evaluation": repository.genai_evaluation,
        "genai_provider_status": repository.genai_provider_status,
        "shadow_replay": repository.shadow_replay,
        "production_candidate": repository.production_candidate,
        "public_evidence_qa": repository.public_evidence_qa,
        "trial_rehearsal": repository.trial_rehearsal,
        "operational_rehearsal": repository.operational_rehearsal,
        "client_demo_data": repository.client_demo_data,
        "client_demo_scorecard": repository.client_demo_scorecard,
        "production_target": repository.production_target,
    }


@app.get("/v1/models/offline-validation")
def offline_validation(as_of: date = Query(...), context: EntitlementContext = Depends(principal)) -> dict:
    authorize(context, action="model:validation:read", resource_type="model", resource_id="offline-lab")
    repository._check_as_of(as_of)
    return repository.offline_validation


@app.get("/v1/genai/status")
def genai_status(context: EntitlementContext = Depends(principal)) -> dict:
    authorize(context, action="genai:status:read", resource_type="genai-provider", resource_id="gateway")
    return {
        "provider_status": repository.genai_provider_status,
        "golden_evaluation": repository.genai_evaluation,
        "production_release_allowed": False,
    }


@app.post("/v1/timing/predict")
def timing_prediction(request: TimingRequest, context: EntitlementContext = Depends(principal)) -> dict:
    authorize(
        context,
        action="timing:predict",
        resource_type="client-product",
        resource_id=f"{request.entity_id}:{request.product}",
        client_id=request.entity_id,
        product=request.product,
    )
    repository._check_as_of(request.as_of)
    prediction = timing_service.predict_baseline(
        as_of=request.as_of,
        event_name=request.event_name,
        seasonal_ratio=request.seasonal_ratio,
        maturity_days=request.maturity_days,
        recurrence=request.recurrence,
    )
    return prediction.model_dump(mode="json")


@app.post("/v1/genai/narratives")
def generate_narrative(request: NarrativeRequest, context: EntitlementContext = Depends(principal)) -> dict:
    opportunity = repository.opportunity(request.opportunity_id, request.as_of)
    authorize(
        context,
        action="genai:narrate",
        resource_type="opportunity",
        resource_id=request.opportunity_id,
        client_id=opportunity.entity_id,
        product=opportunity.product,
    )
    fact_payload = [repository.facts[fact_id] for fact_id in opportunity.evidence_fact_ids if fact_id in repository.facts]
    narrative, mode = genai.generate(
        opportunity,
        {fact["fact_id"]: f"{fact['source_title']} p.{fact['page']}" for fact in fact_payload},
        context.user_id,
    )
    return {"mode": mode, "published": False, "narrative": narrative.model_dump(mode="json")}


@app.post("/v1/access/evaluate")
def evaluate_access(request: AccessEvaluationRequest, context: EntitlementContext = Depends(principal)) -> dict:
    decision = entitlements.authorize(
        context=context,
        action=request.action,
        resource_type=request.resource_type,
        resource_id=request.resource_id,
        client_id=request.client_id,
        product=request.product,
        sensitive_economics=request.sensitive_economics,
        shadow_only=True,
    )
    events.append(
        EventEnvelope(
            event_id=new_event_id(),
            event_type=EventType.ACCESS_DECISION_LOGGED,
            entity_id=request.client_id,
            product=request.product,
            entitlement_context=context,
            reason_codes=decision.reason_codes,
            payload={"allowed": decision.allowed, "action": request.action, "resource_id": request.resource_id},
        )
    )
    return decision.model_dump(mode="json")


@app.get("/v1/events")
def list_events(context: EntitlementContext = Depends(principal)) -> dict:
    authorize(context, action="events:read", resource_type="event-log", resource_id="shadow")
    return {"count": len(events.list()), "items": [event.model_dump(mode="json") for event in events.list()]}


# V3 is an additive decision-intelligence layer.  Including its router here
# preserves every governed V1/V2 endpoint while exposing the new latent-network,
# leakage, portfolio and evidence-acquisition surfaces from one internal API.
from wallet_twin_v3.api import router as v3_router  # noqa: E402

app.include_router(v3_router)
