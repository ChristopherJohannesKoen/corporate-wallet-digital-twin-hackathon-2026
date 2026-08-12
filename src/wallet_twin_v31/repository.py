"""V3.1 repository interfaces.

Import-time fixture construction is replaced by explicit repository
interfaces, so the same service code runs against the reproducible
demonstration fixture, a Delta-backed analytical store or a PostgreSQL
workflow store without changing a call site.

Only the fixture repository is implemented here.  The Delta and PostgreSQL
repositories are declared with the method contract they must satisfy and raise
``NotImplementedError`` — a stub that lies about being connected would be worse
than one that says it is not.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Dict, List, Mapping, Sequence

from .business_evidence import BusinessEvidenceRegistry
from .business_graph import explainable_view
from .contracts import (
    BusinessGraphSnapshot,
    BusinessTwinSnapshot,
    ChangeDigest,
    ConversationBrief,
    ConversationCandidate,
    CoveragePlan,
    FundingRouteProjection,
)
from .events import (
    V31EventStore,
    V31EventType,
    build_v31_event,
)
from .fixtures import DEFAULT_DIGEST_SINCE, build_v31_fixture
from .questions import ClientAnswerWorkflow


class V31Repository(ABC):
    """The contract every V3.1 storage backend must satisfy."""

    @property
    @abstractmethod
    def as_of(self) -> date: ...

    @abstractmethod
    def business_twin(self, entity_id: str, as_of: date) -> BusinessTwinSnapshot: ...

    @abstractmethod
    def business_graph(self, entity_id: str, as_of: date) -> BusinessGraphSnapshot: ...

    @abstractmethod
    def change_digest(self, entity_id: str, since: date, as_of: date) -> ChangeDigest: ...

    @abstractmethod
    def conversations(self, as_of: date) -> List[ConversationCandidate]: ...

    @abstractmethod
    def conversation(self, conversation_id: str, as_of: date) -> ConversationCandidate: ...

    @abstractmethod
    def brief(self, conversation_id: str, as_of: date) -> ConversationBrief: ...

    @abstractmethod
    def coverage_plan(self, as_of: date, week_start: date) -> CoveragePlan: ...

    @abstractmethod
    def funding_routes(self, entity_id: str, as_of: date) -> FundingRouteProjection: ...


class DeltaAnalyticalRepository(V31Repository):
    """Reads curated Delta data products in Unity Catalog.

    Declared, not implemented: the demonstration boundary has no Databricks
    workspace attached, and returning fabricated rows from a stub would defeat
    the point of the point-in-time contract.
    """

    _REASON = (
        "Delta-backed analytical repository requires an attached Databricks workspace "
        "with Unity Catalog row filters; not available in the demonstration boundary."
    )

    @property
    def as_of(self) -> date:
        raise NotImplementedError(self._REASON)

    def business_twin(self, entity_id: str, as_of: date) -> BusinessTwinSnapshot:
        raise NotImplementedError(self._REASON)

    def business_graph(self, entity_id: str, as_of: date) -> BusinessGraphSnapshot:
        raise NotImplementedError(self._REASON)

    def change_digest(self, entity_id: str, since: date, as_of: date) -> ChangeDigest:
        raise NotImplementedError(self._REASON)

    def conversations(self, as_of: date) -> List[ConversationCandidate]:
        raise NotImplementedError(self._REASON)

    def conversation(self, conversation_id: str, as_of: date) -> ConversationCandidate:
        raise NotImplementedError(self._REASON)

    def brief(self, conversation_id: str, as_of: date) -> ConversationBrief:
        raise NotImplementedError(self._REASON)

    def coverage_plan(self, as_of: date, week_start: date) -> CoveragePlan:
        raise NotImplementedError(self._REASON)

    def funding_routes(self, entity_id: str, as_of: date) -> FundingRouteProjection:
        raise NotImplementedError(self._REASON)


class PostgresWorkflowRepository:
    """Operational workflow state: snapshot publication, reviews, attestations.

    Declared, not implemented, for the same reason as the Delta repository.
    """

    _REASON = (
        "PostgreSQL workflow repository requires a provisioned operational database; "
        "not available in the demonstration boundary."
    )

    def publication_state(self, snapshot_id: str) -> Dict[str, Any]:
        raise NotImplementedError(self._REASON)

    def open_review_tasks(self) -> List[Dict[str, Any]]:
        raise NotImplementedError(self._REASON)

    def record_attestation(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError(self._REASON)


class FixtureV31Repository(V31Repository):
    """Reproducible demonstration repository built from the frozen baseline."""

    def __init__(self) -> None:
        self._fixture = build_v31_fixture()
        self.metadata: Dict[str, Any] = self._fixture["metadata"]
        self.twins: Dict[str, BusinessTwinSnapshot] = self._fixture["business_twins"]
        self.graphs: Dict[str, BusinessGraphSnapshot] = self._fixture["business_graphs"]
        self.events = self._fixture["business_events"]
        self.indicators = self._fixture["indicators"]
        self.problems = self._fixture["problems"]
        self.estimates = self._fixture["solution_estimates"]
        self.routes: Dict[str, FundingRouteProjection] = self._fixture["funding_routes"]
        self.conversation_list: List[ConversationCandidate] = self._fixture[
            "conversations"
        ]
        self.by_id: Dict[str, ConversationCandidate] = self._fixture[
            "conversation_index"
        ]
        self.briefs: Dict[str, ConversationBrief] = self._fixture["briefs"]
        self.questions = self._fixture["questions"]
        self.plan: CoveragePlan = self._fixture["coverage_plan"]
        self.digests: Dict[str, ChangeDigest] = self._fixture["change_digests"]
        self.registry: BusinessEvidenceRegistry = self._fixture["evidence_registry"]
        self.evidence_coverage = self._fixture["evidence_coverage"]
        self.pareto_status = self._fixture["pareto_status"]
        self.policy = self._fixture["policy"]
        self.validation = self._fixture["validation"]
        self.release = self._fixture["release"]
        self.events_store = V31EventStore()
        self.answers = ClientAnswerWorkflow(self.as_of)
        self._publish_snapshot_events()

    # -- point in time -----------------------------------------------------
    @property
    def as_of(self) -> date:
        return date.fromisoformat(self.metadata["as_of"])

    @property
    def week_start(self) -> date:
        return date.fromisoformat(self.metadata["week_start"])

    def check_as_of(self, as_of: date) -> None:
        if as_of != self.as_of:
            raise KeyError(f"point-in-time snapshot unavailable: {as_of.isoformat()}")

    @staticmethod
    def _allowed(entity_id: str, client_ids: Sequence[str]) -> bool:
        return "*" in client_ids or entity_id in client_ids

    def _require_entitlement(self, entity_id: str, client_ids: Sequence[str]) -> None:
        if not self._allowed(entity_id, client_ids):
            raise KeyError(f"client not entitled: {entity_id}")

    # -- events ------------------------------------------------------------
    def _publish_snapshot_events(self) -> None:
        for entity_id, twin in self.twins.items():
            self.events_store.append(
                build_v31_event(
                    V31EventType.BUSINESS_TWIN_SNAPSHOT_PUBLISHED,
                    entity_id=entity_id,
                    as_of=self.as_of,
                    snapshot_id=twin.snapshot_id,
                    idempotency_key=f"twin:{twin.snapshot_id}",
                    payload={
                        "supported_domain_count": twin.supported_domain_count,
                        "claim_count": twin.claim_count,
                    },
                )
            )
            graph = self.graphs[entity_id]
            self.events_store.append(
                build_v31_event(
                    V31EventType.BUSINESS_GRAPH_SNAPSHOT_PUBLISHED,
                    entity_id=entity_id,
                    as_of=self.as_of,
                    snapshot_id=graph.graph_id,
                    idempotency_key=f"graph:{graph.graph_id}",
                    payload={
                        "nodes": len(graph.nodes),
                        "edges": len(graph.edges),
                        "review_candidate_edges": graph.review_candidate_edges,
                    },
                )
            )
            for event in self.events[entity_id]:
                self.events_store.append(
                    build_v31_event(
                        V31EventType.BUSINESS_EVENT_PUBLISHED,
                        entity_id=entity_id,
                        as_of=self.as_of,
                        idempotency_key=event.event_key,
                        payload={
                            "event_type": event.event_type,
                            "event_date": event.event_date.isoformat(),
                        },
                    )
                )
            for hypothesis in self.problems[entity_id].values():
                if not hypothesis.identified:
                    continue
                self.events_store.append(
                    build_v31_event(
                        V31EventType.PROBLEM_HYPOTHESIS_PUBLISHED,
                        entity_id=entity_id,
                        as_of=self.as_of,
                        problem_id=hypothesis.problem_id,
                        idempotency_key=hypothesis.problem_id,
                        payload={
                            "problem": hypothesis.problem.value,
                            "commercially_eligible": hypothesis.commercially_eligible,
                        },
                    )
                )

        for conversation in self.conversation_list:
            self.events_store.append(
                build_v31_event(
                    V31EventType.FEASIBILITY_ASSESSMENT_RECORDED,
                    entity_id=conversation.entity_id,
                    as_of=self.as_of,
                    conversation_id=conversation.conversation_id,
                    solution_bundle_id=conversation.solution_bundle.bundle_id,
                    idempotency_key=conversation.risk_and_feasibility.assessment_id,
                    payload={
                        "permitted_action": conversation.risk_and_feasibility.permitted_action.value,
                        "blocked": conversation.risk_and_feasibility.blocked,
                    },
                )
            )
            self.events_store.append(
                build_v31_event(
                    V31EventType.CONVERSATION_ELIGIBILITY_RECORDED,
                    entity_id=conversation.entity_id,
                    as_of=self.as_of,
                    conversation_id=conversation.conversation_id,
                    problem_id=conversation.problem.problem_id,
                    solution_bundle_id=conversation.solution_bundle.bundle_id,
                    idempotency_key=f"eligibility:{conversation.conversation_id}",
                    reason_codes=list(conversation.eligibility_reasons),
                    payload={"eligibility": conversation.eligibility.value},
                )
            )
            if conversation.next_best_question is not None:
                self.events_store.append(
                    build_v31_event(
                        V31EventType.INFORMATION_QUESTION_PROPOSED,
                        entity_id=conversation.entity_id,
                        as_of=self.as_of,
                        conversation_id=conversation.conversation_id,
                        idempotency_key=conversation.next_best_question.question_id,
                        payload={
                            "variable_id": conversation.next_best_question.variable_id,
                            "net_voi_zar": conversation.next_best_question.net_voi_zar,
                        },
                    )
                )
            self.events_store.append(
                build_v31_event(
                    V31EventType.CONVERSATION_BRIEF_COMPILED,
                    entity_id=conversation.entity_id,
                    as_of=self.as_of,
                    conversation_id=conversation.conversation_id,
                    idempotency_key=f"brief:{conversation.conversation_id}",
                    payload={"compiler": self.briefs[conversation.conversation_id].compiler},
                )
            )

        self.events_store.append(
            build_v31_event(
                V31EventType.COVERAGE_PLAN_SELECTED,
                as_of=self.as_of,
                idempotency_key=self.plan.plan_id,
                payload={
                    "plan_id": self.plan.plan_id,
                    "week_start": self.plan.week_start.isoformat(),
                    "selected": [entry.conversation_id for entry in self.plan.entries],
                    "solver_status": self.plan.solver_status,
                },
            )
        )

    # -- reads -------------------------------------------------------------
    def business_twin(
        self, entity_id: str, as_of: date, client_ids: Sequence[str] = ("*",)
    ) -> BusinessTwinSnapshot:
        self.check_as_of(as_of)
        self._require_entitlement(entity_id, client_ids)
        return self.twins[entity_id]

    def business_graph(
        self,
        entity_id: str,
        as_of: date,
        client_ids: Sequence[str] = ("*",),
        *,
        explainable_only: bool = False,
    ) -> BusinessGraphSnapshot:
        self.check_as_of(as_of)
        self._require_entitlement(entity_id, client_ids)
        graph = self.graphs[entity_id]
        return explainable_view(graph) if explainable_only else graph

    def change_digest(
        self,
        entity_id: str,
        since: date,
        as_of: date,
        client_ids: Sequence[str] = ("*",),
    ) -> ChangeDigest:
        self.check_as_of(as_of)
        if since > as_of:
            raise ValueError("since must not exceed as_of")
        self._require_entitlement(entity_id, client_ids)
        from .change_digest import ChangeDigestBuilder

        if since == DEFAULT_DIGEST_SINCE:
            return self.digests[entity_id]
        return ChangeDigestBuilder(self.registry, self.events, as_of).build(
            entity_id, since
        )

    def conversations(
        self, as_of: date, client_ids: Sequence[str] = ("*",)
    ) -> List[ConversationCandidate]:
        self.check_as_of(as_of)
        return [
            item
            for item in self.conversation_list
            if self._allowed(item.entity_id, client_ids)
        ]

    def conversation(
        self, conversation_id: str, as_of: date, client_ids: Sequence[str] = ("*",)
    ) -> ConversationCandidate:
        self.check_as_of(as_of)
        item = self.by_id[conversation_id]
        self._require_entitlement(item.entity_id, client_ids)
        return item

    def brief(
        self, conversation_id: str, as_of: date, client_ids: Sequence[str] = ("*",)
    ) -> ConversationBrief:
        conversation = self.conversation(conversation_id, as_of, client_ids)
        return self.briefs[conversation.conversation_id]

    def coverage_plan(
        self,
        as_of: date,
        week_start: date,
        client_ids: Sequence[str] = ("*",),
    ) -> CoveragePlan:
        self.check_as_of(as_of)
        if week_start != self.week_start:
            raise KeyError(f"coverage plan unavailable for week {week_start.isoformat()}")
        entries = [
            entry
            for entry in self.plan.entries
            if self._allowed(entry.entity_id, client_ids)
        ]
        if len(entries) == len(self.plan.entries):
            return self.plan
        # Re-rank so an entitled projection never shows gaps in the sequence.
        renumbered = [
            entry.model_copy(update={"rank": index})
            for index, entry in enumerate(entries, start=1)
        ]
        return self.plan.model_copy(update={"entries": renumbered})

    def funding_routes(
        self, entity_id: str, as_of: date, client_ids: Sequence[str] = ("*",)
    ) -> FundingRouteProjection:
        self.check_as_of(as_of)
        self._require_entitlement(entity_id, client_ids)
        return self.routes[entity_id]

    def questions_for(self, conversation_id: str) -> List[Any]:
        return list(self.questions.get(conversation_id, []))

    # -- aggregate projection ---------------------------------------------
    def conversation_summary(self, item: ConversationCandidate) -> Dict[str, Any]:
        """The row the workbench needs, without the full decision object.

        Shipping every conversation in full would put the whole portfolio in the
        browser; the detail lives behind ``/v3/conversations/{id}``.
        """
        client_total = item.client_value.monetised_total
        bank_total = item.bank_value.direct_contribution
        return {
            "conversation_id": item.conversation_id,
            "entity_id": item.entity_id,
            "entity_name": item.entity_name,
            "sector": item.sector,
            "stakeholder_role": item.stakeholder.primary_role.value,
            "problem": item.problem.problem.value,
            "problem_label": item.problem.label,
            "primary_solution": item.solution_bundle.primary.value,
            "supporting_solutions": [
                solution.value for solution in item.solution_bundle.supporting
            ],
            "why_now": item.engagement_window.why_now,
            "trigger_supported": item.engagement_window.trigger_supported,
            "client_value_median": client_total.median if client_total else None,
            "client_value_monetised": client_total is not None,
            "bank_value_median": bank_total.median if bank_total else None,
            "bank_value_status": item.bank_value.status,
            "selection_stability": item.policy_rank.selection_stability,
            "weekly_rank": item.policy_rank.weekly_rank,
            "client_frontier_member": item.pareto_status.client_frontier_member,
            "portfolio_frontier_member": item.pareto_status.portfolio_frontier_member,
            "action": item.action.value,
            "eligibility": item.eligibility.value,
            "evidence_tiers": [tier.value for tier in item.evidence_tiers],
            "freshness_days": max(
                0, (self.as_of - item.as_of).days
            ),
            "interval_width": (
                round(
                    (
                        item.solution_estimates[0].amount_interval.upper
                        - item.solution_estimates[0].amount_interval.lower
                    )
                    / max(item.solution_estimates[0].amount_interval.median, 1.0),
                    4,
                )
                if item.solution_estimates[0].amount_interval
                else None
            ),
            "assumption_load": len(item.solution_estimates[0].assumptions)
            + len(item.client_value.assumptions),
            "calibration_status": item.solution_estimates[0].calibration_status,
        }

    def decision_twin(
        self, as_of: date, week_start: date, client_ids: Sequence[str] = ("*",)
    ) -> Dict[str, Any]:
        self.check_as_of(as_of)
        conversations = self.conversations(as_of, client_ids)
        allowed = {
            entity_id
            for entity_id in self.twins
            if self._allowed(entity_id, client_ids)
        }
        return {
            "metadata": self.metadata,
            "coverage_plan": self.coverage_plan(as_of, week_start, client_ids).model_dump(
                mode="json"
            ),
            "conversation_count": len(conversations),
            "conversation_summaries": [
                self.conversation_summary(item) for item in conversations
            ],
            "client_index": [
                {
                    "entity_id": entity_id,
                    "entity_name": self.twins[entity_id].entity_name,
                    "sector": self.twins[entity_id].sector,
                    "supported_domain_count": self.twins[entity_id].supported_domain_count,
                    "claim_count": self.twins[entity_id].claim_count,
                    "approved_claim_count": self.twins[entity_id].approved_claim_count,
                    "evidence_gaps": len(self.twins[entity_id].evidence_gaps),
                    "change_digest_items": len(self.digests[entity_id].items),
                }
                for entity_id in sorted(allowed)
            ],
            "evidence_coverage": self.evidence_coverage,
            "policy": self.policy,
            "validation": self.validation,
            "release": self.release,
            "event_topics": self.events_store.counts_by_topic(),
            "detail_routes": {
                "conversation": "/v3/conversations/{conversation_id}?as_of=",
                "business_twin": "/v3/clients/{client_id}/business-twin?as_of=",
                "business_graph": "/v3/clients/{client_id}/business-graph?as_of=",
                "change_digest": "/v3/clients/{client_id}/change-digest?as_of=&since=",
                "funding_routes": "/v3/funding-routes/{client_id}?as_of=",
            },
        }


repository = FixtureV31Repository()
