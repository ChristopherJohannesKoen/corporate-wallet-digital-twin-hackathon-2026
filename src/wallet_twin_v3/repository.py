from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from wallet_twin_v2.repository import repository as v2_repository

from .briefing import compile_decision_brief
from .contracts import V3OpportunityView
from .fixtures import build_v3_fixture


class V3Repository:
    def __init__(self) -> None:
        fixture = build_v3_fixture(
            {
                "metadata": v2_repository.metadata,
                "opportunities": v2_repository.opportunities,
                "release": v2_repository.release,
            }
        )
        self.metadata: dict[str, Any] = fixture["metadata"]
        self.opportunities: list[V3OpportunityView] = fixture["opportunities"]
        self.by_id = {item.opportunity_id: item for item in self.opportunities}
        self.shadow_reconstructions = fixture["shadow_reconstructions"]
        self.treasury_graphs = fixture["treasury_graphs"]
        self.action_portfolio = fixture["action_portfolio"]
        self.evidence_acquisition = fixture["evidence_acquisition"]
        self.public_sensors = fixture["public_sensors"]
        self.validation = fixture["validation"]
        self.decision_selected_ids = set(fixture["decision_selected_ids"])
        self.release = fixture["release"]

    @property
    def as_of(self) -> date:
        return date.fromisoformat(self.metadata["as_of"])

    def check_as_of(self, as_of: date) -> None:
        if as_of != self.as_of:
            raise KeyError(f"point-in-time snapshot unavailable: {as_of.isoformat()}")

    @staticmethod
    def _allowed(entity_id: str, client_ids: list[str]) -> bool:
        return "*" in client_ids or entity_id in client_ids

    def entitled_opportunities(self, client_ids: list[str]) -> list[V3OpportunityView]:
        return [
            item
            for item in self.opportunities
            if self._allowed(item.entity_id, client_ids)
        ]

    def action_portfolio_projection(self, client_ids: list[str]) -> dict[str, Any]:
        payload = self.action_portfolio.model_dump(mode="json")
        actions = [
            item
            for item in payload["selected_actions"]
            if self._allowed(item["entity_id"], client_ids)
        ]
        payload["selected_actions"] = actions
        payload["expected_scenario_value_zar"] = sum(
            item["expected_scenario_value_zar"] for item in actions
        )
        payload["downside_cvar_zar"] = sum(
            item["downside_cvar_zar"] for item in actions
        )
        payload["product_counts"] = dict(Counter(item["product"] for item in actions))
        payload["sector_counts"] = dict(Counter(item["sector"] for item in actions))
        return payload

    def evidence_acquisition_projection(self, client_ids: list[str]) -> dict[str, Any]:
        payload = self.evidence_acquisition.model_dump(mode="json")
        for field in ("selected", "deferred"):
            payload[field] = [
                item
                for item in payload[field]
                if self._allowed(item["entity_id"], client_ids)
            ]
        payload["total_expected_net_voi_zar"] = sum(
            item["net_value_of_information_zar"] for item in payload["selected"]
        )
        return payload

    def decision_lab(self, as_of: date, client_ids: list[str]) -> dict[str, Any]:
        self.check_as_of(as_of)
        opportunities = self.entitled_opportunities(client_ids)
        allowed_ids = {item.entity_id for item in opportunities}
        return {
            "metadata": self.metadata,
            "opportunities": [item.model_dump(mode="json") for item in opportunities],
            "treasury_graphs": {
                entity_id: graph
                for entity_id, graph in self.treasury_graphs.items()
                if entity_id in allowed_ids
            },
            "action_portfolio": self.action_portfolio_projection(client_ids),
            "evidence_acquisition": self.evidence_acquisition_projection(client_ids),
            "public_sensors": self.public_sensors,
            "validation": self.validation,
            "release": self.release,
        }

    def opportunity(self, opportunity_id: str, as_of: date) -> V3OpportunityView:
        self.check_as_of(as_of)
        return self.by_id[opportunity_id]

    def client_network(self, entity_id: str, as_of: date) -> dict[str, Any]:
        self.check_as_of(as_of)
        graph = self.treasury_graphs[entity_id]
        reconstructions = [
            item for item in self.opportunities if item.entity_id == entity_id
        ]
        return {
            "treasury_graph": graph,
            "reconstructions": [
                item.shadow_wallet.model_dump(mode="json") for item in reconstructions
            ],
        }

    def brief(self, opportunity_id: str, as_of: date) -> dict[str, Any]:
        item = self.opportunity(opportunity_id, as_of)
        v2_item = v2_repository.opportunity(opportunity_id, as_of)
        facts = [
            v2_repository.facts[fact_id]
            for fact_id in v2_item.evidence_fact_ids
            if fact_id in v2_repository.facts
        ]
        return compile_decision_brief(
            v2_item, item, facts, opportunity_id in self.decision_selected_ids
        )


repository = V3Repository()
