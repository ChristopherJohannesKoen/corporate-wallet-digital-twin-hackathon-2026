"""Conversation-candidate assembly.

This is where the five coordinates come together:

    (client, stakeholder, business problem, solution bundle, engagement window)

A candidate is only created when a problem is identified *and* at least one
PRIMARY solution for it has an available estimate.  A problem with no
quantifiable solution produces an evidence-acquisition conversation instead of
a product conversation â€” which is the honest output, not a gap in coverage.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, List, Mapping, Optional, Sequence


from wallet_twin_v2.contracts import (
    ArtifactReference,
    DataProvenanceClass,
    OpportunityView,
)

from .business_evidence import BusinessEvidenceRegistry
from .business_graph import build_explanation_path
from .business_twin import DOMAIN_MATERIALITY, WATERMARK
from .contracts import (
    BusinessEvent,
    BusinessTwinSnapshot,
    ConversationCandidate,
    ProblemHypothesis,
    SolutionBundle,
    SolutionEstimate,
    conversation_id as make_conversation_id,
)
from .feasibility import FeasibilityEngine
from .pareto import CandidateAxes
from .taxonomy import (
    BankingSolution as S,
    BusinessProblem as P,
    ConversationAction,
    EligibilityDecision,
    PROBLEM_LABELS,
    PROBLEM_SOLUTION_MATRIX_VERSION,
    mapping_for,
    mutually_exclusive,
    primary_solutions,
    supporting_solutions,
)
from .timing import EngagementWindowEngine
from .value import BankValueEngine, ClientValueEngine

CONVERSATION_VERSION = "v31-conversation-assembly-3.1.1"

#: Strategic weight per problem: how much a solved instance changes the shape of
#: the relationship rather than this quarter's revenue.  Governed policy.
STRATEGIC_WEIGHT: Mapping[P, float] = {
    P.TREASURY_CENTRALISATION: 0.95,
    P.MA_OR_STRATEGIC_EVENT: 0.90,
    P.CAPITAL_STRUCTURE_EVENT: 0.85,
    P.REFINANCING_CLIFF: 0.80,
    P.ESG_TRANSITION_FUNDING: 0.75,
    P.PROJECT_MOBILISATION: 0.75,
    P.NEW_FUNDING_REQUIREMENT: 0.70,
    P.LIQUIDITY_FRAGMENTATION: 0.65,
    P.WALLET_LEAKAGE: 0.60,
    P.WORKING_CAPITAL_PRESSURE: 0.60,
    P.SUPPLY_CHAIN_RISK: 0.55,
    P.OPERATIONAL_RESILIENCE: 0.55,
    P.FX_EXPOSURE: 0.50,
    P.INTEREST_RATE_EXPOSURE: 0.50,
    P.COMMODITY_EXPOSURE: 0.50,
    P.GUARANTEE_OR_COLLATERAL_REQUIREMENT: 0.45,
    P.PAYMENTS_INEFFICIENCY: 0.40,
    P.COLLECTIONS_INEFFICIENCY: 0.40,
}


def _log_normalise(values: Sequence[float]) -> List[float]:
    """Map values onto 0-1 through a log transform so scale does not dominate."""
    positive = [max(0.0, value) for value in values]
    if not positive or max(positive) <= 0:
        return [0.0] * len(values)
    logged = [math.log1p(value) for value in positive]
    low, high = min(logged), max(logged)
    if high - low < 1e-9:
        return [0.5] * len(values)
    return [(item - low) / (high - low) for item in logged]


class RawCandidate:
    """A conversation before portfolio-relative normalisation."""

    __slots__ = (
        "entity_id",
        "entity_name",
        "sector",
        "problem",
        "bundle",
        "estimates",
        "stakeholder",
        "window",
        "client_value",
        "bank_value",
        "feasibility",
        "explanation",
        "conversation_id",
        "action",
        "eligibility",
        "eligibility_reasons",
        "evidence_claim_ids",
    )

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class ConversationBuilder:
    version = CONVERSATION_VERSION

    def __init__(
        self,
        registry: BusinessEvidenceRegistry,
        as_of: date,
        week_start: date,
    ) -> None:
        self.registry = registry
        self.as_of = as_of
        self.week_start = week_start
        self.feasibility_engine = FeasibilityEngine()
        self.client_value_engine = ClientValueEngine()
        self.bank_value_engine = BankValueEngine()
        self.window_engine = EngagementWindowEngine(as_of)

    # -- bundle construction ----------------------------------------------
    def _bundle_for(
        self,
        problem: P,
        estimates: Mapping[S, SolutionEstimate],
    ) -> Optional[SolutionBundle]:
        available_primary = [
            solution
            for solution in primary_solutions(problem)
            if estimates[solution].available
        ]
        if not available_primary:
            return None
        primary = max(
            available_primary,
            key=lambda solution: (
                estimates[solution].amount_interval.median
                if estimates[solution].amount_interval
                else 0.0,
                solution.value,
            ),
        )
        supporting: List[S] = []
        for solution in supporting_solutions(problem):
            if len(supporting) >= 2:
                break
            if solution is primary or not estimates[solution].available:
                continue
            if mutually_exclusive([primary, *supporting, solution]):
                continue
            supporting.append(solution)
        for solution in available_primary:
            if len(supporting) >= 2:
                break
            if solution is primary or solution in supporting:
                continue
            if mutually_exclusive([primary, *supporting, solution]):
                continue
            supporting.append(solution)

        chosen = [primary, *supporting]
        strengths = {
            solution.value: mapping_for(problem, solution).strength
            for solution in chosen
        }
        prerequisites = sorted(
            {
                item
                for solution in chosen
                for item in mapping_for(problem, solution).prerequisites
            }
        )
        return SolutionBundle(
            bundle_id=f"bundle:{problem.value.lower()}:"
            + "+".join(sorted(item.value.lower() for item in chosen)),
            primary=primary,
            supporting=supporting,
            strengths=strengths,
            prerequisites=prerequisites,
            matrix_version=PROBLEM_SOLUTION_MATRIX_VERSION,
        )

    # -- one candidate -----------------------------------------------------
    def build_candidate(
        self,
        *,
        twin: BusinessTwinSnapshot,
        hypothesis: ProblemHypothesis,
        estimates: Mapping[S, SolutionEstimate],
        events: Sequence[BusinessEvent],
        stakeholder_resolver: Any,
        legacy_opportunities: Mapping[str, OpportunityView],
        corridors: Sequence[str],
        daily_operating_cost: Optional[float],
        ccc_days: Optional[float],
        change_signal: Optional[Any] = None,
    ) -> Optional[RawCandidate]:
        bundle = self._bundle_for(hypothesis.problem, estimates)
        if bundle is None:
            return None
        chosen = [estimates[solution] for solution in bundle.solutions]
        stakeholder = stakeholder_resolver.resolve(
            twin.entity_id, hypothesis.problem, bundle=bundle.solutions
        )
        legacy_timing = None
        primary_estimate = chosen[0]
        if primary_estimate.timing_probability_90d is not None:
            legacy_timing = (
                primary_estimate.timing_probability_30d or 0.0,
                primary_estimate.timing_probability_60d or 0.0,
                primary_estimate.timing_probability_90d,
            )
        window = self.window_engine.build(
            twin.entity_id,
            hypothesis,
            bundle.primary,
            events,
            legacy_timing=legacy_timing,
            change_signal=change_signal,
        )
        client_value = self.client_value_engine.evaluate(
            twin.entity_id,
            bundle,
            chosen,
            ccc_days=ccc_days,
            daily_operating_cost=daily_operating_cost,
        )
        bank_value = self.bank_value_engine.evaluate(
            twin.entity_id, bundle, chosen, legacy_opportunities
        )
        feasibility = self.feasibility_engine.assess(
            twin.entity_id, bundle, chosen, corridors=corridors
        )

        action = feasibility.permitted_action
        reasons: List[str] = []
        if feasibility.blocked:
            eligibility = EligibilityDecision.BLOCKED
            reasons.extend(
                f"GATE_FAILED_{item.gate.value}"
                for item in feasibility.gates
                if item.status.value == "FAIL"
            )
        elif not hypothesis.commercially_eligible:
            eligibility = EligibilityDecision.DISCOVERY_ONLY
            action = ConversationAction.DISCOVERY
            reasons.append("NO_GOVERNED_CRITICAL_PROBLEM_SIGNAL")
        elif feasibility.material_unknowns:
            eligibility = EligibilityDecision.DISCOVERY_ONLY
            action = ConversationAction.DISCOVERY
            reasons.extend(
                f"GATE_UNKNOWN_{gate.value}" for gate in feasibility.material_unknowns
            )
        else:
            eligibility = EligibilityDecision.ELIGIBLE

        trigger_event = next(
            (
                event
                for event in events
                if window.trigger_event_key
                and event.event_key == window.trigger_event_key
            ),
            None,
        )
        impact_claims = sorted(
            {
                claim_id
                for item in hypothesis.supporting_evidence
                for claim_id in item.evidence_claim_ids
            }
        )
        client_supported = client_value.monetised_total is not None
        bank_supported = bank_value.direct_contribution is not None
        explanation = build_explanation_path(
            entity_id=twin.entity_id,
            event=trigger_event,
            business_impact=self._impact_statement(hypothesis),
            impact_claim_ids=impact_claims,
            problem=hypothesis.problem,
            problem_claim_ids=impact_claims,
            role=stakeholder.primary_role,
            solution=bundle.primary,
            client_value_statement=self._client_value_statement(client_value),
            client_value_supported=client_supported,
            bank_value_statement=self._bank_value_statement(bank_value),
            bank_value_supported=bank_supported,
        )

        window_key = (
            window.trigger_event_key or f"no-trigger:{self.week_start.isoformat()}"
        )
        identifier = make_conversation_id(
            twin.entity_id,
            stakeholder.primary_role,
            hypothesis.problem,
            bundle.solutions,
            window_key,
            twin.snapshot_version,
        )
        evidence_ids = sorted(
            set(impact_claims)
            | {
                claim_id
                for estimate in chosen
                for claim_id in estimate.evidence_claim_ids
            }
        )
        return RawCandidate(
            entity_id=twin.entity_id,
            entity_name=twin.entity_name,
            sector=twin.sector,
            problem=hypothesis,
            bundle=bundle,
            estimates=chosen,
            stakeholder=stakeholder,
            window=window,
            client_value=client_value,
            bank_value=bank_value,
            feasibility=feasibility,
            explanation=explanation,
            conversation_id=identifier,
            action=action,
            eligibility=eligibility,
            eligibility_reasons=sorted(set(reasons)),
            evidence_claim_ids=evidence_ids,
        )

    # -- narrative fragments ----------------------------------------------
    @staticmethod
    def _impact_statement(hypothesis: ProblemHypothesis) -> str:
        if hypothesis.intensity_unit == "UNQUANTIFIED":
            return (
                f"{PROBLEM_LABELS[hypothesis.problem]} is indicated but not yet quantified "
                "from reviewed evidence."
            )
        return (
            f"{PROBLEM_LABELS[hypothesis.problem]} of about "
            f"{hypothesis.intensity.median:,.0f} {hypothesis.intensity_unit}"
        )

    @staticmethod
    def _client_value_statement(client_value: Any) -> str:
        if client_value.monetised_total is not None:
            total = client_value.monetised_total
            return (
                f"Modelled client benefit of ZAR {total.lower:,.0f} to ZAR {total.upper:,.0f} "
                "under the governed assumption set"
            )
        if client_value.risk_reduction_statement:
            return "Risk reduction rather than a monetised saving"
        return "Client benefit is not monetisable from reviewed evidence"

    @staticmethod
    def _bank_value_statement(bank_value: Any) -> str:
        if bank_value.direct_contribution is None:
            return "Bank economics are blocked: no approved rate card exists for this bundle"
        contribution = bank_value.direct_contribution
        return (
            f"Representative net contribution of ZAR {contribution.lower:,.0f} to "
            f"ZAR {contribution.upper:,.0f} after cost to win"
        )

    # -- axes --------------------------------------------------------------
    def axes(self, raw: Sequence[RawCandidate]) -> List[CandidateAxes]:
        client_values = [
            raw_item.client_value.monetised_total.median
            if raw_item.client_value.monetised_total is not None
            else 0.0
            for raw_item in raw
        ]
        bank_values = [
            raw_item.bank_value.direct_contribution.median
            if raw_item.bank_value.direct_contribution is not None
            else 0.0
            for raw_item in raw
        ]
        relationship_values = [
            raw_item.bank_value.relationship_value_3y.median
            if raw_item.bank_value.relationship_value_3y is not None
            else 0.0
            for raw_item in raw
        ]
        client_norm = _log_normalise(client_values)
        bank_norm = _log_normalise(bank_values)
        relationship_norm = _log_normalise(relationship_values)

        result: List[CandidateAxes] = []
        for index, raw_item in enumerate(raw):
            interval_width = 0.0
            primary = raw_item.estimates[0]
            if primary.amount_interval and primary.amount_interval.median > 0:
                interval_width = min(
                    1.0,
                    (primary.amount_interval.upper - primary.amount_interval.lower)
                    / primary.amount_interval.median,
                )
            strategic = STRATEGIC_WEIGHT[raw_item.problem.problem]
            domain_weight = max(
                (
                    DOMAIN_MATERIALITY[domain]
                    for domain in raw_item.problem.affected_domains
                ),
                default=0.5,
            )
            result.append(
                CandidateAxes(
                    candidate_id=raw_item.conversation_id,
                    entity_id=raw_item.entity_id,
                    problem_id=raw_item.problem.problem_id,
                    need=raw_item.problem.probability or 0.0,
                    client_value=client_norm[index],
                    bank_value=bank_norm[index],
                    timing=raw_item.window.probability_90d,
                    relationship_value=relationship_norm[index],
                    strategic_value=strategic * domain_weight,
                    risk=raw_item.feasibility.risk_score,
                    friction=raw_item.feasibility.friction_score,
                    feasibility=raw_item.feasibility.feasibility_multiplier,
                    # A wide interval means a genuinely uncertain candidate, so
                    # its scenario draws spread further and it cannot dominate a
                    # well-evidenced candidate by luck.
                    dispersion=round(0.15 + 0.35 * interval_width, 4),
                )
            )
        return result

    # -- finalisation ------------------------------------------------------
    def finalise(
        self,
        raw: RawCandidate,
        *,
        pareto_status: Any,
        policy_rank: Any,
        question: Any,
        why: str,
        how: str,
        what: str,
    ) -> ConversationCandidate:
        tiers = sorted(
            {estimate.evidence_tier for estimate in raw.estimates},
            key=lambda tier: tier.value,
        )
        claim_classes = sorted(
            {estimate.claim_class for estimate in raw.estimates}
            | {raw.problem.claim_class, raw.client_value.claim_class},
            key=lambda item: item.value,
        )
        provenance = [
            DataProvenanceClass.PUBLIC_AUDITED,
            DataProvenanceClass.SYNTHETIC_SIMULATION,
            DataProvenanceClass.REPRESENTATIVE_PUBLIC,
        ]
        return ConversationCandidate(
            conversation_id=raw.conversation_id,
            entity_id=raw.entity_id,
            entity_name=raw.entity_name,
            sector=raw.sector,
            legal_entity_ids=[raw.entity_id],
            as_of=self.as_of,
            week_start=self.week_start,
            stakeholder=raw.stakeholder,
            problem=raw.problem,
            solution_bundle=raw.bundle,
            solution_estimates=raw.estimates,
            engagement_window=raw.window,
            client_value=raw.client_value,
            bank_value=raw.bank_value,
            risk_and_feasibility=raw.feasibility,
            pareto_status=pareto_status,
            policy_rank=policy_rank,
            next_best_question=question,
            explanation_path=raw.explanation,
            why=why,
            how=how,
            what=what,
            action=raw.action,
            eligibility=raw.eligibility,
            eligibility_reasons=raw.eligibility_reasons,
            artifacts=ArtifactReference(
                model_version=CONVERSATION_VERSION,
                dataset_version=self.registry.version,
                prior_version="v31-governed-policy-3.1.1",
                transformation_version=CONVERSATION_VERSION,
                schema_version="3.1.1",
            ),
            claim_classes=claim_classes,
            provenance=provenance,
            evidence_tiers=tiers,
            evidence_claim_ids=raw.evidence_claim_ids,
            watermark=WATERMARK,
        )
