"""Solution-family estimators for all sixteen banking solutions.

Every solution is quantified, but the *quantity* is chosen to match the
solution.  A hedging notional is not a wallet, a contingent guarantee is not a
funded exposure and an advisory mandate fee is not a transaction margin.
Conflating them would produce a comparable-looking number that means nothing.

The five V3 products keep their existing identification bounds and posterior
wallet engines untouched â€” the V3.0 regression boundary depends on that.  The
eleven new solutions each implement:

* identification bounds derived independently of the probabilistic layer;
* a need probability (POSTERIOR for the five calibrated products) or a governed
  scenario likelihood (SCENARIO for the eleven new ones);
* an amount or exposure interval;
* timing;
* evidence and artifact lineage;
* fail-closed behaviour when a required input is unavailable.

Every new solution stays ``SCENARIO`` until its own empirical calibration gate
passes.  Failing closed is the default: an estimator that cannot support a
number returns ``available=False`` with a reason, never a plausible guess.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from wallet_twin_v2.contracts import ClaimClass, EvidenceTier
from wallet_twin_v2.contracts import OpportunityView

from .business_evidence import BusinessEvidenceRegistry
from .contracts import (
    BusinessEvent,
    BusinessTwinSnapshot,
    IndicatorValue,
    ProblemHypothesis,
    SignedInterval,
    SolutionEstimate,
)
from .taxonomy import (
    BankingSolution as S,
    BusinessProblem as P,
    PRINCIPAL_QUANTITY,
    SOLUTION_FAMILY,
    SOLUTION_LABELS,
    SOLUTION_LEGACY_PRODUCT,
)

ESTIMATOR_VERSION = "v31-solution-estimators-3.1.1"

LEGACY_CALIBRATION = "V3_POSTERIOR_WALLET_ENGINE_REPRESENTATIVE_VALIDATION"
NEW_CALIBRATION = (
    "GOVERNED_SCENARIO_NOT_EMPIRICALLY_CALIBRATED â€” this solution family has no "
    "adjudicated outcome history, so its estimate is a scenario pending calibration"
)
LEGACY_STATUS = "SHADOW_ELIGIBLE_REPRESENTATIVE"
NEW_STATUS = "SCENARIO_BLOCKED_PENDING_CALIBRATION"

#: Governed conversion ranges.  Each is a policy band with a stated rationale,
#: not a fitted parameter, and each is shown to the reviewer.
SCF_ELIGIBLE_PAYABLE_RANGE = (0.15, 0.30, 0.45)
GUARANTEE_COVER_RANGE = (0.10, 0.20, 0.30)
IRRM_HEDGEABLE_SHARE = (0.30, 0.55, 0.80)
COMMODITY_HEDGEABLE_SHARE = (0.15, 0.35, 0.60)
REVOLVER_SIZING_RANGE = (1.00, 1.25, 1.60)
TERM_SIZING_RANGE = (0.90, 1.10, 1.40)


def _interval(low: float, mid: float, high: float, unit: str = "ZAR") -> SignedInterval:
    values = sorted((low, mid, high))
    return SignedInterval(
        lower=values[0], median=values[1], upper=values[2], unit=unit
    )


def _scaled(base: float, band: Tuple[float, float, float]) -> SignedInterval:
    return _interval(base * band[0], base * band[1], base * band[2])


class SolutionContext:
    """Everything an estimator is allowed to see."""

    def __init__(
        self,
        *,
        entity_id: str,
        as_of: date,
        registry: BusinessEvidenceRegistry,
        twin: BusinessTwinSnapshot,
        problems: Mapping[P, ProblemHypothesis],
        events: Sequence[BusinessEvent],
        legacy_opportunities: Mapping[str, OpportunityView],
        v3_needs: Mapping[str, Any],
        v3_changes: Mapping[str, Any],
    ) -> None:
        self.entity_id = entity_id
        self.as_of = as_of
        self.registry = registry
        self.twin = twin
        self.problems = problems
        self.events = {event.event_type: event for event in events}
        self.event_list = list(events)
        self.legacy = legacy_opportunities
        self.v3_needs = v3_needs
        self.v3_changes = v3_changes
        self.claims = {claim.concept: claim for claim in registry.claims_for(entity_id)}
        self.indicators: Dict[str, IndicatorValue] = {}
        for component in twin.components:
            for indicator in component.indicators:
                self.indicators[indicator.indicator_id] = indicator

    def money(self, concept: str) -> Optional[float]:
        claim = self.claims.get(concept)
        return float(claim.money_value) if claim is not None and claim.money_value else None

    def claim_id(self, concept: str) -> List[str]:
        claim = self.claims.get(concept)
        return [claim.claim_id] if claim is not None else []

    def indicator(self, key: str) -> Optional[IndicatorValue]:
        value = self.indicators.get(key)
        return value if value is not None and value.available else None

    def problem(self, problem: P) -> ProblemHypothesis:
        return self.problems[problem]

    def legacy_opportunity(self, product: str) -> Optional[OpportunityView]:
        return self.legacy.get(f"{self.entity_id}:{product}")


class SolutionEstimator:
    """Builds one (client, solution) projection."""

    version = ESTIMATOR_VERSION

    def estimate(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        builder = _ESTIMATORS[solution]
        return builder(self, solution, context)

    def estimate_all(self, context: SolutionContext) -> Dict[S, SolutionEstimate]:
        return {solution: self.estimate(solution, context) for solution in S}

    # -- shared constructors ----------------------------------------------
    def _unavailable(
        self,
        solution: S,
        context: SolutionContext,
        reason: str,
        *,
        assumptions: Sequence[str] = (),
    ) -> SolutionEstimate:
        return SolutionEstimate(
            estimate_id=f"solution:{context.entity_id}:{solution.value.lower()}",
            entity_id=context.entity_id,
            solution=solution,
            solution_label=SOLUTION_LABELS[solution],
            family=SOLUTION_FAMILY[solution],
            principal_quantity=PRINCIPAL_QUANTITY[solution],
            as_of=context.as_of,
            available=False,
            unavailable_reason=reason,
            need_semantics="NOT_ESTIMATED_FAIL_CLOSED",
            claim_class=ClaimClass.SCENARIO,
            evidence_tier=EvidenceTier.E0,
            calibration_status=NEW_CALIBRATION,
            model_status="FAIL_CLOSED_REQUIRED_INPUT_UNAVAILABLE",
            evidence_claim_ids=[],
            assumptions=list(assumptions),
            estimator_version=ESTIMATOR_VERSION,
        )

    def _available(
        self,
        solution: S,
        context: SolutionContext,
        *,
        amount: SignedInterval,
        bounds: Optional[SignedInterval],
        need: Optional[float],
        need_semantics: str,
        claim_class: ClaimClass,
        tier: EvidenceTier,
        calibration: str,
        model_status: str,
        claim_ids: Sequence[str],
        assumptions: Sequence[str],
        timing: Tuple[float, float, float],
        legacy_opportunity_id: Optional[str] = None,
        bounds_semantics: str = "AMOUNT_WITHIN_BOUNDS",
    ) -> SolutionEstimate:
        return SolutionEstimate(
            estimate_id=f"solution:{context.entity_id}:{solution.value.lower()}",
            entity_id=context.entity_id,
            solution=solution,
            solution_label=SOLUTION_LABELS[solution],
            family=SOLUTION_FAMILY[solution],
            principal_quantity=PRINCIPAL_QUANTITY[solution],
            as_of=context.as_of,
            available=True,
            identification_bounds=bounds,
            bounds_semantics=bounds_semantics,
            amount_interval=amount,
            need_probability=need,
            need_semantics=need_semantics,
            timing_probability_30d=timing[0],
            timing_probability_60d=timing[1],
            timing_probability_90d=timing[2],
            claim_class=claim_class,
            evidence_tier=tier,
            calibration_status=calibration,
            model_status=model_status,
            evidence_claim_ids=sorted(set(claim_ids)),
            legacy_opportunity_id=legacy_opportunity_id,
            assumptions=list(assumptions),
            estimator_version=ESTIMATOR_VERSION,
        )

    # -- timing helpers ----------------------------------------------------
    @staticmethod
    def _timing_from_problem(hypothesis: ProblemHypothesis) -> Tuple[float, float, float]:
        base = min(0.85, max(0.05, (hypothesis.probability or 0.0)))
        return (base * 0.45, base * 0.75, base)

    @staticmethod
    def _timing_from_legacy(opportunity: OpportunityView) -> Tuple[float, float, float]:
        timing = opportunity.timing
        return (timing.probability_30d, timing.probability_60d, timing.probability_90d)

    # -- legacy five -------------------------------------------------------
    def _legacy(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        product = SOLUTION_LEGACY_PRODUCT[solution]
        opportunity = context.legacy_opportunity(product)
        if opportunity is None:
            return self._unavailable(
                solution,
                context,
                f"No V3 posterior wallet exists for {product} at this snapshot.",
            )
        posterior = opportunity.posterior_wallet
        bounds = opportunity.identification_bounds
        need = next(
            (
                item.product_need_probability
                for item in context.v3_needs.values()
                if item.entity_id == context.entity_id and item.product == product
            ),
            None,
        )
        return self._available(
            solution,
            context,
            amount=_interval(posterior.lower, posterior.median, posterior.upper),
            bounds=_interval(bounds.lower, bounds.median, bounds.upper),
            need=need,
            need_semantics=(
                "POSTERIOR â€” Elkan-Noto positive-unlabelled estimate under the SCAR "
                "assumption, inherited unchanged from V3"
            ),
            claim_class=ClaimClass.POSTERIOR,
            tier=opportunity.evidence_tier,
            calibration=LEGACY_CALIBRATION,
            model_status=LEGACY_STATUS,
            claim_ids=[
                f"bec:{fact_id}" for fact_id in opportunity.evidence_fact_ids
            ],
            assumptions=[
                "Wallet, share and bounds are the frozen V3 estimates; V3.1 does not "
                "re-derive them.",
                "Share remains an identified bound plus a prior, never a measurement of "
                "competitor activity.",
                "The identification bound is a public-anchor range on total addressable "
                "activity; the amount is the shrunk posterior wallet, so the amount "
                "normally sits below the anchor range.",
            ],
            timing=self._timing_from_legacy(opportunity),
            legacy_opportunity_id=opportunity.opportunity_id,
            bounds_semantics="BOUNDS_ARE_PUBLIC_ANCHOR_ON_TOTAL_ADDRESSABLE_ACTIVITY",
        )

    # -- supply-chain finance ---------------------------------------------
    def _supply_chain_finance(
        self, solution: S, context: SolutionContext
    ) -> SolutionEstimate:
        payments = context.money("bank_observed_payments_ltm")
        audited_payables = context.money("trade_payables_close") or context.money(
            "trade_payables"
        )
        if payments is None and audited_payables is None:
            return self._unavailable(
                solution,
                context,
                "Neither bank-observed supplier payments nor an audited payables balance "
                "is available, so no eligible supplier flow can be bounded.",
            )
        base = payments if payments is not None else 0.0
        claim_ids = context.claim_id("bank_observed_payments_ltm")
        # Observed supplier payments are a strict lower bound on total payables
        # flow: the bank cannot see payments routed elsewhere.
        bounds = _interval(base, base * 1.6, base * 3.0)
        amount = _scaled(base, SCF_ELIGIBLE_PAYABLE_RANGE)
        problem = context.problem(P.SUPPLY_CHAIN_RISK)
        return self._available(
            solution,
            context,
            amount=amount,
            bounds=bounds,
            need=problem.probability,
            need_semantics=(
                "SCENARIO â€” governed weight from the supply-chain-risk detector, not a "
                "calibrated probability"
            ),
            claim_class=ClaimClass.SCENARIO,
            tier=EvidenceTier.E0,
            calibration=NEW_CALIBRATION,
            model_status=NEW_STATUS,
            claim_ids=claim_ids,
            assumptions=[
                "Eligible payable flow is 15-45% of observed supplier payments; supplier "
                "concentration and payment terms are unknown.",
                "Bank-observed payments are a lower bound on total payables flow.",
            ],
            timing=self._timing_from_problem(problem),
            bounds_semantics="BOUNDS_ARE_TOTAL_PAYABLE_FLOW_AMOUNT_IS_ELIGIBLE_SUBSET",
        )

    # -- guarantees --------------------------------------------------------
    def _guarantees(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        problem = context.problem(P.GUARANTEE_OR_COLLATERAL_REQUIREMENT)
        pipeline = context.events.get("TRADE_EVENT_PIPELINE")
        if pipeline is None or pipeline.magnitude is None:
            return self._unavailable(
                solution,
                context,
                "No dated contract or trade pipeline is observed, so contingent exposure "
                "cannot be sized.",
            )
        base = pipeline.magnitude.median
        return self._available(
            solution,
            context,
            amount=_scaled(base, GUARANTEE_COVER_RANGE),
            bounds=_interval(0.0, base * 0.5, base),
            need=problem.probability,
            need_semantics="SCENARIO â€” governed guarantee-requirement weight",
            claim_class=ClaimClass.SCENARIO,
            tier=EvidenceTier.E0,
            calibration=NEW_CALIBRATION,
            model_status=NEW_STATUS,
            claim_ids=list(pipeline.evidence_claim_ids),
            assumptions=[
                "Guarantee cover is 10-30% of dated contract value per governed policy.",
                "Existing contingent lines held with other banks are not visible.",
            ],
            timing=self._timing_from_problem(problem),
            bounds_semantics="BOUNDS_ARE_UNDERLYING_CONTRACT_VALUE_AMOUNT_IS_CONTINGENT_COVER",
        )

    # -- working-capital revolver -----------------------------------------
    def _revolver(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        gap = context.indicator("WORKING_CAPITAL_GAP")
        if gap is None or gap.interval.median <= 0:
            return self._unavailable(
                solution,
                context,
                "No positive working-capital gap can be computed from reviewed evidence, "
                "so a revolving facility cannot be sized.",
                assumptions=[
                    "Sizing a revolver without a measured gap would invent a credit need."
                ],
            )
        base = gap.interval.median
        problem = context.problem(P.WORKING_CAPITAL_PRESSURE)
        return self._available(
            solution,
            context,
            amount=_scaled(base, REVOLVER_SIZING_RANGE),
            bounds=_interval(gap.interval.lower, base, gap.interval.upper),
            need=problem.probability,
            need_semantics="SCENARIO â€” governed working-capital-pressure weight",
            claim_class=ClaimClass.SCENARIO,
            tier=EvidenceTier.E1,
            calibration=NEW_CALIBRATION,
            model_status=NEW_STATUS,
            claim_ids=list(gap.evidence_claim_ids),
            assumptions=[
                "Facility sizing is 1.0-1.6x the measured gap to allow for seasonality.",
                "Existing undrawn facilities with other banks are not visible.",
            ],
            timing=self._timing_from_problem(problem),
            bounds_semantics="BOUNDS_ARE_MEASURED_GAP_AMOUNT_ADDS_GOVERNED_SEASONAL_HEADROOM",
        )

    # -- term lending ------------------------------------------------------
    def _term_lending(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        exposure = context.indicator("REFINANCING_EXPOSURE_12M")
        maturity = context.claims.get("current_debt_maturity_window") or context.claims.get(
            "current_debt"
        )
        if exposure is None and maturity is None:
            return self._unavailable(
                solution,
                context,
                "No maturing debt or refinancing exposure is disclosed, so a term facility "
                "cannot be sized.",
            )
        if exposure is not None and exposure.interval.median > 0:
            base = exposure.interval.median
            claim_ids = list(exposure.evidence_claim_ids)
            bounds = _interval(
                exposure.interval.lower, base, exposure.interval.upper
            )
        elif maturity is not None and maturity.money_value:
            base = float(maturity.money_value)
            claim_ids = [maturity.claim_id]
            bounds = _interval(0.0, base * 0.5, base)
        else:
            return self._unavailable(
                solution,
                context,
                "Disclosed liquidity already exceeds maturing debt, so no term financing "
                "requirement is identified.",
            )
        problem = context.problem(P.REFINANCING_CLIFF)
        return self._available(
            solution,
            context,
            amount=_scaled(base, TERM_SIZING_RANGE),
            bounds=bounds,
            need=problem.probability,
            need_semantics="SCENARIO â€” governed refinancing-cliff weight",
            claim_class=ClaimClass.SCENARIO,
            tier=EvidenceTier.E1,
            calibration=NEW_CALIBRATION,
            model_status=NEW_STATUS,
            claim_ids=claim_ids,
            assumptions=[
                "Facility sizing is 0.9-1.4x the disclosed maturing amount.",
                "The full maturity ladder by instrument and tenor is not public.",
            ],
            timing=self._timing_from_problem(problem),
            bounds_semantics="BOUNDS_ARE_DISCLOSED_MATURING_DEBT_AMOUNT_IS_FACILITY_SIZE",
        )

    # -- debt capital markets ---------------------------------------------
    def _dcm(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        exposure = context.indicator("REFINANCING_EXPOSURE_12M")
        maturity = context.claims.get("current_debt_maturity_window") or context.claims.get(
            "current_debt"
        )
        if maturity is None or not maturity.money_value:
            return self._unavailable(
                solution,
                context,
                "No disclosed financing requirement exists, so a DCM mandate cannot be sized.",
            )
        base = (
            exposure.interval.median
            if exposure is not None and exposure.interval.median > 0
            else float(maturity.money_value)
        )
        problem = context.problem(P.REFINANCING_CLIFF)
        return self._available(
            solution,
            context,
            amount=_interval(base * 0.8, base, base * 1.3),
            bounds=_interval(0.0, base * 0.5, base * 1.3),
            need=problem.probability,
            need_semantics=(
                "SCENARIO â€” refinancing weight combined with the funding-route scorecard; "
                "route probability is reported separately"
            ),
            claim_class=ClaimClass.SCENARIO,
            tier=EvidenceTier.E1,
            calibration=NEW_CALIBRATION,
            model_status=NEW_STATUS,
            claim_ids=[maturity.claim_id],
            assumptions=[
                "A DCM route requires an issuer rating or an established programme; "
                "neither is confirmed in the demonstration.",
                "Indicative mandate economics depend on an approved rate card that does "
                "not exist for this family.",
            ],
            timing=self._timing_from_problem(problem),
        )

    # -- project finance ---------------------------------------------------
    def _project_finance(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        return self._unavailable(
            solution,
            context,
            "No reviewed project, SPV or ring-fenced cash-flow evidence exists for this "
            "client. Project finance cannot be sized from a sector assumption, and SPV "
            "ownership is never inferred from name similarity.",
            assumptions=[
                "Requires GLEIF/registry identity resolution plus human review.",
                "Requires a project pipeline with financial-close dates.",
            ],
        )

    # -- interest-rate risk ------------------------------------------------
    def _rates(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        debt = (
            context.claims.get("current_debt")
            or context.claims.get("term_finance")
            or context.claims.get("current_liabilities")
        )
        if debt is None or not debt.money_value:
            return self._unavailable(
                solution,
                context,
                "No disclosed debt balance exists, so a hedgeable rate notional cannot be "
                "bounded.",
            )
        from .indicators import _zar

        base = _zar(float(debt.money_value), debt.currency or "ZAR", debt.unit)
        problem = context.problem(P.INTEREST_RATE_EXPOSURE)
        return self._available(
            solution,
            context,
            amount=_scaled(base, IRRM_HEDGEABLE_SHARE),
            bounds=_interval(0.0, base * 0.5, base),
            need=problem.probability,
            need_semantics="SCENARIO â€” governed interest-rate-exposure weight",
            claim_class=ClaimClass.SCENARIO,
            tier=debt.tier,
            calibration=NEW_CALIBRATION,
            model_status=NEW_STATUS,
            claim_ids=[debt.claim_id],
            assumptions=[
                "Hedgeable share is 30-80% of disclosed debt; the fixed/floating split is "
                "not disclosed.",
                "This is a risk-reduction notional, not a guaranteed interest saving.",
            ],
            timing=self._timing_from_problem(problem),
            bounds_semantics="BOUNDS_ARE_DISCLOSED_DEBT_AMOUNT_IS_HEDGEABLE_NOTIONAL",
        )

    # -- commodity risk ----------------------------------------------------
    def _commodity(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        problem = context.problem(P.COMMODITY_EXPOSURE)
        if not problem.identified:
            return self._unavailable(
                solution,
                context,
                f"The {context.twin.sector} sector carries no governed commodity price "
                "linkage, so a hedgeable commodity notional cannot be asserted.",
            )
        base = context.money("bank_observed_collections_ltm")
        if base is None:
            return self._unavailable(
                solution,
                context,
                "No observed commodity-linked inflow exists to bound a hedgeable notional.",
            )
        return self._available(
            solution,
            context,
            amount=_scaled(base, COMMODITY_HEDGEABLE_SHARE),
            bounds=_interval(0.0, base * 0.5, base),
            need=problem.probability,
            need_semantics="SCENARIO â€” governed commodity-exposure weight",
            claim_class=ClaimClass.SCENARIO,
            tier=EvidenceTier.E0,
            calibration=NEW_CALIBRATION,
            model_status=NEW_STATUS,
            claim_ids=context.claim_id("bank_observed_collections_ltm"),
            assumptions=[
                "Hedgeable share is 15-60% of observed commodity-linked inflows.",
                "Any existing hedge programme is not disclosed and may already cover this.",
                "This is a risk-reduction notional, not a guaranteed price saving.",
            ],
            timing=self._timing_from_problem(problem),
            bounds_semantics="BOUNDS_ARE_OBSERVED_INFLOW_AMOUNT_IS_HEDGEABLE_NOTIONAL",
        )

    # -- escrow and agency -------------------------------------------------
    def _escrow(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        corporate_action = context.problem(P.MA_OR_STRATEGIC_EVENT)
        capital_event = context.problem(P.CAPITAL_STRUCTURE_EVENT)
        if not (corporate_action.identified or capital_event.identified):
            return self._unavailable(
                solution,
                context,
                "Escrow and agency flow is event-linked, and no reviewed corporate action "
                "or capital-structure event exists for this client.",
                assumptions=[
                    "Requires an announced transaction, refinancing or project close."
                ],
            )
        pipeline = context.events.get("TRADE_EVENT_PIPELINE")
        base = pipeline.magnitude.median if pipeline and pipeline.magnitude else 0.0
        return self._available(
            solution,
            context,
            amount=_interval(base * 0.05, base * 0.15, base * 0.30),
            bounds=_interval(0.0, base * 0.5, base),
            need=max(corporate_action.probability or 0.0, capital_event.probability or 0.0),
            need_semantics="SCENARIO â€” governed corporate-event weight",
            claim_class=ClaimClass.SCENARIO,
            tier=EvidenceTier.E0,
            calibration=NEW_CALIBRATION,
            model_status=NEW_STATUS,
            claim_ids=[],
            assumptions=["Event-linked flow is a governed fraction of transaction value."],
            timing=self._timing_from_problem(corporate_action),
        )

    # -- sustainable finance ----------------------------------------------
    def _sustainable(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        return self._unavailable(
            solution,
            context,
            "No reviewed transition target, eligible capex programme or use-of-proceeds "
            "framework has been extracted. Sustainable finance requires evidence-qualified "
            "eligible expenditure and cannot rest on a sector assumption.",
            assumptions=[
                "Requires extracted and reviewed ESG activity evidence.",
                "Requires an approved use-of-proceeds and reporting framework.",
            ],
        )

    # -- M&A advisory ------------------------------------------------------
    def _advisory(self, solution: S, context: SolutionContext) -> SolutionEstimate:
        return self._unavailable(
            solution,
            context,
            "No announced or reviewed transaction evidence exists, so no mandate "
            "probability or transaction size can be estimated.",
            assumptions=[
                "Requires reviewed corporate-development evidence.",
                "Requires mandate conflict clearance before any approach.",
            ],
        )


_ESTIMATORS: Mapping[S, Callable[[SolutionEstimator, S, SolutionContext], SolutionEstimate]] = {
    S.COLLECTIONS: SolutionEstimator._legacy,
    S.PAYMENTS: SolutionEstimator._legacy,
    S.LIQUIDITY_CASH_MANAGEMENT: SolutionEstimator._legacy,
    S.CROSS_BORDER_FX: SolutionEstimator._legacy,
    S.TRADE_FINANCE: SolutionEstimator._legacy,
    S.SUPPLY_CHAIN_FINANCE: SolutionEstimator._supply_chain_finance,
    S.GUARANTEES_AND_LC: SolutionEstimator._guarantees,
    S.WORKING_CAPITAL_REVOLVING: SolutionEstimator._revolver,
    S.TERM_AND_SYNDICATED_LENDING: SolutionEstimator._term_lending,
    S.DEBT_CAPITAL_MARKETS: SolutionEstimator._dcm,
    S.PROJECT_FINANCE: SolutionEstimator._project_finance,
    S.INTEREST_RATE_RISK_MANAGEMENT: SolutionEstimator._rates,
    S.COMMODITY_RISK_MANAGEMENT: SolutionEstimator._commodity,
    S.ESCROW_AND_AGENCY: SolutionEstimator._escrow,
    S.SUSTAINABLE_FINANCE: SolutionEstimator._sustainable,
    S.MA_AND_STRATEGIC_ADVISORY: SolutionEstimator._advisory,
}

if set(_ESTIMATORS) != set(S):
    raise RuntimeError("every one of the sixteen solutions requires an estimator")
