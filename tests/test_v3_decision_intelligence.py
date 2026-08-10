from __future__ import annotations

from datetime import date

import numpy as np
from fastapi.testclient import TestClient

from wallet_twin_v2.api import app
from wallet_twin_v3.repository import repository
from wallet_twin_v3.shadow_network import sinkhorn_coupling


AS_OF = date(2026, 6, 30)
client = TestClient(app)


def test_sinkhorn_transport_preserves_marginals() -> None:
    rows = np.array([0.55, 0.30, 0.15])
    columns = np.array([0.50, 0.32, 0.18])
    cost = np.array([[0.1, 0.5, 0.9], [0.4, 0.1, 0.5], [0.8, 0.4, 0.1]])
    coupling = sinkhorn_coupling(rows, columns, cost)
    assert np.allclose(coupling.sum(axis=1), rows, atol=1e-8)
    assert np.allclose(coupling.sum(axis=0), columns, atol=1e-8)


def test_every_shadow_wallet_reconciles_and_uses_anonymous_nodes() -> None:
    for opportunity in repository.opportunities:
        shadow = opportunity.shadow_wallet
        assert shadow.measurement_status == "RECONSTRUCTED_NOT_MEASURED"
        assert shadow.claim_class.value == "SCENARIO"
        assert (
            abs(
                shadow.total_wallet.median
                - shadow.observed_bank_flow
                - shadow.latent_external_wallet.median
            )
            < 1.0
        )
        assert all(
            flow.provider_node.startswith("External provider ") for flow in shadow.flows
        )


def test_pu_need_model_keeps_scar_assumption_visible() -> None:
    values = [item.need for item in repository.opportunities]
    assert any(item.positive_label_observed for item in values)
    assert any(not item.positive_label_observed for item in values)
    assert all(0 <= item.product_need_probability <= 1 for item in values)
    assert all(
        any("SCAR" in assumption for assumption in item.assumptions) for item in values
    )


def test_change_point_horizons_and_leakage_labels_are_governed() -> None:
    for opportunity in repository.opportunities:
        signal = opportunity.change_point
        assert (
            signal.probability_30d <= signal.probability_60d <= signal.probability_90d
        )
        assert (
            opportunity.leakage.measurement_status
            == "MODELLED_SIGNAL_NOT_CONFIRMED_LEAKAGE"
        )


def test_robust_portfolio_respects_capacity_and_concentration() -> None:
    portfolio = repository.action_portfolio
    assert len(portfolio.selected_actions) <= portfolio.capacity
    assert (
        max(portfolio.product_counts.values())
        <= portfolio.constraints["max_per_product"]
    )
    assert (
        max(portfolio.sector_counts.values()) <= portfolio.constraints["max_per_sector"]
    )
    assert len({action.entity_id for action in portfolio.selected_actions}) == len(
        portfolio.selected_actions
    )
    assert portfolio.causal_status == "CAUSAL_INCREMENTAL_VALUE_WITHHELD"


def test_decision_directed_evidence_only_selects_positive_net_voi() -> None:
    plan = repository.evidence_acquisition
    assert plan.autonomous_external_retrieval is False
    assert len(plan.selected) <= plan.capacity
    assert all(
        item.retrieve and item.net_value_of_information_zar > 0
        for item in plan.selected
    )


def test_v3_api_exposes_entitled_decision_surfaces() -> None:
    for path in [
        "/v3/decision-lab?as_of=2026-06-30",
        "/v3/opportunities?as_of=2026-06-30&limit=2",
        "/v3/action-portfolio?as_of=2026-06-30",
        "/v3/evidence-acquisition?as_of=2026-06-30",
        "/v3/leakage?as_of=2026-06-30&limit=2",
        "/v3/models/validation",
    ]:
        response = client.get(path)
        assert response.status_code == 200, response.text


def test_v3_decision_lab_filters_every_client_level_projection() -> None:
    headers = {
        "x-user-id": "restricted-validator",
        "x-user-roles": "SHADOW_OPERATOR,MODEL_VALIDATOR",
        "x-user-clients": "E01",
        "x-user-products": "*",
    }
    response = client.get(
        "/v3/decision-lab?as_of=2026-06-30", headers=headers
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert {item["entity_id"] for item in payload["opportunities"]} == {"E01"}
    assert set(payload["treasury_graphs"]) == {"E01"}
    assert all(
        item["entity_id"] == "E01"
        for item in payload["action_portfolio"]["selected_actions"]
    )
    assert all(
        item["entity_id"] == "E01"
        for field in ("selected", "deferred")
        for item in payload["evidence_acquisition"][field]
    )


def test_v3_brief_separates_evidence_model_and_missing_inputs() -> None:
    opportunity_id = repository.action_portfolio.selected_actions[0].opportunity_id
    response = client.get(
        f"/v3/opportunities/{opportunity_id}/brief?as_of={AS_OF.isoformat()}"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["observed"]["claim_class"] == "OBSERVED"
    assert all(
        item["claim_class"] in {"SCENARIO", "POSTERIOR"}
        for item in payload["model_claims"]
    )
    assert "direct E3 multibank share observation" in payload["missing_evidence"]
    assert payload["llm_contract"]["autonomous_action"] is False


def test_v3_validation_has_no_measured_competitor_or_causal_claims() -> None:
    validation = repository.validation
    assert validation["max_mass_balance_error_zar"] == 0
    assert validation["measured_competitor_share_claims"] == 0
    assert validation["causal_value_claims"] == 0
    assert validation["rm_capacity_respected"] is True
