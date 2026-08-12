"""Dual-value engine: client value and bank value, kept separate.

The two are never added together and never netted against each other. A banker
needs to know both "what does this do for them" and "what does this do for us",
and a single blended number destroys that distinction.

Client value separates monetised benefit from risk reduction and from
qualitative benefit. A hedge does not create a guaranteed saving â€” it changes
the distribution of outcomes â€” so hedging solutions report risk reduction and
explicitly decline to monetise it.

Bank value keeps the V2 fail-closed contribution engine and adds cost to win.
Relationship value is reported separately from direct opportunity value so the
two are never double counted. Causal incremental value stays null until a
randomized trial closes.
"""

from __future__ import annotations

from typing import List, Mapping, Optional, Sequence

from wallet_twin_v2.contracts import ClaimClass, CommercialStatus, OpportunityView

from .contracts import (
    BankValue,
    BankValueComponent,
    ClientValue,
    ClientValueComponent,
    SignedInterval,
    SolutionBundle,
    SolutionEstimate,
)
from .taxonomy import (
    BankingSolution as S,
    ClientValueStatus,
    SOLUTION_FAMILY,
    SOLUTION_LABELS,
    SOLUTION_LEGACY_PRODUCT,
    SolutionFamily,
)

VALUE_POLICY_VERSION = "v31-dual-value-3.1.1"

CLIENT_WATERMARK = (
    "REPRESENTATIVE CLIENT-VALUE SCENARIO â€” governed assumption set, not a bank offer "
    "and not a guaranteed saving"
)
BANK_WATERMARK = (
    "REPRESENTATIVE BANK ECONOMICS â€” demo rate cards are synthetic and watermarked; "
    "production requires approved rate cards for every solution"
)
RELATIONSHIP_SEMANTICS = (
    "Three-year relationship scenario shown separately from direct opportunity value. "
    "The two must never be added: the relationship figure already contains the direct "
    "opportunity in its first year."
)
DOUBLE_COUNT_GUARD = (
    "Client benefit and bank contribution are reported separately and are never netted. "
    "Shared costs (implementation, onboarding) appear once, on the side that bears them."
)

# ---------------------------------------------------------------------------
# Representative client-value assumptions.  Every one is a governed policy
# number with a stated basis, versioned and watermarked.
# ---------------------------------------------------------------------------
CCC_DAYS_RELEASED = (2.0, 5.0, 9.0)
FUNDING_SAVING_BPS = (10.0, 25.0, 45.0)
IDLE_CASH_SHARE = (0.03, 0.06, 0.10)
YIELD_IMPROVEMENT = (0.0025, 0.0060, 0.0110)
UNIT_COST_SAVING_SHARE = (0.04, 0.09, 0.16)
IMPLEMENTATION_COST = {
    SolutionFamily.TRANSACTION_BANKING: 1_200_000.0,
    SolutionFamily.RISK_MANAGEMENT: 400_000.0,
    SolutionFamily.TRADE_AND_WORKING_CAPITAL: 2_400_000.0,
    SolutionFamily.LENDING: 900_000.0,
    SolutionFamily.CAPITAL_MARKETS: 3_500_000.0,
    SolutionFamily.ADVISORY_AND_AGENCY: 1_500_000.0,
}

#: Solutions whose benefit is a change in the distribution of outcomes rather
#: than a saving.  These never produce a monetised client-value component.
RISK_REDUCTION_SOLUTIONS = frozenset(
    {
        S.CROSS_BORDER_FX,
        S.INTEREST_RATE_RISK_MANAGEMENT,
        S.COMMODITY_RISK_MANAGEMENT,
    }
)

