from __future__ import annotations

import math
from datetime import date

from fastapi.testclient import TestClient

from wallet_twin_v2.api import app
from wallet_twin_v31.repository import repository


AS_OF = date(2026, 6, 30)
HEADERS = {
    "x-user-id": "submission-validator",
    "x-user-roles": "SHADOW_OPERATOR,MODEL_VALIDATOR",
    "x-user-team": "model-risk",
    "x-user-clients": "*",
    "x-user-products": "*",
}


def test_wallet_projection_is_complete_and_approval_authoritative():
    projection = repository.wallet_portfolio(AS_OF)
    assert projection.version == "3.1.1"
    assert projection.clients == 20
    assert len(projection.products) == 5
    assert len(projection.cells) == 100
    assert projection.approved_anchor_cells == 15
    assert projection.prior_led_cells == 85
    assert projection.approved_source_facts == 31
    assert projection.pending_source_facts == 51
    assert all(
        not cell.active_fact_ids
        for cell in projection.cells
        if cell.anchor_activation != "ACTIVATED"
    )


def test_wallet_identity_and_gap_equations_hold():
    for cell in repository.wallet_portfolio(AS_OF).cells:
        observed = float(cell.observed_activity.normalized_amount)
        assert cell.posterior_wallet.lower >= observed
        assert math.isclose(
            observed / cell.posterior_wallet.median,
            cell.share_interval.median,
            rel_tol=1e-4,
            abs_tol=1e-6,
        )
        expected = max(
            cell.target_share_scenario * cell.posterior_wallet.median - observed,
            0.0,
        )
        assert math.isclose(cell.contestable_activity.median, expected, abs_tol=0.011)


def test_wallet_routes_require_identity_and_respect_entitlements(monkeypatch):
    monkeypatch.setenv("WALLET_DEPLOYMENT_MODE", "CLIENT_DEMO")
    client = TestClient(app)
    unauthenticated = client.get("/v3/wallet-portfolio?as_of=2026-06-30")
    assert unauthenticated.status_code == 401

    response = client.get("/v3/wallet-portfolio?as_of=2026-06-30", headers=HEADERS)
    assert response.status_code == 200
    assert len(response.json()["cells"]) == 100

    detail = client.get(
        "/v3/wallet-opportunities/E01-trade-finance?as_of=2026-06-30",
        headers={**HEADERS, "x-user-clients": "E02"},
    )
    assert detail.status_code == 403


def test_openapi_exposes_all_submission_wallet_reads():
    schema = app.openapi()
    assert "/v3/wallet-portfolio" in schema["paths"]
    assert "/v3/wallet-opportunities/{opportunity_id}" in schema["paths"]
    assert "/v3/clients/{client_id}/briefing-notes" in schema["paths"]
