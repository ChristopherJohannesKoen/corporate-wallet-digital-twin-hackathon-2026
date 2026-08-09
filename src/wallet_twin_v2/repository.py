from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from .contracts import OpportunityView, RateCard
from .fixtures import build_fixture


class ShadowRepository:
    """Read model for the local shadow platform.

    Production adapters replace this with service-owned PostgreSQL projections
    and point-in-time Delta tables; the interface remains stable.
    """

    def __init__(self) -> None:
        fixture = build_fixture()
        self.metadata: Dict[str, Any] = fixture["metadata"]
        self.opportunities: List[OpportunityView] = fixture["opportunities"]
        self.clients: Dict[str, dict] = fixture["clients"]
        self.rate_cards: Dict[str, RateCard] = fixture["rate_cards"]
        self.facts: Dict[str, dict] = fixture["facts"]
        self.sensitivity: dict = fixture["sensitivity"]
        self.legacy_sensitivity: list = fixture["legacy_sensitivity"]
        self.evidence_coverage: dict = fixture["evidence_coverage"]
        self.benchmark_economics: dict = fixture["benchmark_economics"]
        self.offline_validation: dict = fixture["offline_validation"]
        self.genai_evaluation: dict = fixture["genai_evaluation"]
        self.genai_provider_status: dict = fixture["genai_provider_status"]
        self.shadow_replay: dict = fixture["shadow_replay"]
        self.production_candidate: dict = fixture["production_candidate"]
        self.public_evidence_qa: dict = fixture["public_evidence_qa"]
        self.trial_rehearsal: dict = fixture["trial_rehearsal"]
        self.operational_rehearsal: dict = fixture["operational_rehearsal"]
        self.client_demo_data: dict = fixture.get("client_demo_data", {})
        self.client_demo_scorecard: dict = fixture.get("client_demo_scorecard", {})
        self.production_target: dict = fixture.get("production_target", {})
        self.release: dict = fixture["release"]

    @property
    def as_of(self) -> date:
        return date.fromisoformat(self.metadata["as_of"])

    def list_opportunities(self, as_of: date) -> List[OpportunityView]:
        self._check_as_of(as_of)
        return list(self.opportunities)

    def opportunity(self, opportunity_id: str, as_of: date) -> OpportunityView:
        self._check_as_of(as_of)
        try:
            return next(item for item in self.opportunities if item.opportunity_id == opportunity_id)
        except StopIteration as exc:
            raise KeyError(opportunity_id) from exc

    def client(self, client_id: str, as_of: date) -> dict:
        self._check_as_of(as_of)
        return self.clients[client_id]

    def _check_as_of(self, as_of: date) -> None:
        if as_of != self.as_of:
            raise KeyError(f"point-in-time snapshot unavailable: {as_of.isoformat()}")


repository = ShadowRepository()
