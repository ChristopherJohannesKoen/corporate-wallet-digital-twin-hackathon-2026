"""Active Coverage Learning — decision-directed value of information.

The governing principle is decision-focused active learning rather than generic
uncertainty reduction: a question is only worth asking if the answer could
change what the bank does.  This follows the primary research on active
learning for decision-making
(https://proceedings.mlr.press/v97/sundin19a.html); the mechanism here is a
governed VOI calculation, not a reimplementation of that paper's model.

    VOI(Q) = E[max_a U(a | Answer(Q))] - max_a E[U(a)] - Cost(Q) - Delay(Q)

A question is selected only when net VOI is positive *and* the answer could
change rank, bundle, feasibility or abstention.  A question that would merely
narrow an interval without changing any decision is rejected, however
interesting the interval is.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from wallet_twin_v2.contracts import (
    ApprovalStatus,
    ClaimClass,
    CuratedMetadata,
    DataProvenanceClass,
    EvidenceTier,
)

from .contracts import (
    AnswerState,
    BusinessEvidenceClaim,
    ClientAnswer,
    InformationQuestion,
)
from .taxonomy import (
    BankingSolution,
    BusinessClaimKind,
    BusinessProblem,
    BusinessTwinDomain as D,
    FeasibilityGate,
    StakeholderRole,
)

VOI_POLICY_VERSION = "v31-decision-directed-voi-3.1.0"
VOI_DRAWS = 512


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16) % (2**32)


@dataclass(frozen=True)
class UnknownVariable:
    """A governed unknown that a client or RM could resolve."""

    variable_id: str
    label: str
    question_text: str
    role: StakeholderRole
    domains: Tuple[D, ...]
    #: Possible answers with prior probability and the multiplicative shift each
    #: answer implies for the conversation's adjusted benefit.
    states: Tuple[Tuple[str, str, float, float], ...]
    cost_zar: float
    delay_days: int
    changes_rank: bool
    changes_bundle: bool
    changes_feasibility: bool
    changes_abstention: bool
    relevant_problems: Tuple[BusinessProblem, ...] = ()
    relevant_solutions: Tuple[BankingSolution, ...] = ()
    resolves_gate: Optional[FeasibilityGate] = None
    claim_concept: str = ""
    claim_kind: BusinessClaimKind = BusinessClaimKind.CATEGORICAL


P = BusinessProblem
S = BankingSolution

#: The governed library of unknowns.  Adding one is a policy change: every
#: variable states which decision it can move and what it costs to ask.
QUESTION_LIBRARY: Tuple[UnknownVariable, ...] = (
    UnknownVariable(
        variable_id="HEDGE_RATIO",
        label="Hedge ratio",
        question_text=(
            "What share of your foreign-currency exposure is currently hedged, and over "
            "what tenor?"
        ),
        role=StakeholderRole.TREASURER,
        domains=(D.CURRENCY_AND_COMMODITY_EXPOSURE,),
        states=(
            ("MOSTLY_HEDGED", "Largely hedged (over 70%)", 0.35, 0.35),
            ("PARTLY_HEDGED", "Partly hedged (30-70%)", 0.40, 1.05),
            ("LARGELY_UNHEDGED", "Largely unhedged (under 30%)", 0.25, 1.75),
        ),
        cost_zar=4_000.0,
        delay_days=5,
        changes_rank=True,
        changes_bundle=True,
        changes_feasibility=False,
        changes_abstention=True,
        relevant_problems=(P.FX_EXPOSURE, P.COMMODITY_EXPOSURE, P.INTEREST_RATE_EXPOSURE),
        relevant_solutions=(
            S.CROSS_BORDER_FX,
            S.COMMODITY_RISK_MANAGEMENT,
            S.INTEREST_RATE_RISK_MANAGEMENT,
        ),
        claim_concept="client_hedge_ratio",
        claim_kind=BusinessClaimKind.RATIO,
    ),
    UnknownVariable(
        variable_id="BANKING_COUNTERPARTIES",
        label="Number of banking counterparties",
        question_text=(
            "How many banks currently hold transaction or facility mandates for the group?"
        ),
        role=StakeholderRole.TREASURER,
        domains=(D.OPERATING_MODEL,),
        states=(
            ("SINGLE_OR_TWO", "One or two banks", 0.25, 0.55),
            ("THREE_TO_FIVE", "Three to five banks", 0.45, 1.15),
            ("MORE_THAN_FIVE", "More than five banks", 0.30, 1.60),
        ),
        cost_zar=2_500.0,
        delay_days=4,
        changes_rank=True,
        changes_bundle=False,
        changes_feasibility=False,
        changes_abstention=True,
        relevant_problems=(P.WALLET_LEAKAGE, P.LIQUIDITY_FRAGMENTATION, P.TREASURY_CENTRALISATION),
        claim_concept="client_bank_counterparty_count",
        claim_kind=BusinessClaimKind.COUNT,
    ),
    UnknownVariable(
        variable_id="CASH_FLOW_TIMING",
        label="Expected payment and cash-flow timing",
        question_text=(
            "When do your largest supplier payment and collection cycles fall over the next "
            "two quarters?"
        ),
        role=StakeholderRole.FINANCE_OPERATIONS,
        domains=(D.WORKING_CAPITAL_CYCLE, D.COST_ENGINE),
        states=(
            ("NEXT_30_DAYS", "Inside the next 30 days", 0.30, 1.65),
            ("30_TO_90_DAYS", "Between 30 and 90 days", 0.45, 1.10),
            ("BEYOND_90_DAYS", "Beyond 90 days", 0.25, 0.55),
        ),
        cost_zar=1_800.0,
        delay_days=3,
        changes_rank=True,
        changes_bundle=False,
        changes_feasibility=False,
        changes_abstention=False,
        relevant_problems=(
            P.PAYMENTS_INEFFICIENCY,
            P.COLLECTIONS_INEFFICIENCY,
            P.WORKING_CAPITAL_PRESSURE,
        ),
        claim_concept="client_cash_flow_timing",
        claim_kind=BusinessClaimKind.CATEGORICAL,
    ),
    UnknownVariable(
        variable_id="FUNDING_ROUTE_PREFERENCE",
        label="Funding-route preference",
        question_text=(
            "For the next refinancing, is the board's preference bank debt, a bond issue or "
            "internal cash?"
        ),
        role=StakeholderRole.CFO,
        domains=(D.FUNDING_STRUCTURE,),
        states=(
            ("BANK_DEBT", "Bank debt", 0.40, 1.55),
            ("CAPITAL_MARKETS", "Bond or capital markets", 0.35, 1.20),
            ("INTERNAL_CASH", "Internal cash", 0.25, 0.35),
        ),
        cost_zar=6_000.0,
        delay_days=10,
        changes_rank=True,
        changes_bundle=True,
        changes_feasibility=False,
        changes_abstention=True,
        relevant_problems=(P.REFINANCING_CLIFF, P.NEW_FUNDING_REQUIREMENT, P.CAPITAL_STRUCTURE_EVENT),
        relevant_solutions=(S.TERM_AND_SYNDICATED_LENDING, S.DEBT_CAPITAL_MARKETS),
        claim_concept="client_funding_route_preference",
    ),
    UnknownVariable(
        variable_id="FACILITY_HEADROOM",
        label="Existing facility capacity",
        question_text=(
            "How much undrawn committed facility headroom is currently available to the group?"
        ),
        role=StakeholderRole.TREASURER,
        domains=(D.FUNDING_STRUCTURE, D.LIQUIDITY_AND_BUFFER),
        states=(
            ("AMPLE", "Ample headroom", 0.30, 0.35),
            ("LIMITED", "Limited headroom", 0.45, 1.30),
            ("NONE", "No undrawn headroom", 0.25, 1.80),
        ),
        cost_zar=3_500.0,
        delay_days=7,
        changes_rank=True,
        changes_bundle=True,
        changes_feasibility=False,
        changes_abstention=True,
        relevant_problems=(
            P.REFINANCING_CLIFF,
            P.WORKING_CAPITAL_PRESSURE,
            P.NEW_FUNDING_REQUIREMENT,
        ),
        claim_concept="client_undrawn_facility_headroom",
        claim_kind=BusinessClaimKind.MONEY,
    ),
    UnknownVariable(
        variable_id="SUPPLIER_CONCENTRATION",
        label="Supplier concentration",
        question_text=(
            "What share of spend sits with your ten largest suppliers, and are any on "
            "extended terms?"
        ),
        role=StakeholderRole.PROCUREMENT,
        domains=(D.COST_ENGINE, D.OPERATING_MODEL),
        states=(
            ("HIGHLY_CONCENTRATED", "Top ten over 60% of spend", 0.35, 1.55),
            ("MODERATE", "Top ten 30-60% of spend", 0.40, 1.05),
            ("FRAGMENTED", "Top ten under 30% of spend", 0.25, 0.50),
        ),
        cost_zar=5_000.0,
        delay_days=9,
        changes_rank=True,
        changes_bundle=True,
        changes_feasibility=False,
        changes_abstention=True,
        relevant_problems=(P.SUPPLY_CHAIN_RISK, P.WORKING_CAPITAL_PRESSURE),
        relevant_solutions=(S.SUPPLY_CHAIN_FINANCE, S.TRADE_FINANCE),
        claim_concept="client_supplier_concentration",
        claim_kind=BusinessClaimKind.RATIO,
    ),
    UnknownVariable(
        variable_id="ERP_CONSTRAINTS",
        label="ERP and integration constraints",
        question_text=(
            "Which ERP do you run, and is host-to-host or API connectivity already in place "
            "with any bank?"
        ),
        role=StakeholderRole.CIO_TECHNOLOGY,
        domains=(D.OPERATING_MODEL,),
        states=(
            ("INTEGRATION_READY", "Host-to-host already in place", 0.30, 1.45),
            ("STANDARD_ERP", "Standard ERP, no integration yet", 0.45, 1.00),
            ("LEGACY_CONSTRAINED", "Legacy or constrained systems", 0.25, 0.45),
        ),
        cost_zar=2_000.0,
        delay_days=6,
        changes_rank=True,
        changes_bundle=False,
        changes_feasibility=True,
        changes_abstention=True,
        relevant_problems=(
            P.PAYMENTS_INEFFICIENCY,
            P.COLLECTIONS_INEFFICIENCY,
            P.TREASURY_CENTRALISATION,
            P.OPERATIONAL_RESILIENCE,
        ),
        resolves_gate=FeasibilityGate.TECHNOLOGY_AND_INTEGRATION,
        claim_concept="client_erp_integration_state",
    ),
    UnknownVariable(
        variable_id="COLLATERAL_CONSTRAINTS",
        label="Collateral and guarantee constraints",
        question_text=(
            "What collateral is already pledged, and are there negative-pledge or "
            "cross-default constraints on new guarantees?"
        ),
        role=StakeholderRole.RISK_LEGAL,
        domains=(D.FUNDING_STRUCTURE, D.BUSINESS_AND_FINANCIAL_RISKS),
        states=(
            ("UNENCUMBERED", "Material unencumbered collateral", 0.30, 1.40),
            ("PARTIALLY_ENCUMBERED", "Partially encumbered", 0.45, 1.00),
            ("FULLY_ENCUMBERED", "Fully encumbered or restricted", 0.25, 0.35),
        ),
        cost_zar=7_500.0,
        delay_days=12,
        changes_rank=True,
        changes_bundle=True,
        changes_feasibility=True,
        changes_abstention=True,
        relevant_problems=(
            P.GUARANTEE_OR_COLLATERAL_REQUIREMENT,
            P.REFINANCING_CLIFF,
            P.PROJECT_MOBILISATION,
        ),
        resolves_gate=FeasibilityGate.CREDIT_AND_RISK,
        claim_concept="client_collateral_position",
    ),
    UnknownVariable(
        variable_id="PROJECT_SPV_STATUS",
        label="Project and SPV status",
        question_text=(
            "Are any projects or SPVs currently being structured, and at what stage are they?"
        ),
        role=StakeholderRole.CORPORATE_DEVELOPMENT,
        domains=(D.PROJECTS_SUBSIDIARIES_SPVS,),
        states=(
            ("ACTIVE_PIPELINE", "Active project pipeline", 0.30, 1.90),
            ("EARLY_STAGE", "Early-stage evaluation only", 0.35, 1.05),
            ("NONE", "No active projects", 0.35, 0.10),
        ),
        cost_zar=6_500.0,
        delay_days=11,
        changes_rank=True,
        changes_bundle=True,
        changes_feasibility=True,
        changes_abstention=True,
        relevant_problems=(P.PROJECT_MOBILISATION, P.GUARANTEE_OR_COLLATERAL_REQUIREMENT),
        relevant_solutions=(S.PROJECT_FINANCE, S.GUARANTEES_AND_LC, S.ESCROW_AND_AGENCY),
        claim_concept="client_project_spv_status",
        claim_kind=BusinessClaimKind.EVENT_OR_PROJECT,
    ),
    UnknownVariable(
        variable_id="DECISION_AUTHORITY",
        label="Decision authority",
        question_text=(
            "Who signs off a mandate of this size, and does it require board approval?"
        ),
        role=StakeholderRole.CFO,
        domains=(D.STAKEHOLDER_RESPONSIBILITY,),
        states=(
            ("DELEGATED", "Delegated to management", 0.40, 1.35),
            ("EXECUTIVE", "Executive committee", 0.35, 1.00),
            ("BOARD", "Board approval required", 0.25, 0.60),
        ),
        cost_zar=1_200.0,
        delay_days=3,
        changes_rank=True,
        changes_bundle=False,
        changes_feasibility=False,
        changes_abstention=True,
        claim_concept="client_decision_authority",
    ),
)

QUESTIONS_BY_ID: Mapping[str, UnknownVariable] = {
    item.variable_id: item for item in QUESTION_LIBRARY
}


class VOIEngine:
    version = VOI_POLICY_VERSION

    def __init__(self, draws: int = VOI_DRAWS) -> None:
        self.draws = draws

    def _applicable(
        self,
        problem: BusinessProblem,
        solutions: Sequence[BankingSolution],
        unknown_gates: Sequence[FeasibilityGate],
    ) -> List[UnknownVariable]:
        chosen: List[UnknownVariable] = []
        for variable in QUESTION_LIBRARY:
            if variable.relevant_problems and problem in variable.relevant_problems:
                chosen.append(variable)
                continue
            if variable.relevant_solutions and set(variable.relevant_solutions) & set(
                solutions
            ):
                chosen.append(variable)
                continue
            if variable.resolves_gate and variable.resolves_gate in unknown_gates:
                chosen.append(variable)
                continue
            if not variable.relevant_problems and not variable.relevant_solutions:
                chosen.append(variable)
        return chosen

    def evaluate(
        self,
        *,
        entity_id: str,
        conversation_id: str,
        problem: BusinessProblem,
        solutions: Sequence[BankingSolution],
        unknown_gates: Sequence[FeasibilityGate],
        utility_draws: np.ndarray,
        alternative_utility: float,
    ) -> List[InformationQuestion]:
        """Score every applicable question and return them ranked by net VOI.

        ``utility_draws`` are the conversation's adjusted-benefit draws.
        ``alternative_utility`` is the best the banker could do instead — the
        opportunity cost of spending the slot here.
        """
        applicable = self._applicable(problem, solutions, unknown_gates)
        if not applicable or utility_draws.size == 0:
            return []

        baseline = float(np.mean(utility_draws))
        best_without = max(baseline, alternative_utility)
        # Value scale: convert the 0-1 adjusted benefit into ZAR so that cost
        # and delay are comparable.  The scale is governed policy, watermarked
        # with the rest of the demo economics.
        scale = 2_500_000.0
        results: List[InformationQuestion] = []

        for variable in applicable:
            rng = np.random.default_rng(_seed(f"{conversation_id}:{variable.variable_id}"))
            index = rng.integers(0, utility_draws.size, size=self.draws)
            common = utility_draws[index]
            expected_with_answer = 0.0
            states: List[AnswerState] = []
            for state_id, label, probability, shift in variable.states:
                # After the answer the banker re-optimises: they take this
                # conversation or the best alternative, whichever is higher.
                posterior = np.clip(common * shift, 0.0, 1.0)
                value = max(float(np.mean(posterior)), alternative_utility)
                expected_with_answer += probability * value
                states.append(
                    AnswerState(
                        state_id=state_id,
                        label=label,
                        probability=probability,
                        implied_shift=shift,
                    )
                )
            gross = (expected_with_answer - best_without) * scale
            delay_penalty = baseline * scale * 0.004 * variable.delay_days
            net = gross - variable.cost_zar - delay_penalty
            can_change = any(
                (
                    variable.changes_rank,
                    variable.changes_bundle,
                    variable.changes_feasibility,
                    variable.changes_abstention,
                )
            )
            results.append(
                InformationQuestion(
                    question_id=f"question:{conversation_id}:{variable.variable_id}",
                    entity_id=entity_id,
                    conversation_id=conversation_id,
                    variable_id=variable.variable_id,
                    variable_label=variable.label,
                    question_text=variable.question_text,
                    stakeholder_role=variable.role,
                    answer_states=states,
                    expected_utility_with_answer=expected_with_answer,
                    expected_utility_without_answer=best_without,
                    cost_zar=variable.cost_zar,
                    delay_penalty_zar=max(0.0, delay_penalty),
                    net_voi_zar=net,
                    can_change_rank=variable.changes_rank,
                    can_change_bundle=variable.changes_bundle,
                    can_change_feasibility=variable.changes_feasibility,
                    can_change_abstention=variable.changes_abstention,
                    scenario_draws=self.draws,
                    selected=bool(net > 0 and can_change),
                    policy_version=VOI_POLICY_VERSION,
                )
            )
        results.sort(key=lambda item: (-item.net_voi_zar, item.question_id))
        # One primary and up to two alternatives, all of which must be positive.
        for position, question in enumerate(results):
            if position >= 3 and question.selected:
                results[position] = question.model_copy(update={"selected": False})
        return results


class ClientAnswerWorkflow:
    """The reviewed-answer loop.

    A submitted answer creates a pending E2 candidate.  It records source,
    respondent, consent, scope and validity.  It cannot update an approved
    model while pending.  On approval it becomes a new point-in-time evidence
    version, and only then may the twin, graph, intervals and weekly plan be
    rebuilt.
    """

    version = VOI_POLICY_VERSION

    def __init__(self, as_of: date) -> None:
        self.as_of = as_of
        self.answers: Dict[str, ClientAnswer] = {}

    def submit(
        self,
        *,
        answer_id: str,
        question: InformationQuestion,
        answer_state_id: str,
        respondent_role: StakeholderRole,
        respondent_type: str,
        consent_reference: str,
        scope: str,
        source: str,
        free_text: Optional[str] = None,
        valid_to: Optional[date] = None,
    ) -> ClientAnswer:
        valid_states = {state.state_id for state in question.answer_states}
        if answer_state_id not in valid_states:
            raise ValueError(f"unknown answer state: {answer_state_id}")
        answer = ClientAnswer(
            answer_id=answer_id,
            question_id=question.question_id,
            entity_id=question.entity_id,
            respondent_role=respondent_role,
            respondent_type=respondent_type,
            answer_state_id=answer_state_id,
            free_text=free_text,
            consent_reference=consent_reference,
            scope=scope,
            valid_from=self.as_of,
            valid_to=valid_to,
            source=source,
            submitted_at=datetime.now(timezone.utc),
            approval_status=ApprovalStatus.PENDING_REVIEW,
            tier=EvidenceTier.E2,
        )
        self.answers[answer_id] = answer
        return answer

    def approve(
        self, answer_id: str, *, reviewer_id: str, reviewer_role: str
    ) -> Tuple[ClientAnswer, BusinessEvidenceClaim]:
        answer = self.answers[answer_id]
        if answer.approval_status is ApprovalStatus.APPROVED:
            raise ValueError("answer is already approved")
        variable = QUESTIONS_BY_ID[answer.question_id.rsplit(":", 1)[-1]]
        now = datetime.now(timezone.utc)
        claim_id = f"bec:{answer.entity_id}:e2:{variable.variable_id.lower()}:{answer.answer_id}"
        claim = BusinessEvidenceClaim(
            claim_id=claim_id,
            entity_id=answer.entity_id,
            domains=list(variable.domains),
            kind=BusinessClaimKind.CATEGORICAL,
            concept=variable.claim_concept or variable.variable_id.lower(),
            categorical_value=answer.answer_state_id,
            text_value=answer.free_text,
            unit="client_attested_state",
            period_start=answer.valid_from,
            period_end=answer.valid_from,
            source_date=answer.valid_from,
            available_date=answer.valid_from,
            source_title=f"Client/RM attestation — {variable.label}",
            source_url=f"internal://v31/client-answers/{answer.answer_id}",
            source_hash=hashlib.sha256(
                f"{answer.answer_id}:{answer.answer_state_id}".encode("utf-8")
            ).hexdigest(),
            extraction_method="structured client or RM attestation captured against a governed question",
            tier=EvidenceTier.E2,
            claim_class=ClaimClass.OBSERVED,
            provenance=DataProvenanceClass.CLIENT_ATTESTED,
            approval_status=ApprovalStatus.APPROVED,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            reviewed_at=now,
            material=True,
            critical_path=True,
            metadata=CuratedMetadata(
                business_key=claim_id,
                source_system_key=f"v31-client-answer:{answer.answer_id}",
                event_time=answer.submitted_at,
                valid_from=datetime.combine(
                    answer.valid_from, datetime.min.time(), tzinfo=timezone.utc
                ),
                ingestion_time=now,
                source_hash=hashlib.sha256(
                    answer.answer_id.encode("utf-8")
                ).hexdigest(),
                transformation_version=VOI_POLICY_VERSION,
                data_owner="Client Coverage",
                entitlement_domain=f"client:{answer.entity_id}",
            ),
        )
        approved = answer.model_copy(
            update={
                "approval_status": ApprovalStatus.APPROVED,
                "reviewer_id": reviewer_id,
                "reviewed_at": now,
                "resulting_claim_id": claim.claim_id,
            }
        )
        self.answers[answer_id] = approved
        return approved, claim

    def reject(self, answer_id: str, *, reviewer_id: str) -> ClientAnswer:
        answer = self.answers[answer_id]
        rejected = answer.model_copy(
            update={
                "approval_status": ApprovalStatus.REJECTED,
                "reviewer_id": reviewer_id,
                "reviewed_at": datetime.now(timezone.utc),
            }
        )
        self.answers[answer_id] = rejected
        return rejected

    def pending(self) -> List[ClientAnswer]:
        return [
            answer
            for answer in self.answers.values()
            if answer.approval_status is ApprovalStatus.PENDING_REVIEW
        ]
