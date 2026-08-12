"""V3.1 Corporate Banking Decision Twin test suite.

Grouped to match the plan's test plan: contracts and compatibility, evidence
and point-in-time integrity, graph, models and economics, feasibility/Pareto/
optimization, the VOI learning loop, GenAI narration and security.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from wallet_twin_v2.api import app
from wallet_twin_v2.contracts import (
    ApprovalStatus,
    ClaimClass,
    EvidenceTier,
)
from wallet_twin_v31.briefs import ClaimCompiler, compile_brief, compile_claim_pack
from wallet_twin_v31.contracts import (
    ClientValueComponent,
    FeasibilityAssessment,
    GateResult,
    InformationQuestion,
    SignedInterval,
    SolutionEstimate,
)
from wallet_twin_v31.coverage import DEFAULT_CONSTRAINTS
from wallet_twin_v31.events import DomainTopic, TOPIC_ROUTING, V31EventType
from wallet_twin_v31.pareto import CandidateAxes, ParetoEngine, robust_dominates
from wallet_twin_v31.questions import QUESTION_LIBRARY, VOIEngine
from wallet_twin_v31.repository import (
    DeltaAnalyticalRepository,
    PostgresWorkflowRepository,
    repository,
)
from wallet_twin_v31.taxonomy import (
    BankingSolution,
    BusinessProblem,
    BusinessTwinDomain,
    ClientValueStatus,
    ComponentStatus,
    ConversationAction,
    EligibilityDecision,
    FeasibilityGate,
    GateStatus,
    MappingStrength,
    PROBLEM_SOLUTION_MATRIX,
    SOLUTION_FAMILY,
    StakeholderRole,
    mapping_for,
    primary_solutions,
)

AS_OF = date(2026, 6, 30)
WEEK_START = repository.week_start
client = TestClient(app)

DEMO_HEADERS = {
    "x-user-id": "demo-validator",
    "x-user-roles": "SHADOW_OPERATOR,MODEL_VALIDATOR,EVIDENCE_REVIEWER,PRODUCT_FINANCE",
    "x-user-team": "demo-model-risk",
    "x-user-clients": "*",
    "x-user-products": "*",
}


# ---------------------------------------------------------------------------
# Contracts and compatibility
# ---------------------------------------------------------------------------
def test_taxonomies_have_the_governed_cardinality() -> None:
    assert len(StakeholderRole) == 10
    assert len(BusinessProblem) == 18
    assert len(BankingSolution) == 16
    assert len(BusinessTwinDomain) == 12
    assert len(PROBLEM_SOLUTION_MATRIX) == 18 * 16


def test_every_problem_solution_pair_is_classified() -> None:
    for problem in BusinessProblem:
        for solution in BankingSolution:
            mapping = mapping_for(problem, solution)
            assert isinstance(mapping.strength, MappingStrength)
            assert mapping.lead_time_days > 0
            if mapping.strength is not MappingStrength.INCOMPATIBLE:
                assert mapping.permitted_roles


def test_every_problem_has_at_least_one_primary_solution() -> None:
    for problem in BusinessProblem:
        assert primary_solutions(problem), problem


def test_v31_schemas_reject_undeclared_fields() -> None:
    with pytest.raises(ValidationError):
        SignedInterval(lower=0, median=1, upper=2, unexpected="nope")


def test_signed_interval_rejects_unordered_bounds() -> None:
    with pytest.raises(ValidationError):
        SignedInterval(lower=5, median=1, upper=2)


def test_events_route_to_four_domain_topics_not_one_per_event() -> None:
    assert len(V31EventType) == 12
    assert len(DomainTopic) == 4
    assert set(TOPIC_ROUTING) == set(V31EventType)
    assert len(set(TOPIC_ROUTING.values())) == 4


def test_v31_event_store_is_idempotent() -> None:
    counts = repository.events_store.counts_by_topic()
    assert sum(counts.values()) == len(repository.events_store)
    assert all(topic.value in counts for topic in DomainTopic)


def test_existing_v1_and_v3_routes_are_unchanged() -> None:
    legacy = client.get("/v1/opportunities", params={"as_of": AS_OF.isoformat()})
    assert legacy.status_code == 200
    assert legacy.json()["count"] == 100
    lab = client.get("/v3/decision-lab", params={"as_of": AS_OF.isoformat()})
    assert lab.status_code == 200
    assert len(lab.json()["opportunities"]) == 100


def test_openapi_exposes_every_new_endpoint() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    for route in (
        "/v3/decision-twin",
        "/v3/clients/{client_id}/business-twin",
        "/v3/clients/{client_id}/business-graph",
        "/v3/clients/{client_id}/change-digest",
        "/v3/conversations",
        "/v3/conversations/{conversation_id}",
        "/v3/conversations/{conversation_id}/brief",
        "/v3/coverage-plan",
        "/v3/funding-routes/{client_id}",
        "/v3/scenarios/conversations/evaluate",
        "/v3/questions/{question_id}/responses",
        "/v3/feasibility/{conversation_id}/attestations",
    ):
        assert route in paths, route
    assert not any(path.startswith("/v3.1") for path in paths)


# ---------------------------------------------------------------------------
# Evidence and point-in-time integrity
# ---------------------------------------------------------------------------
def test_all_twenty_clients_have_twelve_business_twin_components() -> None:
    assert len(repository.twins) == 20
    for twin in repository.twins.values():
        assert len(twin.components) == 12
        assert {component.domain for component in twin.components} == set(
            BusinessTwinDomain
        )


def test_every_client_meets_the_claim_and_domain_thresholds() -> None:
    report = repository.evidence_coverage
    assert report["total_claims"] >= 300
    assert report["all_clients_meet_claim_threshold"]
    assert report["all_clients_meet_domain_threshold"]
    for entity_id, row in report["per_client"].items():
        assert row["claims"] >= 15, entity_id
        assert row["domains_covered"] >= 9, entity_id


def test_every_client_has_an_approved_critical_path_fact() -> None:
    assert repository.evidence_coverage["all_clients_have_approved_critical_path_fact"]


def test_e1_shortfall_is_reported_as_an_open_gate_not_papered_over() -> None:
    report = repository.evidence_coverage
    if not report["all_clients_meet_e1_threshold"]:
        assert report["e1_threshold_status"].startswith("BLOCKING_GATE_OPEN")
        assert report["e1_threshold_shortfall_clients"]
        assert "no audited figure has been invented" in report["e1_threshold_note"]


def test_no_claim_is_used_before_its_availability_date() -> None:
    for claim in repository.registry.claims:
        assert claim.available_date <= AS_OF
        assert claim.available_date >= claim.period_end
        assert claim.source_date <= claim.available_date


def test_pending_claims_cannot_support_a_supported_component() -> None:
    for twin in repository.twins.values():
        for component in twin.components:
            if component.status is not ComponentStatus.SUPPORTED:
                continue
            for indicator in component.indicators:
                assert not indicator.pending_evidence_claim_ids


def test_unknown_components_carry_no_facts_and_say_what_is_missing() -> None:
    unknown_found = False
    for twin in repository.twins.values():
        for component in twin.components:
            if component.status is ComponentStatus.UNKNOWN:
                unknown_found = True
                assert component.facts == {}
                assert component.missing_information
    assert unknown_found, "the demo should surface at least one honest unknown"


def test_unsupported_material_domains_have_explicit_gap_records() -> None:
    for entity_id, twin in repository.twins.items():
        projects = twin.component(BusinessTwinDomain.PROJECTS_SUBSIDIARIES_SPVS)
        assert projects.status is ComponentStatus.UNKNOWN
        gaps = {gap.domain for gap in twin.evidence_gaps}
        assert BusinessTwinDomain.PROJECTS_SUBSIDIARIES_SPVS in gaps, entity_id


def test_legacy_facts_are_migrated_and_relinked_not_discarded() -> None:
    migrated = {
        claim.legacy_fact_id
        for claim in repository.registry.claims
        if claim.legacy_fact_id
    }
    assert len(migrated) >= 82


def test_indicators_never_substitute_a_default_for_a_missing_input() -> None:
    for indicators in repository.indicators.values():
        for indicator in indicators.values():
            if indicator.status is ComponentStatus.UNKNOWN:
                assert indicator.interval is None
                assert indicator.missing_inputs
            else:
                assert indicator.interval is not None


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
def test_graph_has_no_orphan_nodes_or_dangling_edges() -> None:
    for entity_id, graph in repository.graphs.items():
        known = {node.node_id for node in graph.nodes}
        linked = {edge.source for edge in graph.edges} | {
            edge.target for edge in graph.edges
        }
        for edge in graph.edges:
            assert edge.source in known and edge.target in known, entity_id
        orphans = known - linked
        assert not orphans, (entity_id, sorted(orphans)[:3])


def test_every_non_synthetic_edge_carries_lineage() -> None:
    for graph in repository.graphs.values():
        for edge in graph.edges:
            assert edge.transformation_artifact
            assert edge.confidence_semantics
            if edge.claim_class is ClaimClass.OBSERVED:
                assert edge.source_claim_ids or edge.edge_type in {
                    "HAS_BUSINESS_COMPONENT",
                    "HAS_EVENT",
                }


def test_no_named_stakeholder_appears_in_fixture_mode() -> None:
    for graph in repository.graphs.values():
        for node in graph.nodes:
            if node.node_type.value == "STAKEHOLDER_ROLE":
                assert node.attributes.get("named_contact_resolved") is False
    for conversation in repository.conversation_list:
        assert (
            conversation.stakeholder.named_contact_status
            == "NAMED_CONTACT_UNAVAILABLE_IN_DEMONSTRATION"
        )


def test_legal_entity_edges_require_reviewed_identity_resolution() -> None:
    for graph in repository.graphs.values():
        legal_edges = [
            edge for edge in graph.edges if edge.edge_type == "HAS_LEGAL_ENTITY"
        ]
        assert legal_edges
        for edge in legal_edges:
            assert edge.review_state.value == "REVIEW_CANDIDATE"
            assert not edge.explainable
        assert "GLEIF" in graph.identity_resolution_status


def test_explainable_view_drops_review_candidates() -> None:
    from wallet_twin_v31.business_graph import explainable_view

    for graph in repository.graphs.values():
        view = explainable_view(graph)
        assert view.review_candidate_edges == 0
        assert len(view.edges) <= len(graph.edges)


def test_graph_snapshots_reproduce_exactly_for_the_same_as_of() -> None:
    from wallet_twin_v31.business_graph import BusinessGraphBuilder

    builder = BusinessGraphBuilder(repository.registry, repository.twins, AS_OF)
    first, _ = builder.build("E01")
    second, _ = builder.build("E01")
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.model_dump(mode="json") == repository.graphs["E01"].model_dump(
        mode="json"
    )


def test_entitlement_filtering_removes_inaccessible_clients() -> None:
    from wallet_twin_v31.business_graph import entitled_graph

    assert entitled_graph(repository.graphs["E01"], ["E02"]) is None
    assert entitled_graph(repository.graphs["E01"], ["E01"]) is not None
    with pytest.raises(KeyError):
        repository.business_twin("E02", AS_OF, ["E01"])


# ---------------------------------------------------------------------------
# Models and economics
# ---------------------------------------------------------------------------
def test_every_client_solution_pair_returns_an_estimate_or_a_reason() -> None:
    total = 0
    for client_estimates in repository.estimates.values():
        assert len(client_estimates) == 16
        for estimate in client_estimates.values():
            total += 1
            if estimate.available:
                assert estimate.amount_interval is not None
            else:
                assert estimate.unavailable_reason
                assert estimate.amount_interval is None
    assert total == 320


def test_new_solution_families_stay_scenario_until_calibration() -> None:
    legacy = {
        BankingSolution.COLLECTIONS,
        BankingSolution.PAYMENTS,
        BankingSolution.LIQUIDITY_CASH_MANAGEMENT,
        BankingSolution.CROSS_BORDER_FX,
        BankingSolution.TRADE_FINANCE,
    }
    for client_estimates in repository.estimates.values():
        for solution, estimate in client_estimates.items():
            if solution in legacy:
                continue
            assert estimate.claim_class is ClaimClass.SCENARIO
            assert "NOT_EMPIRICALLY_CALIBRATED" in estimate.calibration_status


def test_project_finance_and_sustainable_finance_fail_closed_everywhere() -> None:
    for client_estimates in repository.estimates.values():
        for solution in (
            BankingSolution.PROJECT_FINANCE,
            BankingSolution.SUSTAINABLE_FINANCE,
            BankingSolution.MA_AND_STRATEGIC_ADVISORY,
        ):
            estimate = client_estimates[solution]
            assert not estimate.available
            assert estimate.unavailable_reason


def test_amounts_are_non_negative_and_bounds_relationships_are_declared() -> None:
    for client_estimates in repository.estimates.values():
        for estimate in client_estimates.values():
            if not estimate.available:
                continue
            assert estimate.amount_interval.lower >= 0
            if estimate.identification_bounds is not None:
                assert estimate.identification_bounds.lower >= 0
                inside = (
                    estimate.identification_bounds.lower
                    <= estimate.amount_interval.median
                    <= estimate.identification_bounds.upper
                )
                assert inside or estimate.bounds_semantics != "AMOUNT_WITHIN_BOUNDS"


def test_solution_estimate_rejects_quantities_when_unavailable() -> None:
    with pytest.raises(ValidationError):
        SolutionEstimate(
            estimate_id="x",
            entity_id="E01",
            solution=BankingSolution.PAYMENTS,
            solution_label="Payments",
            family=SOLUTION_FAMILY[BankingSolution.PAYMENTS],
            principal_quantity="TRANSACTION_WALLET",
            as_of=AS_OF,
            available=False,
            unavailable_reason="no data",
            amount_interval=SignedInterval(lower=1, median=2, upper=3),
            need_semantics="x",
            claim_class=ClaimClass.SCENARIO,
            evidence_tier=EvidenceTier.E0,
            calibration_status="x",
            model_status="x",
            estimator_version="x",
        )


def test_timing_probabilities_are_monotone_everywhere() -> None:
    for conversation in repository.conversation_list:
        window = conversation.engagement_window
        assert window.probability_30d <= window.probability_60d <= window.probability_90d


def test_funding_route_probabilities_sum_to_one_and_expose_inputs() -> None:
    assert len(repository.routes) == 20
    for projection in repository.routes.values():
        assert abs(sum(item.probability for item in projection.routes) - 1.0) < 1e-9
        assert len(projection.routes) == 6
        assert "REGISTERED_NOT_ELIGIBLE" in projection.challenger_status
        for route in projection.routes:
            assert isinstance(route.drivers, dict)


def test_funding_route_challenger_cannot_be_promoted() -> None:
    gate = repository.policy["funding_route_challenger_gate"]
    assert gate["promotion_allowed"] is False
    assert gate["required_labelled_events"] >= 500
    assert gate["required_events_per_promoted_route"] >= 50


def test_client_and_bank_value_are_reported_separately() -> None:
    for conversation in repository.conversation_list:
        assert conversation.client_value.watermark
        assert conversation.bank_value.watermark
        assert conversation.bank_value.double_count_guard
        assert conversation.bank_value.causal_incremental_value is None
        assert (
            conversation.bank_value.causal_status
            == "CAUSAL_INCREMENTAL_VALUE_WITHHELD"
        )
        if conversation.bank_value.relationship_value_3y is not None:
            assert conversation.bank_value.direct_contribution is not None


def test_risk_reduction_is_never_monetised_as_a_saving() -> None:
    risky = {
        BankingSolution.CROSS_BORDER_FX,
        BankingSolution.INTEREST_RATE_RISK_MANAGEMENT,
        BankingSolution.COMMODITY_RISK_MANAGEMENT,
    }
    seen = False
    for conversation in repository.conversation_list:
        assert conversation.client_value.guaranteed_saving_claimed is False
        for component in conversation.client_value.components:
            solution_key = component.component_id.rsplit(":", 1)[-1].upper()
            if solution_key in {item.value for item in risky}:
                seen = True
                assert component.status in (
                    ClientValueStatus.QUALITATIVE,
                    ClientValueStatus.UNAVAILABLE,
                )
                assert component.interval is None
    assert seen


def test_qualitative_client_value_cannot_carry_an_amount() -> None:
    with pytest.raises(ValidationError):
        ClientValueComponent(
            component_id="x",
            label="x",
            status=ClientValueStatus.QUALITATIVE,
            dimension="strategic",
            qualitative_statement="resilience",
            interval=SignedInterval(lower=1, median=2, upper=3),
        )


def test_bank_economics_stay_blocked_without_an_approved_rate_card() -> None:
    blocked = [
        conversation
        for conversation in repository.conversation_list
        if conversation.bank_value.status == "BLOCKED"
    ]
    for conversation in blocked:
        assert conversation.bank_value.direct_contribution is None
        assert conversation.bank_value.reason_codes


# ---------------------------------------------------------------------------
# Feasibility, Pareto and optimization
# ---------------------------------------------------------------------------
def test_all_six_gates_are_assessed_for_every_conversation() -> None:
    for conversation in repository.conversation_list:
        gates = conversation.risk_and_feasibility.gates
        assert len(gates) == 6
        assert {item.gate for item in gates} == set(FeasibilityGate)


def test_material_unknown_gates_produce_discovery_actions_only() -> None:
    for conversation in repository.conversation_list:
        assessment = conversation.risk_and_feasibility
        if assessment.material_unknowns:
            assert assessment.permitted_action is not ConversationAction.PRODUCT_PROPOSAL
            assert conversation.action is not ConversationAction.PRODUCT_PROPOSAL
            assert conversation.eligibility is not EligibilityDecision.ELIGIBLE


def test_a_failed_gate_blocks_the_bundle() -> None:
    with pytest.raises(ValidationError):
        FeasibilityAssessment(
            assessment_id="x",
            entity_id="E01",
            bundle_id="b",
            gates=[
                GateResult(
                    gate=gate,
                    status=GateStatus.FAIL if index == 0 else GateStatus.PASS,
                    required=True,
                    reason="r",
                )
                for index, gate in enumerate(FeasibilityGate)
            ],
            blocked=False,
            permitted_action=ConversationAction.PRODUCT_PROPOSAL,
            friction_score=0.1,
            risk_score=0.1,
            feasibility_multiplier=1.0,
            banker_confirmation_notice="n",
            policy_version="v",
        )


def test_demo_states_that_credit_and_compliance_need_banker_confirmation() -> None:
    for conversation in repository.conversation_list:
        notice = conversation.risk_and_feasibility.banker_confirmation_notice
        assert "banker confirmation" in notice.lower()


def test_risk_and_friction_are_separate_dimensions() -> None:
    pairs = {
        (
            conversation.risk_and_feasibility.risk_score,
            conversation.risk_and_feasibility.friction_score,
        )
        for conversation in repository.conversation_list
    }
    assert len({item[0] for item in pairs}) > 1
    assert any(risk != friction for risk, friction in pairs)


def test_robust_dominance_is_reproducible_from_common_draws() -> None:
    axes = [
        CandidateAxes("a", "E01", "p1", 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.1, 0.1, 1.0),
        CandidateAxes("b", "E01", "p1", 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.8, 0.8, 1.0),
    ]
    engine = ParetoEngine(draws=256)
    first, draws_one = engine.evaluate(axes)
    second, draws_two = engine.evaluate(axes)
    assert first["a"].model_dump() == second["a"].model_dump()
    assert np.allclose(draws_one["a"]["need"], draws_two["a"]["need"])
    dominates, share = robust_dominates(draws_one["a"], draws_one["b"])
    assert dominates and share >= 0.80
    assert first["a"].client_frontier_member
    assert not first["b"].client_frontier_member


def test_no_dominated_same_client_bundle_enters_the_weekly_plan() -> None:
    for entry in repository.plan.entries:
        status = repository.pareto_status[entry.conversation_id]
        assert status.client_frontier_member
        assert not status.dominated_by


def test_weekly_plan_respects_capacity_and_every_concentration_constraint() -> None:
    plan = repository.plan
    assert len(plan.entries) <= plan.capacity == DEFAULT_CONSTRAINTS["capacity"] == 8
    report = plan.constraint_report
    assert max(report["per_client"].values()) <= DEFAULT_CONSTRAINTS["max_per_client"]
    assert (
        max(report["per_client_role"].values())
        <= DEFAULT_CONSTRAINTS["max_per_client_role"]
    )
    assert (
        max(report["per_solution_family"].values())
        <= DEFAULT_CONSTRAINTS["max_per_solution_family"]
    )
    assert max(report["per_sector"].values()) <= DEFAULT_CONSTRAINTS["max_per_sector"]


def test_no_selected_bundle_is_mutually_exclusive_or_gate_blocked() -> None:
    from wallet_twin_v31.taxonomy import mutually_exclusive

    for entry in repository.plan.entries:
        conversation = repository.by_id[entry.conversation_id]
        assert not mutually_exclusive(conversation.solution_bundle.solutions)
        assert not conversation.risk_and_feasibility.blocked


def test_solver_status_is_recorded_and_fallback_is_labelled() -> None:
    plan = repository.plan
    assert plan.solver_status in {"OPTIMAL", "DEGRADED_FALLBACK"}
    assert plan.degraded_fallback == (plan.solver_status == "DEGRADED_FALLBACK")
    assert "CVaR" in plan.solver


def test_greedy_fallback_must_be_labelled_degraded() -> None:
    from wallet_twin_v31.contracts import CoveragePlan

    with pytest.raises(ValidationError):
        CoveragePlan(
            plan_id="p",
            as_of=AS_OF,
            week_start=WEEK_START,
            capacity=8,
            entries=[],
            objective_value=0.0,
            expected_adjusted_benefit=0.0,
            cvar10_adjusted_benefit=0.0,
            solver="greedy",
            solver_status="OPTIMAL",
            degraded_fallback=True,
            scenario_draws=512,
            weights_version="v",
        )


def test_policy_weights_are_versioned_and_sum_to_one() -> None:
    weights = repository.policy["benefit_weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert repository.policy["weights_version"]
    assert repository.plan.weights_version == repository.policy["weights_version"]


def test_legacy_decision_score_is_not_used_for_v31_selection() -> None:
    v3_top = {
        item.opportunity_id
        for item in sorted(
            __import__(
                "wallet_twin_v3.repository", fromlist=["repository"]
            ).repository.opportunities,
            key=lambda item: -item.decision_score,
        )[:8]
    }
    selected = {entry.conversation_id for entry in repository.plan.entries}
    assert not (selected & v3_top)


# ---------------------------------------------------------------------------
# VOI and the learning loop
# ---------------------------------------------------------------------------
def test_only_positive_net_voi_questions_are_selected() -> None:
    selected = [
        question
        for group in repository.questions.values()
        for question in group
        if question.selected
    ]
    assert selected
    for question in selected:
        assert question.net_voi_zar > 0
        assert any(
            (
                question.can_change_rank,
                question.can_change_bundle,
                question.can_change_feasibility,
                question.can_change_abstention,
            )
        )


def test_a_question_with_no_decision_effect_is_rejected() -> None:
    with pytest.raises(ValidationError):
        InformationQuestion(
            question_id="q",
            entity_id="E01",
            conversation_id="c",
            variable_id="v",
            variable_label="v",
            question_text="t",
            stakeholder_role=StakeholderRole.CFO,
            answer_states=[
                {"state_id": "a", "label": "a", "probability": 0.5, "implied_shift": 1.0},
                {"state_id": "b", "label": "b", "probability": 0.5, "implied_shift": 1.0},
            ],
            expected_utility_with_answer=1.0,
            expected_utility_without_answer=0.0,
            cost_zar=0.0,
            delay_penalty_zar=0.0,
            net_voi_zar=100.0,
            can_change_rank=False,
            can_change_bundle=False,
            can_change_feasibility=False,
            can_change_abstention=False,
            scenario_draws=512,
            selected=True,
            policy_version="v",
        )


def test_answer_states_form_a_distribution() -> None:
    for variable in QUESTION_LIBRARY:
        assert abs(sum(state[2] for state in variable.states) - 1.0) < 1e-9


def test_at_most_one_primary_and_two_alternative_questions_per_conversation() -> None:
    for group in repository.questions.values():
        assert sum(1 for question in group if question.selected) <= 3


def test_pending_answers_do_not_alter_snapshots_and_approval_creates_evidence() -> None:
    from wallet_twin_v31.questions import ClientAnswerWorkflow

    question = next(
        question
        for group in repository.questions.values()
        for question in group
        if question.selected
    )
    workflow = ClientAnswerWorkflow(AS_OF)
    answer = workflow.submit(
        answer_id="test-answer-1",
        question=question,
        answer_state_id=question.answer_states[0].state_id,
        respondent_role=StakeholderRole.TREASURER,
        respondent_type="CLIENT",
        consent_reference="consent-2026-9999",
        scope="group treasury",
        source="RM meeting note",
    )
    assert answer.approval_status is ApprovalStatus.PENDING_REVIEW
    assert answer.resulting_claim_id is None
    assert workflow.pending()

    approved, claim = workflow.approve(
        "test-answer-1", reviewer_id="reviewer-1", reviewer_role="Evidence Reviewer"
    )
    assert approved.approval_status is ApprovalStatus.APPROVED
    assert approved.resulting_claim_id == claim.claim_id
    assert claim.tier is EvidenceTier.E2
    assert claim.approval_status is ApprovalStatus.APPROVED
    assert claim.reviewer_id == "reviewer-1"
    assert not workflow.pending()


def test_voi_engine_is_reproducible() -> None:
    engine = VOIEngine(draws=128)
    draws = np.linspace(0.1, 0.9, 256)
    first = engine.evaluate(
        entity_id="E01",
        conversation_id="conv:test",
        problem=BusinessProblem.FX_EXPOSURE,
        solutions=[BankingSolution.CROSS_BORDER_FX],
        unknown_gates=[],
        utility_draws=draws,
        alternative_utility=0.2,
    )
    second = engine.evaluate(
        entity_id="E01",
        conversation_id="conv:test",
        problem=BusinessProblem.FX_EXPOSURE,
        solutions=[BankingSolution.CROSS_BORDER_FX],
        unknown_gates=[],
        utility_draws=draws,
        alternative_utility=0.2,
    )
    assert [item.net_voi_zar for item in first] == [item.net_voi_zar for item in second]


# ---------------------------------------------------------------------------
# Briefs and narration control
# ---------------------------------------------------------------------------
def test_every_selected_conversation_has_an_evidence_backed_explanation_path() -> None:
    for entry in repository.plan.entries:
        conversation = repository.by_id[entry.conversation_id]
        path = conversation.explanation_path
        assert len(path.steps) == 7
        assert [step.step for step in path.steps] == [
            "EVENT",
            "BUSINESS_IMPACT",
            "PROBLEM",
            "STAKEHOLDER",
            "SOLUTION",
            "CLIENT_VALUE",
            "BANK_VALUE",
        ]
        supported = [step for step in path.steps if step.evidence_claim_ids]
        assert supported, entry.conversation_id


def test_deterministic_brief_separates_why_how_and_what() -> None:
    for entry in repository.plan.entries:
        brief = repository.briefs[entry.conversation_id]
        assert brief.why and brief.how and brief.what
        assert brief.compiler.startswith("v31-deterministic-brief")
        assert brief.fallback_available
        assert brief.provider_used is False
        assert brief.abstentions


def test_brief_never_contains_a_prohibited_claim() -> None:
    banned = (
        "measured competitor share",
        "causal uplift",
        "guaranteed saving",
        "optimal target share",
    )
    for brief in repository.briefs.values():
        text = " ".join([brief.why, brief.how, brief.what]).lower()
        for phrase in banned:
            assert phrase not in text


def test_claim_compiler_rejects_unsupported_numbers_and_roles() -> None:
    conversation = repository.by_id[repository.plan.entries[0].conversation_id]
    pack = compile_claim_pack(conversation, repository.registry)
    compiler = ClaimCompiler()

    accepted, violations = compiler.verify(
        "The client should hedge ZAR 999,888,777 immediately.", pack
    )
    assert not accepted
    assert any(item.startswith("UNSUPPORTED_NUMBER") for item in violations)

    accepted, violations = compiler.verify(
        "We know that causal uplift will follow.", pack
    )
    assert not accepted
    assert any(item.startswith("PROHIBITED_CLAIM") for item in violations)


def test_provider_failure_always_returns_the_deterministic_brief() -> None:
    conversation = repository.by_id[repository.plan.entries[0].conversation_id]
    deterministic = compile_brief(conversation, repository.registry)
    pack = compile_claim_pack(conversation, repository.registry)
    compiler = ClaimCompiler()
    assert compiler.compile_or_fallback(deterministic, pack, None) is deterministic
    rejected = compiler.compile_or_fallback(
        deterministic, pack, "Guaranteed saving of ZAR 123,456,789."
    )
    assert rejected.provider_used is False
    assert rejected.why == deterministic.why


def test_unsupported_urgency_is_rejected() -> None:
    unsupported = next(
        (
            item
            for item in repository.conversation_list
            if not item.engagement_window.trigger_supported
        ),
        None,
    )
    if unsupported is None:
        pytest.skip("every conversation in this snapshot has a supported trigger")
    pack = compile_claim_pack(unsupported, repository.registry)
    accepted, violations = ClaimCompiler().verify("You must act now.", pack)
    assert not accepted
    assert "UNSUPPORTED_URGENCY" in violations


def test_no_time_critical_trigger_is_manufactured() -> None:
    for conversation in repository.conversation_list:
        window = conversation.engagement_window
        if not window.trigger_supported:
            assert window.trigger_date is None
            assert "No dated, supported trigger" in window.why_now


# ---------------------------------------------------------------------------
# API, security and operations
# ---------------------------------------------------------------------------
def test_decision_twin_does_not_ship_the_whole_portfolio_to_the_browser() -> None:
    response = client.get("/v3/decision-twin", params={"as_of": AS_OF.isoformat()})
    assert response.status_code == 200
    assert len(response.content) < 1_000_000
    payload = response.json()
    assert "conversation_summaries" in payload
    assert "conversations" not in payload
    assert payload["detail_routes"]


def test_every_modelled_read_requires_as_of() -> None:
    for route in (
        "/v3/decision-twin",
        "/v3/conversations",
        "/v3/coverage-plan",
        "/v3/clients/E01/business-twin",
        "/v3/clients/E01/business-graph",
        "/v3/funding-routes/E01",
    ):
        assert client.get(route).status_code == 422, route


def test_since_may_not_exceed_as_of() -> None:
    response = client.get(
        "/v3/clients/E01/change-digest",
        params={"as_of": AS_OF.isoformat(), "since": "2026-12-31"},
    )
    assert response.status_code == 400


def test_mutations_require_an_idempotency_key() -> None:
    conversation_id = repository.plan.entries[0].conversation_id
    body = {
        "gate": "CREDIT_AND_RISK",
        "status": "PASS",
        "role": "Credit Officer",
        "reason": "limit confirmed by the credit team",
    }
    assert (
        client.post(f"/v3/feasibility/{conversation_id}/attestations", json=body).status_code
        == 400
    )
    assert (
        client.post(
            f"/v3/feasibility/{conversation_id}/attestations",
            json=body,
            headers={"Idempotency-Key": "test-key-1"},
        ).status_code
        == 201
    )


def test_an_attestation_may_not_restate_the_unknown() -> None:
    conversation_id = repository.plan.entries[0].conversation_id
    response = client.post(
        f"/v3/feasibility/{conversation_id}/attestations",
        json={
            "gate": "CREDIT_AND_RISK",
            "status": "UNKNOWN",
            "role": "Credit Officer",
            "reason": "still unknown to us",
        },
        headers={"Idempotency-Key": "test-key-2"},
    )
    assert response.status_code == 400


def test_scenario_evaluation_never_publishes() -> None:
    conversation_id = repository.plan.entries[0].conversation_id
    response = client.post(
        "/v3/scenarios/conversations/evaluate",
        json={
            "conversation_id": conversation_id,
            "as_of": AS_OF.isoformat(),
            "policy_version": "v31-policy-weights-3.1.0",
            "economics_version": "v31-dual-value-3.1.0",
            "client_value_multiplier": 1.25,
        },
        headers={"Idempotency-Key": "test-key-3"},
    )
    assert response.status_code == 200
    assert response.json()["publishes"] is False


def test_cross_client_reads_are_denied() -> None:
    headers = {
        "x-user-id": "rm-1",
        "x-user-roles": "PILOT_RM",
        "x-user-team": "coverage",
        "x-user-clients": "E01",
    }
    assert (
        client.get(
            "/v3/clients/E02/business-twin",
            params={"as_of": AS_OF.isoformat()},
            headers=headers,
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/v3/clients/E01/business-twin",
            params={"as_of": AS_OF.isoformat()},
            headers=headers,
        ).status_code
        == 200
    )


def test_sensitive_economics_requires_the_right_role() -> None:
    headers = {
        "x-user-id": "rm-2",
        "x-user-roles": "PILOT_RM",
        "x-user-team": "coverage",
        "x-user-clients": "*",
    }
    assert (
        client.get(
            "/v3/funding-routes/E01",
            params={"as_of": AS_OF.isoformat()},
            headers=headers,
        ).status_code
        == 403
    )


def test_unimplemented_repositories_say_so_instead_of_faking_data() -> None:
    for repo, method in (
        (DeltaAnalyticalRepository(), "conversations"),
        (PostgresWorkflowRepository(), "open_review_tasks"),
    ):
        with pytest.raises(NotImplementedError):
            getattr(repo, method)(AS_OF) if method == "conversations" else getattr(
                repo, method
            )()


# ---------------------------------------------------------------------------
# Release posture
# ---------------------------------------------------------------------------
def test_release_posture_stays_not_promotable() -> None:
    assert repository.release["bank_production_status"] == "NOT_PROMOTABLE"
    assert repository.release["blocking_external_gates"]


def test_validation_reports_no_forbidden_claim_class() -> None:
    validation = repository.validation
    assert validation["measured_competitor_share_claims"] == 0
    assert validation["causal_value_claims"] == 0
    assert validation["opaque_confidence_scores"] == 0
    assert validation["guaranteed_saving_claims"] == 0
    assert validation["named_stakeholders_displayed"] == 0


def test_every_client_receives_the_same_surfaces() -> None:
    for entity_id in repository.twins:
        assert repository.twins[entity_id]
        assert repository.graphs[entity_id]
        assert repository.digests[entity_id]
        assert repository.routes[entity_id]
        assert len(repository.estimates[entity_id]) == 16
        assert len(repository.problems[entity_id]) == 18


def test_clients_without_eligible_conversations_still_get_discovery_cards() -> None:
    covered = {item.entity_id for item in repository.conversation_list}
    assert covered == set(repository.twins)
    for conversation in repository.conversation_list:
        assert conversation.action in {
            ConversationAction.PRODUCT_PROPOSAL,
            ConversationAction.DISCOVERY,
            ConversationAction.EVIDENCE_ACQUISITION,
            ConversationAction.VALIDATION,
        }
