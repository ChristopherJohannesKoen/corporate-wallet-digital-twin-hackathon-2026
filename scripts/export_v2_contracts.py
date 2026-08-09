from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.api import app
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


CONTRACTS = ROOT / "contracts"
SCHEMAS = CONTRACTS / "jsonschema"
DASHBOARD_DATA = ROOT / "dashboard" / "app" / "data"


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
    }
    for name, model in models.items():
        write_json(SCHEMAS / f"{name}.schema.json", model.model_json_schema())
    write_json(CONTRACTS / "openapi.json", app.openapi())
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
    write_json(DASHBOARD_DATA / "shadow-fixture.json", payload)
    print(json.dumps({"schemas": len(models), "opportunities": len(repository.opportunities), "output": str(DASHBOARD_DATA)}))


if __name__ == "__main__":
    main()