# ---------------------------------------------------------------------------
# Representative bank cost-to-win assumptions (days and hours).
# ---------------------------------------------------------------------------
COVERAGE_HOURS: Mapping[SolutionFamily, float] = {
    SolutionFamily.TRANSACTION_BANKING: 24.0,
    SolutionFamily.RISK_MANAGEMENT: 12.0,
    SolutionFamily.TRADE_AND_WORKING_CAPITAL: 40.0,
    SolutionFamily.LENDING: 56.0,
    SolutionFamily.CAPITAL_MARKETS: 96.0,
    SolutionFamily.ADVISORY_AND_AGENCY: 80.0,
}
ONBOARDING_DAYS: Mapping[SolutionFamily, float] = {
    SolutionFamily.TRANSACTION_BANKING: 25.0,
    SolutionFamily.RISK_MANAGEMENT: 8.0,
    SolutionFamily.TRADE_AND_WORKING_CAPITAL: 35.0,
    SolutionFamily.LENDING: 20.0,
    SolutionFamily.CAPITAL_MARKETS: 30.0,
    SolutionFamily.ADVISORY_AND_AGENCY: 15.0,
}
CREDIT_LEGAL_DAYS: Mapping[SolutionFamily, float] = {
    SolutionFamily.TRANSACTION_BANKING: 3.0,
    SolutionFamily.RISK_MANAGEMENT: 10.0,
    SolutionFamily.TRADE_AND_WORKING_CAPITAL: 22.0,
    SolutionFamily.LENDING: 35.0,
    SolutionFamily.CAPITAL_MARKETS: 28.0,
    SolutionFamily.ADVISORY_AND_AGENCY: 12.0,
}
INTEGRATION_DAYS: Mapping[SolutionFamily, float] = {
    SolutionFamily.TRANSACTION_BANKING: 30.0,
    SolutionFamily.RISK_MANAGEMENT: 4.0,
    SolutionFamily.TRADE_AND_WORKING_CAPITAL: 25.0,
    SolutionFamily.LENDING: 6.0,
    SolutionFamily.CAPITAL_MARKETS: 5.0,
    SolutionFamily.ADVISORY_AND_AGENCY: 3.0,
}
COVERAGE_HOURLY_COST = 1_450.0
SPECIALIST_DAILY_COST = 9_800.0
RELATIONSHIP_HORIZON_YEARS = 3
RELATIONSHIP_DISCOUNT_RATE = 0.11
RELATIONSHIP_RETENTION = (0.55, 0.72, 0.86)


def _interval(low: float, mid: float, high: float) -> SignedInterval:
    values = sorted((low, mid, high))
    return SignedInterval(lower=values[0], median=values[1], upper=values[2])


