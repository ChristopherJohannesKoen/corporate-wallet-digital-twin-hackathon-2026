"""Dynamic Business Knowledge Graph — attribute and event layers.

The V3 corridor-only Treasury graph is replaced by two temporal layers:

* **Attribute layer** — relatively stable structure: client, legal entities,
  subsidiaries, SPVs, projects, geographies, currencies, commodities,
  stakeholder roles, business-model components and banking solutions.
* **Event layer** — time-sensitive facts: maturities, tenders, projects,
  capex, strategy changes, payment shifts, market regimes and leakage signals.

The attribute/event separation and graph-based retrieval pattern follows
FinKario (https://aclanthology.org/2026.acl-long.446/).  Its investment-
prediction results are *not* treated as validation of this banking use case;
only the representational idea is borrowed.

Every edge carries valid time, availability time, claim class, evidence tier,
approval state, source evidence and the transformation that produced it.  Only
approved or explicitly scenario-labelled edges may appear in a banker-facing
explanation.  Ownership is never inferred from name similarity.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from wallet_twin_v2.contracts import ApprovalStatus, ClaimClass, EvidenceTier

from .business_evidence import BusinessEvidenceRegistry
from .contracts import (
    BusinessEvent,
    BusinessGraphSnapshot,
    BusinessTwinSnapshot,
    ExplanationPath,
    ExplanationStep,
    GraphEdge,
    GraphLayer,
    GraphNode,
    NodeType,
    ReviewState,
    SignedInterval,
)
from .taxonomy import (
    BankingSolution,
    BusinessProblem,
    BusinessTwinDomain as D,
    DOMAIN_LABELS,
    PROBLEM_LABELS,
    RESPONSIBILITY_MATRIX,
    SOLUTION_LABELS,
    StakeholderRole,
)

ROOT = Path(__file__).resolve().parents[2]
V1_BASELINE = ROOT / "legacy" / "v1" / "fixtures" / "portfolio.json"

GRAPH_VERSION = "v31-business-graph-3.1.0"
ONTOLOGY_VERSION = "v31-graph-ontology-3.1.0"

IDENTITY_RESOLUTION_STATUS = (
    "GLEIF_AND_REGISTRY_RESOLUTION_REGISTERED_NOT_EXECUTED — parent/SPV edges require "
    "deterministic identifier matching plus human review; name similarity alone is "
    "never sufficient"
)
MEASUREMENT_STATUS = (
    "SYN_BANK_SIMULATION_TOPOLOGY_AND_AUDITED_PUBLIC_FACTS — reconstructed structure is "
    "not an observed client treasury graph"
)

COMMODITY_SECTORS: Mapping[str, Tuple[str, ...]] = {
    "mining": ("Iron ore", "Copper", "Platinum group metals", "Gold"),
}


def _load_clients() -> Dict[str, Dict[str, Any]]:
    baseline = json.loads(V1_BASELINE.read_text(encoding="utf-8"))
    return {item["entity_id"]: item for item in baseline["clients"]}


class BusinessGraphBuilder:
    version = GRAPH_VERSION

    def __init__(
        self,
        registry: BusinessEvidenceRegistry,
        twins: Mapping[str, BusinessTwinSnapshot],
        as_of: date,
    ) -> None:
        self.registry = registry
        self.twins = twins
        self.as_of = as_of
        self.clients = _load_clients()

    # -- node/edge helpers -------------------------------------------------
    def _node(
        self,
        entity_id: str,
        layer: GraphLayer,
        node_type: NodeType,
        key: str,
        label: str,
        *,
        attributes: Optional[Dict[str, Any]] = None,
        claim_class: ClaimClass = ClaimClass.OBSERVED,
        tier: EvidenceTier = EvidenceTier.E0,
        review_state: ReviewState = ReviewState.DETERMINISTIC,
        valid_from: Optional[date] = None,
        available_date: Optional[date] = None,
    ) -> GraphNode:
        return GraphNode(
            node_id=f"{layer.value.lower()}:{node_type.value.lower()}:{entity_id}:{key}",
            layer=layer,
            node_type=node_type,
            label=label,
            entity_id=entity_id,
            attributes=attributes or {},
            valid_from=valid_from,
            available_date=available_date or self.as_of,
            claim_class=claim_class,
            evidence_tier=tier,
            review_state=review_state,
        )

    def _edge(
        self,
        entity_id: str,
        layer: GraphLayer,
        edge_type: str,
        source: str,
        target: str,
        *,
        weight: Optional[float] = None,
        claim_ids: Optional[Sequence[str]] = None,
        claim_class: ClaimClass = ClaimClass.OBSERVED,
        tier: EvidenceTier = EvidenceTier.E0,
        approval: ApprovalStatus = ApprovalStatus.APPROVED,
        review_state: ReviewState = ReviewState.DETERMINISTIC,
        artifact: str = GRAPH_VERSION,
        semantics: str = "deterministic transformation of bank-observed aggregates",
        valid_from: Optional[date] = None,
        available_date: Optional[date] = None,
    ) -> GraphEdge:
        # A stable digest, not ``hash()``: Python randomises string hashing per
        # process, which would make the same ``as_of`` produce different edge
        # ids on every run and break point-in-time reproducibility.
        suffix = f"{source}->{target}:{edge_type}"
        digest = hashlib.sha256(suffix.encode("utf-8")).hexdigest()[:16]
        return GraphEdge(
            edge_id=f"edge:{entity_id}:{digest}",
            layer=layer,
            edge_type=edge_type,
            source=source,
            target=target,
            weight=weight,
            valid_from=valid_from,
            available_date=available_date or self.as_of,
            claim_class=claim_class,
            evidence_tier=tier,
            approval_status=approval,
            source_claim_ids=list(claim_ids or []),
            source_fact_ids=[
                claim.legacy_fact_id
                for claim_id in (claim_ids or [])
                if (claim := self.registry.get(claim_id)) is not None
                and claim.legacy_fact_id
            ],
            transformation_artifact=artifact,
            confidence_semantics=semantics,
            review_state=review_state,
        )

    # -- attribute layer ---------------------------------------------------
    def _attribute_layer(
        self, entity_id: str
    ) -> Tuple[List[GraphNode], List[GraphEdge]]:
        client = self.clients[entity_id]
        twin = self.twins[entity_id]
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []

        client_node = self._node(
            entity_id,
            GraphLayer.ATTRIBUTE,
            NodeType.CLIENT,
            "root",
            client["entity_name"],
            attributes={"sector": client["sector"]},
        )
        nodes.append(client_node)

        legal_node = self._node(
            entity_id,
            GraphLayer.ATTRIBUTE,
            NodeType.LEGAL_ENTITY,
            "primary",
            f"{client['entity_name']} (primary banked entity)",
            attributes={
                "identifier_resolution": "NOT_RESOLVED",
                "lei": None,
            },
            review_state=ReviewState.REVIEW_CANDIDATE,
        )
        nodes.append(legal_node)
        edges.append(
            self._edge(
                entity_id,
                GraphLayer.ATTRIBUTE,
                "HAS_LEGAL_ENTITY",
                client_node.node_id,
                legal_node.node_id,
                claim_class=ClaimClass.SCENARIO,
                approval=ApprovalStatus.PENDING_REVIEW,
                review_state=ReviewState.REVIEW_CANDIDATE,
                semantics=(
                    "structural placeholder; requires GLEIF/registry resolution and "
                    "human review before it may appear in an explanation"
                ),
            )
        )

        for claim in self.registry.claims_in_domain(entity_id, D.GEOGRAPHIC_EXPOSURE):
            if claim.concept != "bank_observed_corridor_country":
                continue
            country = claim.categorical_value or "Unknown"
            node = self._node(
                entity_id,
                GraphLayer.ATTRIBUTE,
                NodeType.COUNTRY,
                country.lower().replace(" ", "-"),
                country,
                available_date=claim.available_date,
            )
            nodes.append(node)
            edges.append(
                self._edge(
                    entity_id,
                    GraphLayer.ATTRIBUTE,
                    "TRADES_WITH",
                    client_node.node_id,
                    node.node_id,
                    claim_ids=[claim.claim_id],
                    approval=claim.approval_status,
                    tier=claim.tier,
                    available_date=claim.available_date,
                )
            )

        for claim in self.registry.claims_in_domain(
            entity_id, D.CURRENCY_AND_COMMODITY_EXPOSURE
        ):
            if claim.concept != "bank_observed_currency_pair":
                continue
            pair = claim.categorical_value or "Unknown"
            node = self._node(
                entity_id,
                GraphLayer.ATTRIBUTE,
                NodeType.CURRENCY,
                pair.lower().replace("/", "-"),
                pair,
                available_date=claim.available_date,
            )
            nodes.append(node)
            edges.append(
                self._edge(
                    entity_id,
                    GraphLayer.ATTRIBUTE,
                    "HAS_CURRENCY_EXPOSURE",
                    client_node.node_id,
                    node.node_id,
                    claim_ids=[claim.claim_id],
                    approval=claim.approval_status,
                    tier=claim.tier,
                    available_date=claim.available_date,
                )
            )

        for commodity in COMMODITY_SECTORS.get(client["sector"], ()):
            node = self._node(
                entity_id,
                GraphLayer.ATTRIBUTE,
                NodeType.COMMODITY,
                commodity.lower().replace(" ", "-"),
                commodity,
                claim_class=ClaimClass.SCENARIO,
                review_state=ReviewState.REVIEW_CANDIDATE,
            )
            nodes.append(node)
            edges.append(
                self._edge(
                    entity_id,
                    GraphLayer.ATTRIBUTE,
                    "HAS_COMMODITY_EXPOSURE",
                    client_node.node_id,
                    node.node_id,
                    claim_class=ClaimClass.SCENARIO,
                    approval=ApprovalStatus.APPROVED,
                    review_state=ReviewState.APPROVED,
                    semantics="representative sector exposure, not a disclosed hedge book",
                )
            )

        for component in twin.components:
            node = self._node(
                entity_id,
                GraphLayer.ATTRIBUTE,
                NodeType.BUSINESS_MODEL_COMPONENT,
                component.domain.value.lower(),
                DOMAIN_LABELS[component.domain],
                attributes={
                    "status": component.status.value,
                    "materiality": component.materiality,
                },
                claim_class=component.claim_class,
                tier=component.evidence_tier,
            )
            nodes.append(node)
            edges.append(
                self._edge(
                    entity_id,
                    GraphLayer.ATTRIBUTE,
                    "HAS_BUSINESS_COMPONENT",
                    client_node.node_id,
                    node.node_id,
                    claim_ids=component.evidence_claim_ids[:8],
                    claim_class=component.claim_class,
                    tier=component.evidence_tier,
                    semantics="Business Twin component derived from typed evidence",
                )
            )

        for role in StakeholderRole:
            node = self._node(
                entity_id,
                GraphLayer.ATTRIBUTE,
                NodeType.STAKEHOLDER_ROLE,
                role.value.lower(),
                role.value.replace("_", " ").title(),
                attributes={"named_contact_resolved": False},
                claim_class=ClaimClass.SCENARIO,
            )
            nodes.append(node)
            edges.append(
                self._edge(
                    entity_id,
                    GraphLayer.ATTRIBUTE,
                    "HAS_ROLE",
                    client_node.node_id,
                    node.node_id,
                    claim_class=ClaimClass.SCENARIO,
                    review_state=ReviewState.APPROVED,
                    semantics="governed responsibility matrix; no named individual is resolved",
                )
            )

        for solution in BankingSolution:
            nodes.append(
                self._node(
                    entity_id,
                    GraphLayer.ATTRIBUTE,
                    NodeType.BANKING_SOLUTION,
                    solution.value.lower(),
                    SOLUTION_LABELS[solution],
                    claim_class=ClaimClass.SCENARIO,
                )
            )
        return nodes, edges

    # -- event layer -------------------------------------------------------
    def derive_events(
        self,
        entity_id: str,
        *,
        change_signals: Optional[Mapping[str, Any]] = None,
    ) -> List[BusinessEvent]:
        """Derive dated business events from evidence and V3 change signals."""
        claims = self.registry.claims_for(entity_id)
        by_concept = {claim.concept: claim for claim in claims}
        events: List[BusinessEvent] = []

        maturity = by_concept.get("current_debt_maturity_window") or by_concept.get(
            "current_debt"
        )
        if maturity is not None and maturity.money_value is not None:
            # Current borrowings disclosed at a balance-sheet date fall due within
            # twelve months of that date.  If the window has already closed by
            # ``as_of`` the honest statement is that the last audited maturity
            # position has elapsed and must be re-confirmed — that is itself a
            # dated trigger, not a manufactured one.
            window_end = maturity.maturity_window_end or (
                maturity.period_end + timedelta(days=365)
            )
            elapsed = window_end <= self.as_of
            events.append(
                BusinessEvent(
                    event_key=f"event:{entity_id}:debt-maturity",
                    entity_id=entity_id,
                    event_type="DEBT_MATURITY_WINDOW_ELAPSED"
                    if elapsed
                    else "DEBT_MATURITY_WINDOW",
                    label=(
                        "The last audited current-borrowings window closed on "
                        f"{window_end.isoformat()} and no newer maturity disclosure is available"
                        if elapsed
                        else "Disclosed current borrowings fall due inside the governed horizon"
                    ),
                    event_date=window_end,
                    available_date=maturity.available_date,
                    horizon_days=max(0, (window_end - self.as_of).days),
                    magnitude=SignedInterval(
                        lower=float(maturity.money_value or 0.0) * 0.75,
                        median=float(maturity.money_value or 0.0),
                        upper=float(maturity.money_value or 0.0) * 1.5,
                    ),
                    affected_domains=[D.FUNDING_STRUCTURE, D.LIQUIDITY_AND_BUFFER],
                    implied_problems=[
                        BusinessProblem.REFINANCING_CLIFF,
                        BusinessProblem.INTEREST_RATE_EXPOSURE,
                    ],
                    evidence_claim_ids=[maturity.claim_id],
                    claim_class=ClaimClass.IDENTIFIED_BOUND,
                    evidence_tier=maturity.tier,
                    review_state=ReviewState.APPROVED
                    if maturity.approval_status is ApprovalStatus.APPROVED
                    else ReviewState.REVIEW_CANDIDATE,
                )
            )

        trade_events = by_concept.get("bank_observed_trade_events_next_90d")
        trade_value = by_concept.get("bank_observed_trade_events_value_next_90d")
        if trade_events is not None and (trade_events.count_value or 0) > 0:
            events.append(
                BusinessEvent(
                    event_key=f"event:{entity_id}:trade-pipeline-90d",
                    entity_id=entity_id,
                    event_type="TRADE_EVENT_PIPELINE",
                    label=(
                        f"{trade_events.count_value} bank-observed trade events are dated "
                        "inside the next 90 days"
                    ),
                    event_date=self.as_of + timedelta(days=45),
                    available_date=self.as_of,
                    horizon_days=90,
                    magnitude=SignedInterval(
                        lower=float(trade_value.money_value or 0.0) * 0.8,
                        median=float(trade_value.money_value or 0.0),
                        upper=float(trade_value.money_value or 0.0) * 1.2,
                    )
                    if trade_value is not None
                    else None,
                    affected_domains=[D.WORKING_CAPITAL_CYCLE, D.OPERATING_MODEL],
                    implied_problems=[
                        BusinessProblem.SUPPLY_CHAIN_RISK,
                        BusinessProblem.WORKING_CAPITAL_PRESSURE,
                        BusinessProblem.GUARANTEE_OR_COLLATERAL_REQUIREMENT,
                    ],
                    evidence_claim_ids=[trade_events.claim_id],
                    claim_class=ClaimClass.OBSERVED,
                    evidence_tier=EvidenceTier.E0,
                    review_state=ReviewState.APPROVED,
                )
            )

        for product, concept in (
            ("Payments", "bank_observed_payments_yoy_change"),
            ("Collections", "bank_observed_collections_yoy_change"),
            ("Cross-border FX", "bank_observed_cross_border_fx_yoy_change"),
            ("Liquidity", "bank_observed_liquidity_yoy_change"),
            ("Trade finance", "bank_observed_trade_finance_yoy_change"),
        ):
            claim = by_concept.get(concept)
            if claim is None or claim.ratio_value is None:
                continue
            if abs(claim.ratio_value) < 0.10:
                continue
            direction = "increase" if claim.ratio_value > 0 else "decline"
            problems = (
                [BusinessProblem.WALLET_LEAKAGE, BusinessProblem.OPERATIONAL_RESILIENCE]
                if claim.ratio_value < 0
                else [BusinessProblem.TREASURY_CENTRALISATION]
            )
            events.append(
                BusinessEvent(
                    event_key=f"event:{entity_id}:flow-shift:{product.lower().replace(' ', '-')}",
                    entity_id=entity_id,
                    event_type="OBSERVED_FLOW_SHIFT",
                    label=(
                        f"Bank-observed {product} flow shows a {abs(claim.ratio_value):.0%} "
                        f"year-on-year {direction}"
                    ),
                    event_date=self.as_of,
                    available_date=self.as_of,
                    horizon_days=0,
                    affected_domains=[D.OPERATING_MODEL],
                    implied_problems=problems,
                    evidence_claim_ids=[claim.claim_id],
                    claim_class=ClaimClass.OBSERVED,
                    evidence_tier=EvidenceTier.E0,
                    review_state=ReviewState.APPROVED,
                )
            )

        for signal in (change_signals or {}).values():
            if getattr(signal, "entity_id", None) != entity_id:
                continue
            if signal.recent_peak_probability < 0.5:
                continue
            events.append(
                BusinessEvent(
                    event_key=f"event:{entity_id}:change-point:{signal.product.lower().replace(' ', '-')}",
                    entity_id=entity_id,
                    event_type="CHANGE_POINT_DETECTED",
                    label=(
                        f"Bayesian change-point filter flags a regime shift in {signal.product} "
                        f"(peak run-length reset probability {signal.recent_peak_probability:.0%})"
                    ),
                    event_date=self.as_of,
                    available_date=self.as_of,
                    horizon_days=30,
                    affected_domains=[D.OPERATING_MODEL, D.REVENUE_ENGINE],
                    implied_problems=[BusinessProblem.WALLET_LEAKAGE]
                    if signal.signed_level_shift < 0
                    else [BusinessProblem.TREASURY_CENTRALISATION],
                    evidence_claim_ids=[],
                    claim_class=ClaimClass.POSTERIOR,
                    evidence_tier=EvidenceTier.E0,
                    review_state=ReviewState.APPROVED,
                )
            )

        events.sort(key=lambda item: (item.event_date, item.event_key))
        return events

    def _event_layer(
        self, entity_id: str, events: Sequence[BusinessEvent], client_node_id: str
    ) -> Tuple[List[GraphNode], List[GraphEdge]]:
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        problem_nodes: Dict[BusinessProblem, str] = {}

        for event in events:
            node = self._node(
                entity_id,
                GraphLayer.EVENT,
                NodeType.EVENT,
                event.event_key.split(":", 2)[-1],
                event.label,
                attributes={
                    "event_type": event.event_type,
                    "event_date": event.event_date.isoformat(),
                    "horizon_days": event.horizon_days,
                },
                claim_class=event.claim_class,
                tier=event.evidence_tier,
                review_state=event.review_state,
                valid_from=event.event_date,
                available_date=event.available_date,
            )
            nodes.append(node)
            edges.append(
                self._edge(
                    entity_id,
                    GraphLayer.EVENT,
                    "HAS_EVENT",
                    client_node_id,
                    node.node_id,
                    claim_ids=event.evidence_claim_ids,
                    claim_class=event.claim_class,
                    tier=event.evidence_tier,
                    review_state=event.review_state,
                    available_date=event.available_date,
                    valid_from=event.event_date,
                )
            )
            for problem in event.implied_problems:
                if problem not in problem_nodes:
                    problem_node = self._node(
                        entity_id,
                        GraphLayer.EVENT,
                        NodeType.PROBLEM,
                        problem.value.lower(),
                        PROBLEM_LABELS[problem],
                        claim_class=ClaimClass.POSTERIOR,
                    )
                    nodes.append(problem_node)
                    problem_nodes[problem] = problem_node.node_id
                edges.append(
                    self._edge(
                        entity_id,
                        GraphLayer.EVENT,
                        "IMPLIES_PROBLEM",
                        node.node_id,
                        problem_nodes[problem],
                        claim_ids=event.evidence_claim_ids,
                        claim_class=ClaimClass.POSTERIOR,
                        tier=event.evidence_tier,
                        review_state=event.review_state,
                        semantics=(
                            "governed detector mapping from a dated event to a candidate "
                            "business problem; not a calibrated posterior"
                        ),
                        available_date=event.available_date,
                    )
                )
        return nodes, edges

    # -- assembly ----------------------------------------------------------
    def build(
        self,
        entity_id: str,
        *,
        change_signals: Optional[Mapping[str, Any]] = None,
        events: Optional[Sequence[BusinessEvent]] = None,
    ) -> Tuple[BusinessGraphSnapshot, List[BusinessEvent]]:
        attribute_nodes, attribute_edges = self._attribute_layer(entity_id)
        client_node_id = attribute_nodes[0].node_id
        derived = (
            list(events)
            if events is not None
            else self.derive_events(entity_id, change_signals=change_signals)
        )
        event_nodes, event_edges = self._event_layer(
            entity_id, derived, client_node_id
        )
        nodes = attribute_nodes + event_nodes
        edges = attribute_edges + event_edges

        # link each problem to its governed owning role and permitted solutions
        role_nodes = {
            node.label.upper().replace(" ", "_"): node.node_id
            for node in attribute_nodes
            if node.node_type is NodeType.STAKEHOLDER_ROLE
        }
        solution_nodes = {
            node.label: node.node_id
            for node in attribute_nodes
            if node.node_type is NodeType.BANKING_SOLUTION
        }
        for node in event_nodes:
            if node.node_type is not NodeType.PROBLEM:
                continue
            problem = next(
                (
                    item
                    for item in BusinessProblem
                    if PROBLEM_LABELS[item] == node.label
                ),
                None,
            )
            if problem is None:
                continue
            rule = RESPONSIBILITY_MATRIX[problem]
            role_node = role_nodes.get(rule.primary.value)
            if role_node:
                edges.append(
                    self._edge(
                        entity_id,
                        GraphLayer.EVENT,
                        "IS_OWNED_BY_ROLE",
                        node.node_id,
                        role_node,
                        claim_class=ClaimClass.SCENARIO,
                        review_state=ReviewState.APPROVED,
                        semantics="governed stakeholder responsibility matrix",
                    )
                )
            from .taxonomy import primary_solutions

            for solution in primary_solutions(problem):
                target = solution_nodes.get(SOLUTION_LABELS[solution])
                if target:
                    edges.append(
                        self._edge(
                            entity_id,
                            GraphLayer.EVENT,
                            "ADDRESSED_BY_SOLUTION",
                            node.node_id,
                            target,
                            claim_class=ClaimClass.SCENARIO,
                            review_state=ReviewState.APPROVED,
                            semantics="governed problem-solution matrix (PRIMARY mapping)",
                        )
                    )

        # Prune orphans.  A solution node that no problem reaches is not part of
        # this client's graph, and leaving it in would suggest the bank sees a
        # connection it has not established.
        linked = {edge.source for edge in edges} | {edge.target for edge in edges}
        nodes = [
            node
            for node in nodes
            if node.node_id in linked or node.node_id == client_node_id
        ]

        snapshot = BusinessGraphSnapshot(
            graph_id=f"graph:{entity_id}:{self.as_of.isoformat()}:{GRAPH_VERSION}",
            entity_id=entity_id,
            as_of=self.as_of,
            nodes=nodes,
            edges=edges,
            explanation_paths=[],
            attribute_node_count=sum(
                1 for node in nodes if node.layer is GraphLayer.ATTRIBUTE
            ),
            event_node_count=sum(1 for node in nodes if node.layer is GraphLayer.EVENT),
            review_candidate_edges=sum(
                1 for edge in edges if edge.review_state is ReviewState.REVIEW_CANDIDATE
            ),
            identity_resolution_status=IDENTITY_RESOLUTION_STATUS,
            measurement_status=MEASUREMENT_STATUS,
        )
        return snapshot, derived

    def build_all(
        self, *, change_signals: Optional[Mapping[str, Any]] = None
    ) -> Tuple[Dict[str, BusinessGraphSnapshot], Dict[str, List[BusinessEvent]]]:
        graphs: Dict[str, BusinessGraphSnapshot] = {}
        events: Dict[str, List[BusinessEvent]] = {}
        for entity_id in sorted(self.clients):
            snapshot, derived = self.build(entity_id, change_signals=change_signals)
            graphs[entity_id] = snapshot
            events[entity_id] = derived
        return graphs, events


def entitled_graph(
    snapshot: BusinessGraphSnapshot, client_ids: Sequence[str]
) -> Optional[BusinessGraphSnapshot]:
    """Remove inaccessible client nodes and every edge connected to them."""
    if "*" in client_ids or snapshot.entity_id in client_ids:
        return snapshot
    return None


def explainable_view(snapshot: BusinessGraphSnapshot) -> BusinessGraphSnapshot:
    """Drop edges that may not appear in a banker-facing explanation."""
    edges = [edge for edge in snapshot.edges if edge.explainable]
    keep = {edge.source for edge in edges} | {edge.target for edge in edges}
    nodes = [node for node in snapshot.nodes if node.node_id in keep]
    return snapshot.model_copy(
        update={
            "nodes": nodes,
            "edges": edges,
            "attribute_node_count": sum(
                1 for node in nodes if node.layer is GraphLayer.ATTRIBUTE
            ),
            "event_node_count": sum(
                1 for node in nodes if node.layer is GraphLayer.EVENT
            ),
            "review_candidate_edges": 0,
        }
    )


def build_explanation_path(
    *,
    entity_id: str,
    event: Optional[BusinessEvent],
    business_impact: str,
    impact_claim_ids: Sequence[str],
    problem: BusinessProblem,
    problem_claim_ids: Sequence[str],
    role: StakeholderRole,
    solution: BankingSolution,
    client_value_statement: str,
    client_value_supported: bool,
    bank_value_statement: str,
    bank_value_supported: bool,
) -> ExplanationPath:
    """Materialise Event -> BusinessImpact -> Problem -> Stakeholder -> Solution -> ClientValue -> BankValue."""
    unsupported: List[str] = []
    steps: List[ExplanationStep] = []

    if event is not None:
        steps.append(
            ExplanationStep(
                step="EVENT",
                node_id=f"event:event:{entity_id}:{event.event_key.split(':', 2)[-1]}",
                label=event.label,
                claim_class=event.claim_class,
                evidence_claim_ids=list(event.evidence_claim_ids),
            )
        )
        if not event.evidence_claim_ids:
            unsupported.append("EVENT")
    else:
        steps.append(
            ExplanationStep(
                step="EVENT",
                node_id=f"event:event:{entity_id}:none",
                label="No dated, supported trigger event is established",
                claim_class=ClaimClass.SCENARIO,
                evidence_claim_ids=[],
            )
        )
        unsupported.append("EVENT")

    steps.append(
        ExplanationStep(
            step="BUSINESS_IMPACT",
            node_id=f"attribute:business_model_component:{entity_id}:impact",
            label=business_impact,
            claim_class=ClaimClass.IDENTIFIED_BOUND
            if impact_claim_ids
            else ClaimClass.SCENARIO,
            evidence_claim_ids=list(impact_claim_ids),
        )
    )
    if not impact_claim_ids:
        unsupported.append("BUSINESS_IMPACT")

    steps.append(
        ExplanationStep(
            step="PROBLEM",
            node_id=f"event:problem:{entity_id}:{problem.value.lower()}",
            label=PROBLEM_LABELS[problem],
            claim_class=ClaimClass.POSTERIOR,
            evidence_claim_ids=list(problem_claim_ids),
        )
    )
    if not problem_claim_ids:
        unsupported.append("PROBLEM")

    steps.append(
        ExplanationStep(
            step="STAKEHOLDER",
            node_id=f"attribute:stakeholder_role:{entity_id}:{role.value.lower()}",
            label=role.value.replace("_", " ").title(),
            claim_class=ClaimClass.SCENARIO,
            evidence_claim_ids=[],
        )
    )
    steps.append(
        ExplanationStep(
            step="SOLUTION",
            node_id=f"attribute:banking_solution:{entity_id}:{solution.value.lower()}",
            label=SOLUTION_LABELS[solution],
            claim_class=ClaimClass.SCENARIO,
            evidence_claim_ids=[],
        )
    )
    steps.append(
        ExplanationStep(
            step="CLIENT_VALUE",
            node_id=f"attribute:client_value_component:{entity_id}:{solution.value.lower()}",
            label=client_value_statement,
            claim_class=ClaimClass.SCENARIO,
            evidence_claim_ids=[],
        )
    )
    if not client_value_supported:
        unsupported.append("CLIENT_VALUE")
    steps.append(
        ExplanationStep(
            step="BANK_VALUE",
            node_id=f"attribute:bank_value_component:{entity_id}:{solution.value.lower()}",
            label=bank_value_statement,
            claim_class=ClaimClass.SCENARIO,
            evidence_claim_ids=[],
        )
    )
    if not bank_value_supported:
        unsupported.append("BANK_VALUE")

    return ExplanationPath(
        path_id=f"path:{entity_id}:{problem.value.lower()}:{solution.value.lower()}",
        entity_id=entity_id,
        steps=steps,
        evidence_backed=not unsupported,
        unsupported_steps=unsupported,
    )
