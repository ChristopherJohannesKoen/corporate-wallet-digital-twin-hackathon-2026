from fastapi.routing import APIRoute

from wallet_twin_v2.service_apps import evidence_app, recommendation_app, workbench_bff_app


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
    assert "/v1/clients/{client_id}/twin" in bff_paths
    assert not any(path.startswith("/v1/evidence") for path in bff_paths)
