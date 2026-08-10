from __future__ import annotations

import json
import math
import re
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.contracts import (
    AccessEvaluationRequest,
    CalibrationObservation,
    CuratedMetadata,
    EntitlementContext,
    EventEnvelope,
    EvidenceFact,
    ExtractionCandidate,
    IngestionRecordRequest,
    NarrativeRequest,
    OpportunityView,
    PilotFeedbackRequest,
    PilotSessionRequest,
    RateCard,
    StartStopInterval,
    TimingRequest,
)
from wallet_twin_v2.repository import repository
from wallet_twin_v2.service_apps import workbench_bff_app
from wallet_twin_v3.contracts import (
    ChangePointSignal,
    EvidenceAcquisitionPlan,
    LeakageAlarm,
    ProductNeedEstimate,
    RobustActionPortfolio,
    ShadowWalletReconstruction,
    V3OpportunityView,
)
from wallet_twin_v3.repository import repository as v3_repository


CONTRACTS = ROOT / "contracts"
SCHEMAS = CONTRACTS / "jsonschema"
DASHBOARD_DATA = ROOT / "dashboard" / "app" / "data"
V3_OUTPUTS = ROOT / "outputs" / "v3"
LONG_DECIMAL = re.compile(r"^-?\d+\.\d{9,}$")


def canonical_dashboard_value(value: object) -> object:
    """Remove platform-only floating-point noise from the checked-in UI fixture."""
    if isinstance(value, dict):
        return {key: canonical_dashboard_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [canonical_dashboard_value(item) for item in value]
    if isinstance(value, float) and math.isfinite(value):
        if abs(value) < 0.0000001:
            return 0.0
        # Portfolio currency values are displayed at cent precision; ratios and
        # probabilities retain eight decimals. This removes BLAS/platform noise
        # without changing any decision-relevant value.
        return round(value, 2 if abs(value) >= 1_000 else 8)
    if isinstance(value, str) and LONG_DECIMAL.fullmatch(value):
        rounded = Decimal(value).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)
        return format(rounded, "f")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    models = {
        "curated-metadata": CuratedMetadata,
        "evidence-fact": EvidenceFact,
        "extraction-candidate": ExtractionCandidate,
        "calibration-observation": CalibrationObservation,
        "rate-card": RateCard,
        "opportunity-view": OpportunityView,
        "entitlement-context": EntitlementContext,
        "event-envelope": EventEnvelope,
        "start-stop-interval": StartStopInterval,
        "ingestion-record-request": IngestionRecordRequest,
        "timing-request": TimingRequest,
        "narrative-request": NarrativeRequest,
        "access-evaluation-request": AccessEvaluationRequest,
        "pilot-session-request": PilotSessionRequest,
        "pilot-feedback-request": PilotFeedbackRequest,
        "v3-shadow-wallet-reconstruction": ShadowWalletReconstruction,
        "v3-product-need-estimate": ProductNeedEstimate,
        "v3-change-point-signal": ChangePointSignal,
        "v3-leakage-alarm": LeakageAlarm,
        "v3-robust-action-portfolio": RobustActionPortfolio,
        "v3-evidence-acquisition-plan": EvidenceAcquisitionPlan,
        "v3-opportunity-view": V3OpportunityView,
    }
    for name, model in models.items():
        write_json(SCHEMAS / f"{name}.schema.json", model.model_json_schema())
    write_json(CONTRACTS / "openapi.json", workbench_bff_app.openapi())
    payload = {
        "metadata": repository.metadata,
        "opportunities": [item.model_dump(mode="json") for item in repository.opportunities],
        "clients": repository.clients,
        "facts": repository.facts,
        "sensitivity": repository.sensitivity,
        "legacy_sensitivity": repository.legacy_sensitivity,
        "evidence_coverage": repository.evidence_coverage,
        "benchmark_economics": repository.benchmark_economics,
        "offline_validation": repository.offline_validation,
        "genai_evaluation": repository.genai_evaluation,
        "genai_provider_status": repository.genai_provider_status,
        "shadow_replay": repository.shadow_replay,
        "production_candidate": repository.production_candidate,
        "public_evidence_qa": repository.public_evidence_qa,
        "trial_rehearsal": repository.trial_rehearsal,
        "operational_rehearsal": repository.operational_rehearsal,
        "release": repository.release,
    }
    write_json(DASHBOARD_DATA / "shadow-fixture.json", canonical_dashboard_value(payload))
    v3_payload = {
        "metadata": v3_repository.metadata,
        "opportunities": [item.model_dump(mode="json") for item in v3_repository.opportunities],
        "treasury_graphs": v3_repository.treasury_graphs,
        "action_portfolio": v3_repository.action_portfolio.model_dump(mode="json"),
        "evidence_acquisition": v3_repository.evidence_acquisition.model_dump(mode="json"),
        "public_sensors": v3_repository.public_sensors,
        "validation": v3_repository.validation,
        "release": v3_repository.release,
    }
    write_json(DASHBOARD_DATA / "v3-fixture.json", canonical_dashboard_value(v3_payload))
    canonical_v3 = canonical_dashboard_value(v3_payload)
    write_json(V3_OUTPUTS / "decision-lab.json", canonical_v3)
    write_json(
        V3_OUTPUTS / "validation.json",
        {
            "metadata": canonical_v3["metadata"],
            "validation": canonical_v3["validation"],
            "release": canonical_v3["release"],
        },
    )
    for action in v3_repository.action_portfolio.selected_actions:
        write_json(
            V3_OUTPUTS / "briefs" / f"{action.opportunity_id}.json",
            v3_repository.brief(action.opportunity_id, v3_repository.as_of),
        )
    print(json.dumps({
        "schemas": len(models),
        "substrate_opportunities": len(repository.opportunities),
        "v3_opportunities": len(v3_repository.opportunities),
        "dashboard_output": str(DASHBOARD_DATA),
        "canonical_v3_output": str(V3_OUTPUTS),
    }))


if __name__ == "__main__":
    main()
