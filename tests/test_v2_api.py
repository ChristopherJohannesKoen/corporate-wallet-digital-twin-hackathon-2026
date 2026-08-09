import hashlib
import json

from fastapi.testclient import TestClient

from wallet_twin_v2.api import app


client = TestClient(app)
AS_OF = "2026-06-30"


def test_shadow_api_requires_as_of_and_returns_strict_layers():
    assert client.get("/v1/opportunities").status_code == 422
    response = client.get(f"/v1/opportunities?as_of={AS_OF}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 100
    item = payload["items"][0]
    assert item["observed_activity"]
    assert item["identification_bounds"]["claim_class"] == "IDENTIFIED_BOUND"
    assert item["posterior_wallet"]["claim_class"] == "POSTERIOR"
    assert item["eligibility"]["state"] == "SHADOW_ONLY"
    assert (
        item["commercial"]["watermark"]
        == "CLIENT-DEMO SCENARIO ECONOMICS — REPRESENTATIVE INPUTS — NOT BANK-APPROVED PRICING"
    )


def test_rm_is_denied_during_shadow_mode():
    response = client.get(
        f"/v1/clients/E01/twin?as_of={AS_OF}",
        headers={
            "x-user-id": "rm-1",
            "x-user-roles": "RM",
            "x-user-clients": "E01",
            "x-user-products": "*",
        },
    )
    assert response.status_code == 403
    assert "SHADOW_ROLE_REQUIRED" in response.json()["detail"]["reason_codes"]


def test_explanation_has_no_causal_value_and_uses_fallback():
    first = client.get(f"/v1/opportunities?as_of={AS_OF}").json()["items"][0]
    response = client.get(f"/v1/opportunities/{first['opportunity_id']}/explanation?as_of={AS_OF}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["layers"]["causal"] is None
    assert payload["narrative_mode"] in {"deterministic", "deterministic_fallback"}


def test_model_is_not_promotable_without_bank_inputs():
    response = client.get("/v1/models/hierarchical-wallet-2.0.0/validation")
    assert response.status_code == 200
    assert response.json()["promotable"] is False


def test_ingestion_quarantines_hash_mismatch_and_missing_critical_field():
    response = client.post(
        "/v1/ingestion/records",
        json={
            "record_id": "source-1",
            "source_system": "fixture",
            "contract_version": "1.0.0",
            "event_time": "2026-06-01T00:00:00Z",
            "as_of": AS_OF,
            "source_hash": "0" * 64,
            "required_fields": ["amount", "currency"],
            "payload": {"amount": 100},
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "QUARANTINED"
    assert "SOURCE_HASH_MISMATCH" in response.json()["reason_codes"]
    assert "MISSING_REQUIRED_FIELD:currency" in response.json()["reason_codes"]


def test_ingestion_accepts_exact_canonical_hash_without_persisting_fixture():
    payload = {"amount": 100, "currency": "ZAR"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    response = client.post(
        "/v1/ingestion/records",
        json={
            "record_id": "source-2",
            "source_system": "fixture",
            "contract_version": "1.0.0",
            "event_time": "2026-06-01T00:00:00Z",
            "as_of": AS_OF,
            "source_hash": hashlib.sha256(canonical).hexdigest(),
            "required_fields": ["amount", "currency"],
            "payload": payload,
        },
    )
    assert response.json() == {
        "record_id": "source-2",
        "status": "ACCEPTED",
        "reason_codes": [],
        "contract_version": "1.0.0",
        "persisted": False,
    }


def test_timing_endpoint_returns_named_monotone_probabilities():
    response = client.post(
        "/v1/timing/predict",
        json={
            "entity_id": "E01",
            "product": "Trade Finance",
            "as_of": AS_OF,
            "event_name": "qualified_rm_action",
            "seasonal_ratio": 1.2,
            "maturity_days": 45,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["event_name"] == "qualified_rm_action"
    assert result["probability_30d"] < result["probability_60d"] < result["probability_90d"]