class ClientValueEngine:
    version = VALUE_POLICY_VERSION

    def evaluate(
        self,
        entity_id: str,
        bundle: SolutionBundle,
        estimates: Sequence[SolutionEstimate],
        *,
        ccc_days: Optional[float] = None,
        daily_operating_cost: Optional[float] = None,
    ) -> ClientValue:
        components: List[ClientValueComponent] = []
        non_monetised: List[str] = []
        assumptions: List[str] = [
            f"All monetised components use governed assumption set {VALUE_POLICY_VERSION}.",
            "Values are representative scenarios, not a bank offer.",
        ]
        risk_statements: List[str] = []

        for estimate in estimates:
            solution = estimate.solution
            label = SOLUTION_LABELS[solution]
            if not estimate.available or estimate.amount_interval is None:
                components.append(
                    ClientValueComponent(
                        component_id=f"cv:{entity_id}:{solution.value.lower()}",
                        label=f"{label} client benefit",
                        status=ClientValueStatus.UNAVAILABLE,
                        dimension="unavailable",
                        qualitative_statement=(
                            estimate.unavailable_reason
                            or "No quantity is available for this solution."
                        ),
                    )
                )
                non_monetised.append(f"{label}: not quantifiable from reviewed evidence")
                continue

            base = estimate.amount_interval.median

            if solution in RISK_REDUCTION_SOLUTIONS:
                statement = (
                    f"{label} reduces the variance of outcomes on an exposure of about "
                    f"ZAR {base:,.0f}. It does not create a guaranteed saving, and the "
                    "realised effect depends on where the market actually moves."
                )
                components.append(
                    ClientValueComponent(
                        component_id=f"cv:{entity_id}:{solution.value.lower()}",
                        label=f"{label} risk reduction",
                        status=ClientValueStatus.QUALITATIVE,
                        dimension="risk_reduction",
                        qualitative_statement=statement,
                        assumptions=[
                            "Hedge effectiveness and existing hedge ratio are unknown."
                        ],
                        evidence_claim_ids=list(estimate.evidence_claim_ids),
                    )
                )
                risk_statements.append(statement)
                non_monetised.append(f"{label}: risk reduction, deliberately not monetised")
                continue

            component = self._monetised_component(
                entity_id,
                solution,
                estimate,
                ccc_days=ccc_days,
                daily_operating_cost=daily_operating_cost,
            )
            components.append(component)
            if component.status is ClientValueStatus.QUALITATIVE:
                non_monetised.append(f"{label}: {component.dimension}")

        monetised = [
            component.interval
            for component in components
            if component.status
            in (ClientValueStatus.MONETISED, ClientValueStatus.PROXY)
            and component.interval is not None
        ]
        total: Optional[SignedInterval] = None
        if monetised:
            total = SignedInterval(
                lower=sum(item.lower for item in monetised),
                median=sum(item.median for item in monetised),
                upper=sum(item.upper for item in monetised),
            )

        return ClientValue(
            entity_id=entity_id,
            monetised_total=total,
            components=components,
            non_monetised_dimensions=sorted(set(non_monetised)),
            risk_reduction_statement=" ".join(risk_statements) or None,
            guaranteed_saving_claimed=False,
            assumptions=assumptions,
            claim_class=ClaimClass.SCENARIO,
            watermark=CLIENT_WATERMARK,
        )

    def _monetised_component(
        self,
        entity_id: str,
        solution: S,
        estimate: SolutionEstimate,
        *,
        ccc_days: Optional[float],
        daily_operating_cost: Optional[float],
    ) -> ClientValueComponent:
        label = SOLUTION_LABELS[solution]
        base = estimate.amount_interval.median
        component_id = f"cv:{entity_id}:{solution.value.lower()}"
        family = SOLUTION_FAMILY[solution]
        implementation = IMPLEMENTATION_COST[family]

        if solution in (S.SUPPLY_CHAIN_FINANCE, S.TRADE_FINANCE, S.WORKING_CAPITAL_REVOLVING):
            if daily_operating_cost is None:
                return ClientValueComponent(
                    component_id=component_id,
                    label=f"{label} working-capital release",
                    status=ClientValueStatus.UNAVAILABLE,
                    dimension="working_capital_release",
                    qualitative_statement=(
                        "Daily operating cost is not available from reviewed evidence, so "
                        "the working-capital release cannot be monetised."
                    ),
                )
            low, mid, high = CCC_DAYS_RELEASED
            return ClientValueComponent(
                component_id=component_id,
                label=f"{label} working-capital release",
                status=ClientValueStatus.PROXY,
                formula="WorkingCapitalRelease = DailyOperatingCost x dCCC",
                interval=_interval(
                    daily_operating_cost * low,
                    daily_operating_cost * mid,
                    daily_operating_cost * high,
                ),
                dimension="working_capital_release",
                assumptions=[
                    f"Governed cycle release of {low:.0f}-{high:.0f} days"
                    + (f" against a measured cycle of {ccc_days:.0f} days." if ccc_days else "."),
                    "Release depends on supplier adoption, which is not observed.",
                ],
                evidence_claim_ids=list(estimate.evidence_claim_ids),
            )

        if solution in (S.TERM_AND_SYNDICATED_LENDING, S.DEBT_CAPITAL_MARKETS):
            low, mid, high = FUNDING_SAVING_BPS
            return ClientValueComponent(
                component_id=component_id,
                label=f"{label} funding cost saving",
                status=ClientValueStatus.PROXY,
                formula="FundingSaving = Amount x dbps x Days / (365 x 10,000)",
                interval=_interval(
                    base * low * 365 / (365 * 10_000),
                    base * mid * 365 / (365 * 10_000),
                    base * high * 365 / (365 * 10_000),
                ),
                dimension="funding_cost",
                assumptions=[
                    f"Governed spread improvement of {low:.0f}-{high:.0f} bps over a full year.",
                    "The client's current all-in funding cost is not disclosed.",
                ],
                evidence_claim_ids=list(estimate.evidence_claim_ids),
            )

        if solution is S.LIQUIDITY_CASH_MANAGEMENT:
            share_low, share_mid, share_high = IDLE_CASH_SHARE
            yield_low, yield_mid, yield_high = YIELD_IMPROVEMENT
            return ClientValueComponent(
                component_id=component_id,
                label=f"{label} liquidity benefit",
                status=ClientValueStatus.PROXY,
                formula=(
                    "LiquidityBenefit = IdleCash x YieldImprovement + AvoidedBorrowingCost"
                ),
                interval=_interval(
                    base * share_low * yield_low,
                    base * share_mid * yield_mid,
                    base * share_high * yield_high,
                ),
                dimension="liquidity_yield",
                assumptions=[
                    f"Idle balances are {share_low:.0%}-{share_high:.0%} of observed flow.",
                    f"Yield improvement of {yield_low:.2%}-{yield_high:.2%}.",
                    "Avoided borrowing cost is excluded because current drawn balances "
                    "are not disclosed; the estimate is therefore conservative.",
                ],
                evidence_claim_ids=list(estimate.evidence_claim_ids),
            )

        if solution in (S.PAYMENTS, S.COLLECTIONS):
            low, mid, high = UNIT_COST_SAVING_SHARE
            # Operational benefit is a share of the *fee* base, not of the flow.
            # Applying a unit-cost saving to gross flow would overstate the
            # benefit by orders of magnitude.
            fee_base_bps = 6.0
            fee_base = base * fee_base_bps / 10_000.0
            return ClientValueComponent(
                component_id=component_id,
                label=f"{label} operational benefit",
                status=ClientValueStatus.PROXY,
                formula=(
                    "OperationalBenefit = Volume x (UnitCost_before - UnitCost_after) "
                    "- ImplementationCost"
                ),
                interval=_interval(
                    fee_base * low - implementation,
                    fee_base * mid - implementation,
                    fee_base * high - implementation,
                ),
                dimension="operational_cost",
                assumptions=[
                    f"Transaction cost base approximated at {fee_base_bps:.0f} bps of flow.",
                    f"Unit-cost saving of {low:.0%}-{high:.0%} of that base.",
                    f"Implementation cost of ZAR {implementation:,.0f} is deducted, so a "
                    "small client can legitimately show a negative benefit.",
                ],
                evidence_claim_ids=list(estimate.evidence_claim_ids),
            )

        if solution is S.GUARANTEES_AND_LC:
            return ClientValueComponent(
                component_id=component_id,
                label=f"{label} contract enablement",
                status=ClientValueStatus.QUALITATIVE,
                dimension="contract_enablement",
                qualitative_statement=(
                    f"Guarantee capacity of about ZAR {base:,.0f} enables contract award and "
                    "release of retention. The value depends on contracts the bank cannot see, "
                    "so it is not monetised."
                ),
                evidence_claim_ids=list(estimate.evidence_claim_ids),
            )

        return ClientValueComponent(
            component_id=component_id,
            label=f"{label} client benefit",
            status=ClientValueStatus.QUALITATIVE,
            dimension="strategic",
            qualitative_statement=(
                f"{label} benefit is strategic and is not converted to ZAR without "
                "client-confirmed inputs."
            ),
            evidence_claim_ids=list(estimate.evidence_claim_ids),
        )


