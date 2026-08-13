"""The promotion service: routes, events, persistence and the topic wiring.

Two classes of test here. The first exercises the twelve routes and their
guards. The second checks that the *infrastructure* agrees with the code —
specifically the outbox CHECK constraint and the broker topic list, both of
which reject a new topic silently until widened, and both of which fail at
insert time in production rather than at build time.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wallet_twin_v2.api import app
from wallet_twin_v2.service_apps import SERVICE_ROUTES, promotion_app
from wallet_twin_v32.contracts import GateEvaluation, GateOutcome
from wallet_twin_v32.events import (
    PROMOTION_EVENT_TYPES,
    REHEARSAL_ONLY_EVENTS,
    PromotionEventStore,
    PromotionEventType,
    build_promotion_event,
    declared_topics,
)
from wallet_twin_v32.modes import DecisionTrack, PromotionEvidenceMode
from wallet_twin_v32.repository import (
    FIXTURE_AS_OF,
    FIXTURE_GENERATED_AT,
    FixtureModeError,
    PromotionRepository,
    repository,
)

ROOT = Path(__file__).resolve().parents[1]
AS_OF = FIXTURE_AS_OF.isoformat()
SYNTHETIC = PromotionEvidenceMode.SYNTHETIC_REHEARSAL
ATTESTED = PromotionEvidenceMode.BANK_ATTESTED

READER = {
    "X-User-Id": "shadow-operator-1",
    "X-User-Roles": "SHADOW_OPERATOR",
    "X-User-Clients": "*",
    "X-User-Products": "*",
}
#: A relationship manager: entitled to read the promotion position, not to
#: decide it.
RM = {**READER, "X-User-Id": "pilot-rm-1", "X-User-Roles": "PILOT_RM"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# --------------------------------------------------------------------------
# Topic wiring — the trap that fails at insert time in production
# --------------------------------------------------------------------------


def test_the_outbox_check_constraint_admits_the_promotion_topic() -> None:
    """A topic the code emits and the CHECK rejects fails at INSERT, in
    production, with no earlier signal."""
    sql = (ROOT / "infra" / "sql" / "001_operational_schemas.sql").read_text(
        encoding="utf-8"
    )
    for topic in declared_topics():
        assert f"'{topic}'" in sql, f"outbox CHECK does not admit {topic}"


def test_the_broker_topic_list_declares_the_promotion_topic() -> None:
    topics = (ROOT / "infra" / "msk" / "topics.yaml").read_text(encoding="utf-8")
    for topic in declared_topics():
        assert topic in topics, f"topics.yaml does not declare {topic}"


def test_the_promotion_schema_exists_and_is_append_only() -> None:
    sql = (ROOT / "infra" / "sql" / "002_promotion_schemas.sql").read_text(
        encoding="utf-8"
    )
    assert "CREATE SCHEMA IF NOT EXISTS promotion" in sql
    assert "BEFORE UPDATE OR DELETE" in sql
    assert "refuse_mutation" in sql


def test_the_database_restates_the_separation_invariant() -> None:
    """Python refuses a synthetic real-track verdict, but a direct INSERT would
    not go through Python."""
    sql = (ROOT / "infra" / "sql" / "002_promotion_schemas.sql").read_text(
        encoding="utf-8"
    )
    assert "synthetic_evidence_cannot_support_a_real_verdict" in sql
    assert "a_rehearsal_records_no_bank_days" in sql
    assert "four_eyes_submitter_cannot_review" in sql
    assert "rehearsal_domain_cannot_sign_real_evidence" in sql


def test_the_decision_table_stores_no_composite_score() -> None:
    sql = (ROOT / "infra" / "sql" / "002_promotion_schemas.sql").read_text(
        encoding="utf-8"
    )
    assert "promotion_machinery_readiness" in sql
    assert "bank_evidence_readiness" in sql
    for forbidden in ("overall_readiness", "promotability", "composite_score"):
        assert f"{forbidden} double" not in sql


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------


def test_there_are_twelve_promotion_event_types() -> None:
    assert len(PROMOTION_EVENT_TYPES) == 12


def test_a_rehearsal_only_event_cannot_be_emitted_on_the_real_track() -> None:
    for event_type in REHEARSAL_ONLY_EVENTS:
        with pytest.raises(ValueError, match="did not happen at the bank"):
            build_promotion_event(event_type, track=DecisionTrack.REAL)


def test_a_real_track_event_cannot_carry_synthetic_evidence() -> None:
    with pytest.raises(ValueError, match="cannot carry SYNTHETIC_REHEARSAL"):
        build_promotion_event(
            PromotionEventType.GATE_EVALUATED,
            track=DecisionTrack.REAL,
            evidence_mode=SYNTHETIC,
        )


def test_a_real_track_event_cannot_carry_a_simulation_clock() -> None:
    with pytest.raises(ValueError, match="virtual time has no meaning"):
        build_promotion_event(
            PromotionEventType.GATE_EVALUATED,
            track=DecisionTrack.REAL,
            simulation_clock=FIXTURE_GENERATED_AT,
        )


def test_the_event_store_is_idempotent() -> None:
    store = PromotionEventStore()
    first = store.append(
        build_promotion_event(
            PromotionEventType.GATE_EVALUATED,
            track=DecisionTrack.REHEARSAL,
            idempotency_key="k1",
        )
    )
    second = store.append(
        build_promotion_event(
            PromotionEventType.GATE_EVALUATED,
            track=DecisionTrack.REHEARSAL,
            idempotency_key="k1",
        )
    )
    assert first.event_id == second.event_id
    assert len(store) == 1


def test_the_stream_reports_its_track_split() -> None:
    """A stream that is overwhelmingly rehearsal is the honest picture of a
    system that has never run at a bank."""
    counts = repository.events.counts_by_track()
    assert counts["REHEARSAL"] > counts["REAL"]
    assert sum(counts.values()) == len(repository.events)


# --------------------------------------------------------------------------
# Repository
# --------------------------------------------------------------------------


def test_the_fixture_refuses_real_track_writes() -> None:
    fixture = PromotionRepository()
    with pytest.raises(FixtureModeError, match="never be able to produce bank"):
        fixture.record_evaluation(
            GateEvaluation(
                gate_id="supply-chain-clean",
                transition_id="OFFLINE_CANDIDATE__TO__SHADOW_READY",
                track=DecisionTrack.REAL,
                outcome=GateOutcome.PASS,
                evidence_mode=ATTESTED,
                evidence_ids=["ev-x"],
            )
        )


def test_the_fixture_status_is_computed_not_written_down() -> None:
    """A hardcoded verdict cannot be wrong and therefore cannot be right — the
    defect found in wallet_portfolio.py during V3.1.1."""
    status = repository.honest_status()
    assert status["real_state"] == "OFFLINE_CANDIDATE"
    assert status["rehearsed_state"] == "CAUSAL_CHAMPION"
    assert status["bank_shadow_authorized"] is False
    assert status["promotion_machinery_readiness"] == 1.0
    assert status["bank_evidence_readiness"] == 0.0
    assert status["bank_production_status"] == "NOT_PROMOTABLE"


def test_simulated_days_are_published_beside_elapsed_bank_days() -> None:
    status = repository.honest_status()
    assert status["shadow_rehearsal_days"] == 30
    assert status["elapsed_bank_shadow_days"] == 0


def test_every_rehearsal_evidence_item_is_signed() -> None:
    assert len(repository.envelopes()) == len(repository.evidence())
    for envelope in repository.envelopes():
        assert envelope.signature is not None
        assert envelope.signature_status == "SIGNED_REHEARSAL"
        assert envelope.trust_domain == "rehearsal"
        assert envelope.mode is SYNTHETIC


def test_gates_without_failure_injection_are_reported_rather_than_hidden() -> None:
    outstanding = repository.readiness()["gates_without_failure_injection"]
    assert outstanding, "a fixture claiming full injection coverage would be false"


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


def test_the_promotion_service_is_the_twelfth() -> None:
    assert len(SERVICE_ROUTES) == 12
    assert "promotion" in SERVICE_ROUTES


def test_the_promotion_deployment_registers_exactly_its_twelve_routes() -> None:
    from fastapi.routing import APIRoute

    paths = {
        route.path
        for route in promotion_app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/v3/promotion")
    }
    assert len(paths) == 12


@pytest.mark.parametrize(
    "path",
    [
        "/v3/promotion/state",
        "/v3/promotion/readiness",
        "/v3/promotion/gates",
        "/v3/promotion/transitions",
        "/v3/promotion/capabilities",
        "/v3/promotion/evidence",
        "/v3/promotion/signing",
        "/v3/promotion/rehearsal-clock",
        "/v3/promotion/events",
        "/v3/promotion/approvals",
    ],
)
def test_every_read_requires_as_of(client: TestClient, path: str) -> None:
    """A promotion position without a date is unfalsifiable."""
    assert client.get(path, headers=READER).status_code == 422
    assert client.get(path, params={"as_of": AS_OF}, headers=READER).status_code == 200


def test_an_unentitled_role_cannot_read_the_promotion_position(
    client: TestClient,
) -> None:
    """PRODUCT_FINANCE is not a shadow role, so it is denied — the same negative
    the container smoke test exercises against the running service."""
    response = client.get(
        "/v3/promotion/state",
        params={"as_of": AS_OF},
        headers={**READER, "X-User-Roles": "PRODUCT_FINANCE"},
    )
    assert response.status_code == 403


def test_fixture_mode_grants_a_demo_identity_by_design(client: TestClient) -> None:
    """Documented behaviour, asserted so a later change to it is visible: with
    no identity header the fixture deployment returns a demo principal. Any
    non-FIXTURE deployment raises 401 instead."""
    assert client.get(
        "/v3/promotion/state", params={"as_of": AS_OF}
    ).status_code == 200


def test_the_state_route_publishes_both_tracks(client: TestClient) -> None:
    body = client.get(
        "/v3/promotion/state", params={"as_of": AS_OF}, headers=READER
    ).json()
    assert body["real_state"] == "OFFLINE_CANDIDATE"
    assert body["rehearsed_state"] == "CAUSAL_CHAMPION"
    assert body["bank_shadow_authorized"] is False
    assert body["score"]["bank_evidence_readiness"] == 0.0


def test_the_readiness_route_returns_no_composite_score(client: TestClient) -> None:
    from wallet_twin_v32 import assert_no_composite_score

    body = client.get(
        "/v3/promotion/readiness", params={"as_of": AS_OF}, headers=READER
    ).json()
    assert_no_composite_score(body)
    assert_no_composite_score(body["decision"]["score"])


def test_the_gates_route_can_be_filtered_by_transition(client: TestClient) -> None:
    body = client.get(
        "/v3/promotion/gates",
        params={"as_of": AS_OF, "transition_id": "SCALE_READY__TO__CAUSAL_CHAMPION"},
        headers=READER,
    ).json()
    assert len(body["gates"]) == 3


def test_an_unknown_transition_is_a_404(client: TestClient) -> None:
    response = client.get(
        "/v3/promotion/gates",
        params={"as_of": AS_OF, "transition_id": "NOT_A_TRANSITION"},
        headers=READER,
    )
    assert response.status_code == 404


def test_an_unknown_gate_is_a_404(client: TestClient) -> None:
    response = client.get(
        "/v3/promotion/gates/not-a-gate", params={"as_of": AS_OF}, headers=READER
    )
    assert response.status_code == 404


def test_the_gate_detail_route_says_what_would_make_the_real_gate_pass(
    client: TestClient,
) -> None:
    body = client.get(
        "/v3/promotion/gates/elapsed-clean-shadow-days",
        params={"as_of": AS_OF},
        headers=READER,
    ).json()
    assert body["evaluation"]["real_outcome"] == "NOT_EVALUATED"
    assert body["evaluation"]["rehearsal_outcome"] == "PASS"
    assert "thirty consecutive clean" in body["definition"]["what_would_make_real_pass"]


def test_the_capabilities_route_returns_refusals_with_reasons(
    client: TestClient,
) -> None:
    body = client.get(
        "/v3/promotion/capabilities", params={"as_of": AS_OF}, headers=READER
    ).json()
    refused = [item for item in body["capabilities"] if not item["granted"]]
    assert refused
    for item in refused:
        assert item["refusal_reason"]


def test_the_signing_route_states_no_real_bank_capability(client: TestClient) -> None:
    body = client.get(
        "/v3/promotion/signing", params={"as_of": AS_OF}, headers=READER
    ).json()
    assert body["signers"]["real_bank_signing_available"] is False
    assert body["signers"]["executed"] == ["LocalECDSASigner"]


def test_the_clock_route_never_returns_simulated_days_alone(
    client: TestClient,
) -> None:
    body = client.get(
        "/v3/promotion/rehearsal-clock", params={"as_of": AS_OF}, headers=READER
    ).json()
    assert body["rehearsal_days_elapsed"] == 47
    assert body["consecutive_clean_rehearsal_days"] == 30
    assert body["elapsed_bank_shadow_days"] == 0


def test_events_can_be_filtered_by_track(client: TestClient) -> None:
    body = client.get(
        "/v3/promotion/events",
        params={"as_of": AS_OF, "track": "REHEARSAL"},
        headers=READER,
    ).json()
    assert all(item["track"] == "REHEARSAL" for item in body["events"])
    assert body["counts_by_track"]["REHEARSAL"] > 0


# --------------------------------------------------------------------------
# Mutation guards
# --------------------------------------------------------------------------


def evaluation_body(track: str = "REHEARSAL") -> dict:
    return {
        "evaluation": {
            "gate_id": "supply-chain-clean",
            "transition_id": "OFFLINE_CANDIDATE__TO__SHADOW_READY",
            "track": track,
            "outcome": "PASS",
            "evidence_mode": "SYNTHETIC_REHEARSAL"
            if track == "REHEARSAL"
            else "BANK_ATTESTED",
            "evidence_ids": ["ev-supply-chain-clean"],
            "evaluated_at": FIXTURE_GENERATED_AT.isoformat(),
        }
    }


def test_a_mutation_without_an_idempotency_key_is_refused(client: TestClient) -> None:
    response = client.post(
        "/v3/promotion/evaluations", json=evaluation_body(), headers=READER
    )
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()["detail"]


def test_fixture_mode_refuses_a_real_track_evaluation(client: TestClient) -> None:
    response = client.post(
        "/v3/promotion/evaluations",
        json=evaluation_body("REAL"),
        headers={**READER, "Idempotency-Key": "real-1"},
    )
    assert response.status_code == 409
    assert "bank authorisation" in response.json()["detail"]


def test_a_relationship_manager_cannot_write_to_the_promotion_register(
    client: TestClient,
) -> None:
    """Reading the promotion position is broadly useful; deciding it is not."""
    response = client.post(
        "/v3/promotion/evaluations",
        json=evaluation_body(),
        headers={**RM, "Idempotency-Key": "rm-1"},
    )
    assert response.status_code == 403


def test_a_relationship_manager_may_still_read_the_promotion_position(
    client: TestClient,
) -> None:
    response = client.get(
        "/v3/promotion/state", params={"as_of": AS_OF}, headers=RM
    )
    assert response.status_code == 200


def test_an_entitled_operator_can_record_a_rehearsal_evaluation(
    client: TestClient,
) -> None:
    response = client.post(
        "/v3/promotion/evaluations",
        json=evaluation_body(),
        headers={**READER, "Idempotency-Key": "rehearsal-write-1"},
    )
    assert response.status_code == 201
    assert response.json()["track"] == "REHEARSAL"


def test_a_self_approval_is_refused_before_it_reaches_the_service(
    client: TestClient,
) -> None:
    """Maker/checker is a contract validator, so it fails at parse time."""
    response = client.post(
        "/v3/promotion/approvals",
        json={
            "approval": {
                "approval_id": "ap-self",
                "transition_id": "OFFLINE_CANDIDATE__TO__SHADOW_READY",
                "track": "REHEARSAL",
                "submitted_by": "same@bank",
                "submitted_role": "ENGINEERING",
                "reviewed_by": "same@bank",
                "reviewed_role": "MODEL_RISK",
                "decision": "APPROVED",
                "rationale": "approving my own work",
                "submitted_at": FIXTURE_GENERATED_AT.isoformat(),
                "reviewed_at": (FIXTURE_GENERATED_AT + timedelta(hours=1)).isoformat(),
            }
        },
        headers={**READER, "Idempotency-Key": "self-approve"},
    )
    assert response.status_code == 422


def test_the_composed_api_exposes_the_promotion_surface(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    promotion_paths = [path for path in schema["paths"] if path.startswith("/v3/promotion")]
    assert len(promotion_paths) == 12


def test_as_of_in_the_future_still_returns_the_recorded_position(
    client: TestClient,
) -> None:
    """The engine derives state from evaluations, not from a stored value, so a
    later as_of cannot invent progress."""
    later = (date.fromisoformat(AS_OF) + timedelta(days=90)).isoformat()
    body = client.get(
        "/v3/promotion/state", params={"as_of": later}, headers=READER
    ).json()
    assert body["real_state"] == "OFFLINE_CANDIDATE"
