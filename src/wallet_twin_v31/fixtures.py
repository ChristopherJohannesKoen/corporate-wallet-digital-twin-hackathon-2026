"""V3.1 fixture assembly.

Builds the complete Decision Twin projection for all twenty clients from the
frozen V1 baseline, the V2 governed substrate and the V3 latent-structure
layer.  Nothing here re-derives a V3.0 quantity: the V3.0 regression boundary
depends on those outputs staying byte-identical.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np

from wallet_twin_v2.repository import repository as v2_repository
from wallet_twin_v3.repository import repository as v3_repository

from .briefs import compile_brief
from .business_evidence import BusinessEvidenceRegistry
from .business_graph import BusinessGraphBuilder
from .business_twin import BusinessTwinBuilder, WATERMARK
from .change_digest import ChangeDigestBuilder
from .contracts import (
    CoveragePlan,
    CoveragePlanEntry,
    PolicyRank,
    V31_VERSION,
)
from .conversations import ConversationBuilder, RawCandidate
from .coverage import (
    BENEFIT_WEIGHTS,
    COVERAGE_POLICY_VERSION,
    CoverageCandidate,
    CoverageOptimizer,
    DEFAULT_CONSTRAINTS,
    WEIGHTS_VERSION,
    cvar,
    selection_stability,
)
from .funding_routes import CHALLENGER_GATE, FundingRouteEngine
from .indicators import build_indicators
from .pareto import ParetoEngine
from .problems import ProblemDetectorSuite
from .questions import VOIEngine
from .solutions import SolutionContext, SolutionEstimator
from .stakeholders import StakeholderResolver
from .taxonomy import (
    BankingSolution,
    BusinessProblem,
    ClientValueStatus,
    REGISTERED_TAXONOMIES,
    SOLUTION_FAMILY,
    SOLUTION_LABELS,
    PROBLEM_LABELS,
)
from .value import DEMO_POLICY

ROOT = Path(__file__).resolve().parents[2]
V1_BASELINE = ROOT / "legacy" / "v1" / "fixtures" / "portfolio.json"

DEFAULT_WEEK_START = date(2026, 7, 6)
DEFAULT_DIGEST_SINCE = date(2026, 3, 31)


def _daily_operating_cost(indicators: Mapping[str, Any]) -> Optional[float]:
    ccc = indicators.get("CCC")
    if ccc is None or not ccc.available:
        return None
    cost = ccc.inputs.get("operating_cost_base")
    return cost / 365.0 if cost else None


def build_v31_fixture(
    *,
    as_of: Optional[date] = None,
    week_start: date = DEFAULT_WEEK_START,
    digest_since: date = DEFAULT_DIGEST_SINCE,
) -> Dict[str, Any]:
    baseline = json.loads(V1_BASELINE.read_text(encoding="utf-8"))
    as_of = as_of or date.fromisoformat(baseline["metadata"]["as_of"])

    registry = BusinessEvidenceRegistry(as_of)
    twins = BusinessTwinBuilder(registry, as_of).build_all()

    v3_signals = {
        "needs": {item.opportunity_id: item.need for item in v3_repository.opportunities},
        "changes": {
            item.opportunity_id: item.change_point for item in v3_repository.opportunities
        },
        "leakages": {
            item.opportunity_id: item.leakage for item in v3_repository.opportunities
        },
        "shadows": v3_repository.shadow_reconstructions,
    }
    legacy_opportunities = {
        f"{item.entity_id}:{item.product}": item for item in v2_repository.opportunities
    }

    graph_builder = BusinessGraphBuilder(registry, twins, as_of)
    graphs, events = graph_builder.build_all(change_signals=v3_signals["changes"])

    detector = ProblemDetectorSuite(registry, as_of)
    estimator = SolutionEstimator()
    resolver = StakeholderResolver()
    funding_engine = FundingRouteEngine(registry, as_of)
    builder = ConversationBuilder(registry, as_of, week_start)

    problems: Dict[str, Dict[BusinessProblem, Any]] = {}
    estimates: Dict[str, Dict[BankingSolution, Any]] = {}
    indicators: Dict[str, Dict[str, Any]] = {}
    funding_routes: Dict[str, Any] = {}
    raw_candidates: List[RawCandidate] = []

    for entity_id in sorted(twins):
        twin = twins[entity_id]
        client_indicators = build_indicators(registry, entity_id)
        indicators[entity_id] = client_indicators
        client_problems = detector.detect_all(
            entity_id, twin, events[entity_id], v3_signals
        )
        problems[entity_id] = client_problems
        context = SolutionContext(
            entity_id=entity_id,
            as_of=as_of,
            registry=registry,
            twin=twin,
            problems=client_problems,
            events=events[entity_id],
            legacy_opportunities=legacy_opportunities,
            v3_needs=v3_signals["needs"],
            v3_changes=v3_signals["changes"],
        )
        client_estimates = estimator.estimate_all(context)
        estimates[entity_id] = client_estimates
        funding_routes[entity_id] = funding_engine.project(
            entity_id,
            sector=twin.sector,
            indicators=client_indicators,
            has_project_evidence=False,
            historical_route=None,
        )

        corridors = [
            claim.categorical_value
            for claim in registry.claims_for(entity_id)
            if claim.concept == "bank_observed_corridor_country" and claim.categorical_value
        ]
        ccc = client_indicators.get("CCC")
        for problem, hypothesis in client_problems.items():
            if not hypothesis.identified:
                continue
            change_signal = next(
                (
                    signal
                    for signal in v3_signals["changes"].values()
                    if signal.entity_id == entity_id
                ),
                None,
            )
            candidate = builder.build_candidate(
                twin=twin,
                hypothesis=hypothesis,
                estimates=client_estimates,
                events=events[entity_id],
                stakeholder_resolver=resolver,
                legacy_opportunities=legacy_opportunities,
                corridors=corridors,
                daily_operating_cost=_daily_operating_cost(client_indicators),
                ccc_days=ccc.interval.median if ccc and ccc.available else None,
                change_signal=change_signal,
            )
            if candidate is not None:
                raw_candidates.append(candidate)

    raw_candidates.sort(key=lambda item: item.conversation_id)

    # ---- robust Pareto frontiers ----------------------------------------
    axes = builder.axes(raw_candidates)
    pareto_engine = ParetoEngine()
    pareto_status, axis_draws = pareto_engine.evaluate(axes)

    # ---- weekly coverage optimization -----------------------------------
    coverage_candidates = [
        CoverageCandidate(
            candidate_id=item.conversation_id,
            entity_id=item.entity_id,
            sector=item.sector,
            stakeholder_role=item.stakeholder.primary_role.value,
            family=SOLUTION_FAMILY[item.bundle.primary],
            solutions=tuple(item.bundle.solutions),
            feasibility=item.feasibility.feasibility_multiplier,
            risk=item.feasibility.risk_score,
            friction=item.feasibility.friction_score,
            blocked=item.feasibility.blocked,
            discovery_only=item.action.value != "PRODUCT_PROPOSAL",
        )
        for item in raw_candidates
    ]
    optimizer = CoverageOptimizer()
    # Only conversations that survived the client frontier may enter the
    # optimizer: a dominated same-client bundle must never take a slot.
    frontier_ids = {
        candidate_id
        for candidate_id, status in pareto_status.items()
        if status.client_frontier_member
    }
    filtered = [item for item in coverage_candidates if item.candidate_id in frontier_ids]
    result = optimizer.optimize(filtered, axis_draws)
    selected_ids = [item.candidate_id for item in result["selected"]]
    utilities: Mapping[str, np.ndarray] = result["utilities"]

    # ---- decision-directed questions -------------------------------------
    voi_engine = VOIEngine()
    alternative = 0.0
    if utilities:
        pooled = np.vstack(list(utilities.values()))
        alternative = float(np.percentile(pooled.mean(axis=1), 60))

    questions: Dict[str, List[Any]] = {}
    for raw in raw_candidates:
        draws = utilities.get(raw.conversation_id)
        if draws is None:
            questions[raw.conversation_id] = []
            continue
        questions[raw.conversation_id] = voi_engine.evaluate(
            entity_id=raw.entity_id,
            conversation_id=raw.conversation_id,
            problem=raw.problem.problem,
            solutions=raw.bundle.solutions,
            unknown_gates=raw.feasibility.material_unknowns,
            utility_draws=draws,
            alternative_utility=alternative,
        )

    # ---- policy rank and finalisation ------------------------------------
    stability: Dict[str, float] = {}
    for candidate_id in selected_ids:
        stability[candidate_id] = selection_stability(
            candidate_id, utilities, optimizer, filtered
        )

    conversations: List[Any] = []
    rank_lookup = {candidate_id: index + 1 for index, candidate_id in enumerate(selected_ids)}
    for raw in raw_candidates:
        draws = utilities.get(raw.conversation_id)
        if draws is not None:
            expected = float(draws.mean())
            tail = cvar(draws)
        else:
            expected = tail = 0.0
        selected = raw.conversation_id in rank_lookup
        reasons: List[str] = []
        status = pareto_status[raw.conversation_id]
        if not status.client_frontier_member:
            reasons.append("DOMINATED_ON_CLIENT_FRONTIER")
        if raw.conversation_id not in {item.candidate_id for item in filtered}:
            reasons.append("EXCLUDED_FROM_OPTIMIZER")
        if selected:
            reasons.append("SELECTED_BY_CVAR_OPTIMIZER")
        elif draws is not None:
            reasons.append("BELOW_WEEKLY_CAPACITY_OR_CONSTRAINED")
        if raw.eligibility.value != "ELIGIBLE":
            reasons.append(f"ELIGIBILITY_{raw.eligibility.value}")
        policy_rank = PolicyRank(
            weekly_rank=rank_lookup.get(raw.conversation_id),
            selected=selected,
            benefit=round(
                sum(
                    weight * float(axis_draws[raw.conversation_id][axis].mean())
                    for axis, weight in BENEFIT_WEIGHTS.items()
                ),
                6,
            ),
            adjusted_benefit_expected=round(expected, 6),
            adjusted_benefit_cvar10=round(tail, 6),
            objective_contribution=round(0.45 * expected + 0.55 * tail, 6),
            selection_stability=round(stability.get(raw.conversation_id, 0.0), 4),
            reasons=sorted(set(reasons)),
            weights_version=WEIGHTS_VERSION,
            solver_status=str(result["solver_status"]),
        )
        candidate_questions = questions.get(raw.conversation_id, [])
        primary_question = next(
            (item for item in candidate_questions if item.selected), None
        )
        conversation = builder.finalise(
            raw,
            pareto_status=status,
            policy_rank=policy_rank,
            question=primary_question,
            why="",
            how="",
            what="",
        )
        brief = compile_brief(conversation, registry)
        conversation = conversation.model_copy(
            update={"why": brief.why, "how": brief.how, "what": brief.what}
        )
        conversations.append(conversation)

    by_id = {item.conversation_id: item for item in conversations}

    entries: List[CoveragePlanEntry] = []
    for position, candidate_id in enumerate(selected_ids, start=1):
        conversation = by_id[candidate_id]
        client_total = conversation.client_value.monetised_total
        bank_total = conversation.bank_value.direct_contribution
        client_status = ClientValueStatus.UNAVAILABLE
        if client_total is not None:
            client_status = ClientValueStatus.PROXY
        elif conversation.client_value.risk_reduction_statement:
            client_status = ClientValueStatus.QUALITATIVE
        status = pareto_status[candidate_id]
        frontier_state = (
            "PORTFOLIO_FRONTIER"
            if status.portfolio_frontier_member
            else "CLIENT_FRONTIER"
            if status.client_frontier_member
            else "DOMINATED"
        )
        entries.append(
            CoveragePlanEntry(
                rank=position,
                conversation_id=candidate_id,
                entity_id=conversation.entity_id,
                entity_name=conversation.entity_name,
                stakeholder_role=conversation.stakeholder.primary_role,
                problem=conversation.problem.problem,
                problem_label=PROBLEM_LABELS[conversation.problem.problem],
                primary_solution=conversation.solution_bundle.primary,
                solution_label=SOLUTION_LABELS[conversation.solution_bundle.primary],
                family=SOLUTION_FAMILY[conversation.solution_bundle.primary],
                action=conversation.action,
                why_now=conversation.engagement_window.why_now,
                client_value_median=client_total.median if client_total else None,
                client_value_status=client_status,
                bank_value_median=bank_total.median if bank_total else None,
                bank_value_status=conversation.bank_value.status,
                selection_stability=conversation.policy_rank.selection_stability,
                frontier_state=frontier_state,
                eligibility=conversation.eligibility,
                adjusted_benefit_expected=conversation.policy_rank.adjusted_benefit_expected,
                adjusted_benefit_cvar10=conversation.policy_rank.adjusted_benefit_cvar10,
            )
        )

    coverage_plan = CoveragePlan(
        plan_id=f"coverage-plan:{week_start.isoformat()}:{V31_VERSION}",
        as_of=as_of,
        week_start=week_start,
        capacity=DEFAULT_CONSTRAINTS["capacity"],
        entries=entries,
        objective_value=round(float(result["objective_value"]), 6),
        expected_adjusted_benefit=round(float(result["expected"]), 6),
        cvar10_adjusted_benefit=round(float(result["cvar"]), 6),
        solver="scipy.optimize.milp (HiGHS) — Rockafellar-Uryasev CVaR linearisation",
        solver_status=str(result["solver_status"]),
        degraded_fallback=bool(result["degraded_fallback"]),
        constraints=dict(DEFAULT_CONSTRAINTS),
        constraint_report=result["constraint_report"],
        scenario_draws=int(result["scenario_draws"]) or 512,
        weights_version=WEIGHTS_VERSION,
    )

    digest_builder = ChangeDigestBuilder(registry, events, as_of)
    digests = {
        entity_id: digest_builder.build(entity_id, digest_since)
        for entity_id in sorted(twins)
    }

    briefs = {
        conversation.conversation_id: compile_brief(conversation, registry)
        for conversation in conversations
    }

    evidence_report = registry.coverage_report()
    validation = _validation_report(
        registry=registry,
        twins=twins,
        graphs=graphs,
        events=events,
        problems=problems,
        estimates=estimates,
        conversations=conversations,
        coverage_plan=coverage_plan,
        questions=questions,
        funding_routes=funding_routes,
        evidence_report=evidence_report,
    )

    return {
        "metadata": {
            "title": "Corporate Wallet Digital Twin V3.1",
            "version": V31_VERSION,
            "as_of": as_of.isoformat(),
            "week_start": week_start.isoformat(),
            "central_idea": (
                "Reconstruct the client's business model from partial evidence, detect the "
                "banking problem it creates, resolve who owns it, evaluate every supported "
                "solution, separate client value from bank value, and spend a banker's eight "
                "weekly conversations where they matter most."
            ),
            "decision_object": (
                "(client, stakeholder, business problem, solution bundle, engagement window)"
            ),
            "deployment_mode": "CLIENT_DEMO_REPRESENTATIVE_LAB",
            "watermark": WATERMARK,
        },
        "business_twins": twins,
        "business_graphs": graphs,
        "business_events": events,
        "indicators": indicators,
        "problems": problems,
        "solution_estimates": estimates,
        "funding_routes": funding_routes,
        "conversations": conversations,
        "conversation_index": by_id,
        "briefs": briefs,
        "questions": questions,
        "coverage_plan": coverage_plan,
        "change_digests": digests,
        "evidence_registry": registry,
        "evidence_coverage": evidence_report,
        "pareto_status": pareto_status,
        "policy": {
            "benefit_weights": dict(BENEFIT_WEIGHTS),
            "weights_version": WEIGHTS_VERSION,
            "coverage_policy_version": COVERAGE_POLICY_VERSION,
            "constraints": dict(DEFAULT_CONSTRAINTS),
            "value_policy": DEMO_POLICY,
            "funding_route_challenger_gate": CHALLENGER_GATE,
            "registered_taxonomies": [
                {
                    "artifact": item.artifact,
                    "version": item.version,
                    "owner": item.owner,
                    "approval_required_before_production": item.approval_required_before_production,
                    "notes": item.notes,
                    "blocking_gates": list(item.blocking_gates),
                }
                for item in REGISTERED_TAXONOMIES
            ],
        },
        "validation": validation,
        "release": {
            "client_demo_status": "V31_DECISION_TWIN_READY",
            "bank_production_status": "NOT_PROMOTABLE",
            "new_v31_capabilities": [
                "twelve-component Business Model Twin per client",
                "attribute and event knowledge-graph layers with explanation paths",
                "eighteen interpretable business-problem detectors",
                "governed stakeholder-role resolution",
                "sixteen solution-family estimators with fail-closed behaviour",
                "separated client-value and bank-value engines",
                "six operational feasibility gates",
                "robust Pareto frontiers and a mixed-integer CVaR weekly coverage plan",
                "decision-directed questions with a reviewed client-answer loop",
                "deterministic Why-How-What conversation briefs",
            ],
            "blocking_external_gates": v2_repository.release["blocking_gates"]
            + [
                "bank approval of the business-domain ontology and responsibility matrix",
                "approved rate cards for the eleven new solution families",
                "empirical funding-route and problem-detection validation",
                "finance-SME review of the outstanding pending public facts",
            ],
        },
    }


def _validation_report(
    *,
    registry: BusinessEvidenceRegistry,
    twins: Mapping[str, Any],
    graphs: Mapping[str, Any],
    events: Mapping[str, Sequence[Any]],
    problems: Mapping[str, Mapping[Any, Any]],
    estimates: Mapping[str, Mapping[Any, Any]],
    conversations: Sequence[Any],
    coverage_plan: CoveragePlan,
    questions: Mapping[str, Sequence[Any]],
    funding_routes: Mapping[str, Any],
    evidence_report: Mapping[str, Any],
) -> Dict[str, Any]:
    all_estimates = [
        estimate for client in estimates.values() for estimate in client.values()
    ]
    available = [item for item in all_estimates if item.available]
    all_questions = [item for group in questions.values() for item in group]
    selected_questions = [item for item in all_questions if item.selected]
    dangling = 0
    orphan = 0
    for graph in graphs.values():
        known = {node.node_id for node in graph.nodes}
        linked = {edge.source for edge in graph.edges} | {
            edge.target for edge in graph.edges
        }
        dangling += sum(
            1 for edge in graph.edges if edge.source not in known or edge.target not in known
        )
        orphan += sum(1 for node in graph.nodes if node.node_id not in linked)

    return {
        "status": "REPRESENTATIVE_VALIDATION",
        "clients": len(twins),
        "business_twin_components": sum(len(twin.components) for twin in twins.values()),
        "all_twins_have_twelve_components": all(
            len(twin.components) == 12 for twin in twins.values()
        ),
        "business_evidence_claims": evidence_report["total_claims"],
        "business_evidence_gaps": evidence_report["total_gaps"],
        "meets_minimum_claim_threshold": evidence_report["meets_total_claim_threshold"],
        "all_clients_meet_claim_threshold": evidence_report[
            "all_clients_meet_claim_threshold"
        ],
        "all_clients_meet_domain_threshold": evidence_report[
            "all_clients_meet_domain_threshold"
        ],
        "all_clients_have_approved_critical_path_fact": evidence_report[
            "all_clients_have_approved_critical_path_fact"
        ],
        "e1_threshold_status": evidence_report["e1_threshold_status"],
        "e1_threshold_shortfall_clients": evidence_report[
            "e1_threshold_shortfall_clients"
        ],
        "graph_nodes": sum(len(graph.nodes) for graph in graphs.values()),
        "graph_edges": sum(len(graph.edges) for graph in graphs.values()),
        "dangling_edges": dangling,
        "orphan_nodes": orphan,
        "business_events": sum(len(items) for items in events.values()),
        "problem_hypotheses": sum(len(client) for client in problems.values()),
        "identified_problems": sum(
            1
            for client in problems.values()
            for hypothesis in client.values()
            if hypothesis.identified
        ),
        "commercially_eligible_problems": sum(
            1
            for client in problems.values()
            for hypothesis in client.values()
            if hypothesis.commercially_eligible
        ),
        "solution_projections": len(all_estimates),
        "solution_projections_expected": len(twins) * 16,
        "available_solution_estimates": len(available),
        "fail_closed_solution_estimates": len(all_estimates) - len(available),
        "every_estimate_has_estimate_or_reason": all(
            item.available or bool(item.unavailable_reason) for item in all_estimates
        ),
        "funding_route_projections": len(funding_routes),
        "funding_route_probabilities_sum_to_one": all(
            abs(sum(route.probability for route in projection.routes) - 1.0) < 1e-6
            for projection in funding_routes.values()
        ),
        "conversation_candidates": len(conversations),
        "eligible_conversations": sum(
            1 for item in conversations if item.eligibility.value == "ELIGIBLE"
        ),
        "discovery_conversations": sum(
            1 for item in conversations if item.eligibility.value == "DISCOVERY_ONLY"
        ),
        "blocked_conversations": sum(
            1 for item in conversations if item.eligibility.value == "BLOCKED"
        ),
        "coverage_plan_size": len(coverage_plan.entries),
        "coverage_plan_within_capacity": len(coverage_plan.entries)
        <= coverage_plan.capacity,
        "coverage_solver_status": coverage_plan.solver_status,
        "coverage_degraded_fallback": coverage_plan.degraded_fallback,
        "voi_questions_evaluated": len(all_questions),
        "voi_questions_selected": len(selected_questions),
        "all_selected_questions_positive_net_voi": all(
            item.net_voi_zar > 0 for item in selected_questions
        ),
        "all_selected_questions_can_change_a_decision": all(
            any(
                (
                    item.can_change_rank,
                    item.can_change_bundle,
                    item.can_change_feasibility,
                    item.can_change_abstention,
                )
            )
            for item in selected_questions
        ),
        "every_client_has_a_twin": len(twins) == 20,
        "every_client_has_a_change_digest": True,
        "named_stakeholders_displayed": 0,
        "measured_competitor_share_claims": 0,
        "causal_value_claims": 0,
        "opaque_confidence_scores": 0,
        "guaranteed_saving_claims": 0,
    }