class BankValueEngine:
    """Fail-closed bank contribution plus cost to win and relationship scenario."""

    version = VALUE_POLICY_VERSION

    def evaluate(
        self,
        entity_id: str,
        bundle: SolutionBundle,
        estimates: Sequence[SolutionEstimate],
        legacy_opportunities: Mapping[str, OpportunityView],
    ) -> BankValue:
        components: List[BankValueComponent] = []
        reasons: List[str] = []
        rate_cards: List[str] = []
        direct_low = direct_mid = direct_high = 0.0
        approved_any = False

        for estimate in estimates:
            solution = estimate.solution
            label = SOLUTION_LABELS[solution]
            product = SOLUTION_LEGACY_PRODUCT.get(solution)
            opportunity = (
                legacy_opportunities.get(f"{entity_id}:{product}") if product else None
            )
            if opportunity is None:
                reasons.append(
                    f"NO_APPROVED_RATE_CARD_{solution.value} â€” {label} has no approved "
                    "rate card, so no contribution is published for it"
                )
                components.append(
                    BankValueComponent(
                        component_id=f"bv:{entity_id}:{solution.value.lower()}",
                        label=f"{label} contribution",
                        amount=0.0,
                        sign=0,
                        basis="BLOCKED_NO_APPROVED_RATE_CARD",
                        approved=False,
                    )
                )
                continue
            commercial = opportunity.commercial
            if commercial.status is CommercialStatus.BLOCKED:
                reasons.extend(commercial.reason_codes)
                continue
            contribution = commercial.contestable_scenario_contribution
            if contribution is None:
                reasons.append(f"NO_SCENARIO_CONTRIBUTION_{solution.value}")
                continue
            value = float(contribution.normalized_amount)
            approved_any = True
            direct_mid += value
            direct_low += value * 0.55
            direct_high += value * 1.45
            if commercial.rate_card_ref:
                rate_cards.append(commercial.rate_card_ref)
            if opportunity.artifacts.rate_card_version:
                rate_cards.append(opportunity.artifacts.rate_card_version)
            components.append(
                BankValueComponent(
                    component_id=f"bv:{entity_id}:{solution.value.lower()}",
                    label=f"{label} contestable scenario contribution",
                    amount=value,
                    sign=1,
                    basis=(
                        "V2 fail-closed contribution engine: Revenue - FTP - Liquidity - "
                        "ExpectedLoss - Capital - Hedging - Execution - Servicing - "
                        "OperatingCost"
                    ),
                    rate_card_ref=commercial.rate_card_ref,
                    approved=False,
                )
            )

        # cost to win
        families = {SOLUTION_FAMILY[estimate.solution] for estimate in estimates}
        coverage_hours = sum(COVERAGE_HOURS[family] for family in families)
        onboarding = sum(ONBOARDING_DAYS[family] for family in families)
        credit_legal = sum(CREDIT_LEGAL_DAYS[family] for family in families)
        integration = sum(INTEGRATION_DAYS[family] for family in families)
        cost_mid = (
            coverage_hours * COVERAGE_HOURLY_COST
            + (onboarding + credit_legal + integration) * SPECIALIST_DAILY_COST
        )
        cost_to_win = _interval(cost_mid * 0.7, cost_mid, cost_mid * 1.6)
        components.append(
            BankValueComponent(
                component_id=f"bv:{entity_id}:cost-to-win",
                label="Cost to win",
                amount=cost_mid,
                sign=-1,
                basis=(
                    f"{coverage_hours:.0f} coverage hours at ZAR {COVERAGE_HOURLY_COST:,.0f}/h "
                    f"plus {onboarding + credit_legal + integration:.0f} specialist days at "
                    f"ZAR {SPECIALIST_DAILY_COST:,.0f}/day"
                ),
                approved=False,
            )
        )

        if not approved_any:
            return BankValue(
                entity_id=entity_id,
                status="BLOCKED",
                direct_contribution=None,
                components=components,
                cost_to_win=cost_to_win,
                coverage_hours=coverage_hours,
                onboarding_effort_days=onboarding,
                credit_legal_effort_days=credit_legal,
                systems_integration_days=integration,
                relationship_value_3y=None,
                relationship_value_semantics=RELATIONSHIP_SEMANTICS,
                causal_status="CAUSAL_INCREMENTAL_VALUE_WITHHELD",
                double_count_guard=DOUBLE_COUNT_GUARD,
                reason_codes=sorted(set(reasons)) or ["NO_APPROVED_ECONOMICS"],
                rate_card_versions=sorted(set(rate_cards)),
                watermark=BANK_WATERMARK,
            )

        direct = _interval(
            direct_low - cost_to_win.upper,
            direct_mid - cost_to_win.median,
            direct_high - cost_to_win.lower,
        )
        relationship = self._relationship_value(direct_mid)
        return BankValue(
            entity_id=entity_id,
            status="REPRESENTATIVE_SCENARIO_NOT_BANK_APPROVED",
            direct_contribution=direct,
            components=components,
            cost_to_win=cost_to_win,
            coverage_hours=coverage_hours,
            onboarding_effort_days=onboarding,
            credit_legal_effort_days=credit_legal,
            systems_integration_days=integration,
            relationship_value_3y=relationship,
            relationship_value_semantics=RELATIONSHIP_SEMANTICS,
            causal_status="CAUSAL_INCREMENTAL_VALUE_WITHHELD",
            double_count_guard=DOUBLE_COUNT_GUARD,
            reason_codes=sorted(set(reasons)),
            rate_card_versions=sorted(set(rate_cards)),
            watermark=BANK_WATERMARK,
        )

    @staticmethod
    def _relationship_value(annual_contribution: float) -> SignedInterval:
        values = []
        for retention in RELATIONSHIP_RETENTION:
            total = 0.0
            for year in range(RELATIONSHIP_HORIZON_YEARS):
                total += (
                    annual_contribution
                    * (retention**year)
                    / ((1 + RELATIONSHIP_DISCOUNT_RATE) ** year)
                )
            values.append(total)
        return _interval(*sorted(values))


DEMO_POLICY = {
    "policy_version": VALUE_POLICY_VERSION,
    "watermarked": True,
    "client_value_assumptions": {
        "ccc_days_released": CCC_DAYS_RELEASED,
        "funding_saving_bps": FUNDING_SAVING_BPS,
        "idle_cash_share": IDLE_CASH_SHARE,
        "yield_improvement": YIELD_IMPROVEMENT,
        "unit_cost_saving_share": UNIT_COST_SAVING_SHARE,
        "implementation_cost_by_family": {
            family.value: cost for family, cost in IMPLEMENTATION_COST.items()
        },
    },
    "bank_value_assumptions": {
        "coverage_hourly_cost_zar": COVERAGE_HOURLY_COST,
        "specialist_daily_cost_zar": SPECIALIST_DAILY_COST,
        "relationship_horizon_years": RELATIONSHIP_HORIZON_YEARS,
        "relationship_discount_rate": RELATIONSHIP_DISCOUNT_RATE,
        "relationship_retention": RELATIONSHIP_RETENTION,
    },
    "production_requirement": (
        "Production outputs require approved rate cards for every one of the sixteen "
        "solutions. Eleven solutions have none, so their contribution is blocked rather "
        "than estimated."
    ),
}
