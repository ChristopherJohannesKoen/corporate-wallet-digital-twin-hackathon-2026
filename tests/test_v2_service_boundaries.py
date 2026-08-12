from fastapi.routing import APIRoute

from fastapi.testclient import TestClient

from wallet_twin_v2.service_apps import (
    business_twin_app,
    evidence_app,
    recommendation_app,
    workbench_bff_app,
)


def _paths(app):
    return {route.path for route in app.routes if isinstance(route, APIRoute)}


def test_evidence_service_exposes_only_owned_business_paths():
    paths = _paths(evidence_app)
    assert "/health" in paths
    assert any(path.startswith("/v1/evidence") for path in paths)
    assert not any(path.startswith("/v1/opportunities") for path in paths)


def test_recommendation_and_bff_contracts_are_scoped():
    recommendation_paths = _paths(recommendation_app)
    bff_paths = _paths(workbench_bff_app)
    assert "/v1/opportunities" in recommendation_paths
    assert "/v3/decision-lab" in recommendation_paths
    assert "/v3/decision-twin" in recommendation_paths
    assert "/v1/clients/{client_id}/twin" in bff_paths
    assert "/v3/decision-lab" in bff_paths
    assert "/v3/decision-twin" in bff_paths
    assert not any(path.startswith("/v1/evidence") for path in bff_paths)


def test_business_twin_service_is_an_independent_v31_boundary() -> None:
    paths = _paths(business_twin_app)
    assert "/v3/decision-twin" in paths
    assert "/v3/clients/{client_id}/business-twin" in paths
    assert "/v3/funding-routes/{client_id}" in paths
    assert "/v3/decision-lab" not in paths
    assert not any(path.startswith("/v1/evidence") for path in paths)


def test_composed_service_health_reports_v31() -> None:
    response = TestClient(workbench_bff_app).get("/health")
    assert response.status_code == 200
    assert response.json()["version"] == "3.1.0"
