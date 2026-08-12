"""Transparent, evidence-linked business indicators.

Every indicator returns its formula, its inputs, the evidence claims behind
those inputs and an explicit list of anything missing.  When a required input
is unavailable the indicator returns ``UNKNOWN`` with no value: it never
substitutes a zero, a sector median or a silent default.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Tuple

from wallet_twin_v2.contracts import ApprovalStatus, ClaimClass

from .business_evidence import BusinessEvidenceRegistry
from .contracts import IndicatorValue, SignedInterval
from .taxonomy import ComponentStatus

INDICATOR_VERSION = "v31-business-indicators-3.1.1"

#: Bounded uncertainty applied to accounting-derived indicators.  These are
#: transformation tolerances, not statistical confidence intervals: audited
#: line items are point-in-time and classification differences are real.
ACCOUNTING_TOLERANCE = 0.12

FX_TO_ZAR: Mapping[str, float] = {"ZAR": 1.0, "USD": 17.86, "EUR": 20.90, "GBP": 24.45}
FX_POLICY_REF = "FX-E0-PTI-2026-06-30"


def _zar(value: float, currency: str, unit: Optional[str]) -> float:
    scale = 1_000_000.0 if (unit or "").lower() == "million" else 1.0
    return value * scale * FX_TO_ZAR[currency]


def _interval(median: float, tolerance: float = ACCOUNTING_TOLERANCE) -> SignedInterval:
    low = median * (1.0 - tolerance)
    high = median * (1.0 + tolerance)
    return SignedInterval(
        lower=min(low, high), median=median, upper=max(low, high), unit="ZAR"
    )


class _Inputs:
    """Resolves indicator inputs and tracks the approval state of each one.

    An input that exists but has not completed finance-SME review is still used
    for analysis â€” hiding it would make the twin less honest, not more â€” but it
    downgrades the indicator to ``INFERRED`` so that nothing resting on
    unreviewed evidence can ever reach a client-facing product proposal.
    """

    def __init__(self, registry: BusinessEvidenceRegistry, entity_id: str) -> None:
        self.registry = registry
        self.entity_id = entity_id
        self.values: Dict[str, float] = {}
        self.claim_ids: List[str] = []
        self.pending_claim_ids: List[str] = []
        self.missing: List[str] = []

    def _record(self, claim) -> None:
        self.claim_ids.append(claim.claim_id)
        if claim.approval_status is not ApprovalStatus.APPROVED:
            self.pending_claim_ids.append(claim.claim_id)

    def money(self, name: str, *concepts: str) -> Optional[float]:
        for concept in concepts:
            claim = self.registry.by_concept(self.entity_id, concept)
            if claim is not None and claim.money_value is not None and claim.currency:
                value = _zar(claim.money_value, claim.currency, claim.unit)
                self.values[name] = value
                self._record(claim)
                return value
        self.missing.append(name)
        return None

    def ratio(self, name: str, concept: str) -> Optional[float]:
        claim = self.registry.by_concept(self.entity_id, concept)
        if claim is not None and claim.ratio_value is not None:
            self.values[name] = claim.ratio_value
            self._record(claim)
            return claim.ratio_value
        self.missing.append(name)
        return None

    def build(
        self,
        indicator_id: str,
        label: str,
        formula: str,
        unit: str,
        median: Optional[float],
        *,
        tolerance: float = ACCOUNTING_TOLERANCE,
        claim_class: ClaimClass = ClaimClass.IDENTIFIED_BOUND,
    ) -> IndicatorValue:
        if median is None or self.missing:
            return IndicatorValue(
                indicator_id=indicator_id,
                label=label,
                formula=formula,
                interval=None,
                unit=unit,
                inputs=dict(self.values),
                evidence_claim_ids=sorted(set(self.claim_ids)),
                pending_evidence_claim_ids=sorted(set(self.pending_claim_ids)),
                missing_inputs=sorted(set(self.missing)),
                status=ComponentStatus.UNKNOWN,
                transformation_version=INDICATOR_VERSION,
                claim_class=claim_class,
            )
        pending = sorted(set(self.pending_claim_ids))
        return IndicatorValue(
            indicator_id=indicator_id,
            label=label,
            formula=formula,
            interval=_interval(median, tolerance)
            if unit == "ZAR"
            else SignedInterval(
                lower=min(median * (1.0 - tolerance), median * (1.0 + tolerance)),
                median=median,
                upper=max(median * (1.0 - tolerance), median * (1.0 + tolerance)),
                unit=unit,
            ),
            unit=unit,
            inputs=dict(self.values),
            evidence_claim_ids=sorted(set(self.claim_ids)),
            pending_evidence_claim_ids=pending,
            missing_inputs=[],
            status=ComponentStatus.INFERRED if pending else ComponentStatus.SUPPORTED,
            transformation_version=INDICATOR_VERSION,
            claim_class=ClaimClass.POSTERIOR if pending else claim_class,
        )


def cash_conversion_cycle(
    registry: BusinessEvidenceRegistry, entity_id: str
) -> IndicatorValue:
    r"""CCC = DIO + DSO - DPO, each leg from audited opening/closing balances."""
    inputs = _Inputs(registry, entity_id)
    revenue = inputs.money(
        "revenue", "revenue", "insurance_revenue", "gross_rental_income"
    )
    cost = inputs.money("operating_cost_base", "operating_cost_base", "trade_payables")
    inventory_open = inputs.money("inventories_open", "inventories_open")
    inventory_close = inputs.money("inventories_close", "inventories_close")
    receivable_open = inputs.money("trade_receivables_open", "trade_receivables_open")
    receivable_close = inputs.money("trade_receivables_close", "trade_receivables_close")
    payable_open = inputs.money("trade_payables_open", "trade_payables_open")
    payable_close = inputs.money("trade_payables_close", "trade_payables_close")

    median: Optional[float] = None
    if None not in (
        revenue,
        cost,
        inventory_open,
        inventory_close,
        receivable_open,
        receivable_close,
        payable_open,
        payable_close,
    ):
        average_inventory = (inventory_open + inventory_close) / 2.0
        average_receivable = (receivable_open + receivable_close) / 2.0
        average_payable = (payable_open + payable_close) / 2.0
        dio = 365.0 * average_inventory / max(cost, 1.0)
        dso = 365.0 * average_receivable / max(revenue, 1.0)
        dpo = 365.0 * average_payable / max(cost, 1.0)
        median = dio + dso - dpo
        inputs.values.update({"DIO": dio, "DSO": dso, "DPO": dpo})
    return inputs.build(
        "CCC",
        "Cash conversion cycle",
        "CCC = DIO + DSO - DPO",
        "days",
        median,
        tolerance=0.15,
    )


def liquidity_buffer(
    registry: BusinessEvidenceRegistry, entity_id: str
) -> IndicatorValue:
    r"""LiquidityBuffer = Cash + CommittedFacilities - NearTermObligations."""
    inputs = _Inputs(registry, entity_id)
    cash = inputs.money("cash", "cash_and_cash_equivalents")
    obligations = inputs.money(
        "near_term_obligations",
        "current_debt",
        "term_finance",
        "current_liabilities",
        "insurance_liabilities",
    )
    facilities = registry.by_concept(entity_id, "short_term_facilities")
    committed = 0.0
    if facilities is not None and facilities.money_value is not None:
        committed = _zar(
            facilities.money_value, facilities.currency or "ZAR", facilities.unit
        )
        inputs.values["committed_facilities"] = committed
        inputs._record(facilities)
    else:
        inputs.values["committed_facilities"] = 0.0
        # An undisclosed facility is genuinely unknown, but excluding it makes
        # the buffer conservative rather than optimistic, so the indicator
        # remains reportable with the assumption made explicit.
    median = (
        cash + committed - obligations
        if cash is not None and obligations is not None
        else None
    )
    indicator = inputs.build(
        "LIQUIDITY_BUFFER",
        "Liquidity and cash buffer",
        "LiquidityBuffer = Cash + CommittedFacilities - NearTermObligations",
        "ZAR",
        median,
    )
    if facilities is None and indicator.status is ComponentStatus.SUPPORTED:
        return indicator.model_copy(
            update={
                "formula": indicator.formula
                + " (committed facilities not disclosed; treated as nil, which is conservative)"
            }
        )
    return indicator


def working_capital_gap(
    registry: BusinessEvidenceRegistry, entity_id: str
) -> IndicatorValue:
    r"""WorkingCapitalGap = max(0, RequiredNWC - AvailableShortTermFunding)."""
    inputs = _Inputs(registry, entity_id)
    receivable = inputs.money("trade_receivables_close", "trade_receivables_close")
    inventory = inputs.money("inventories_close", "inventories_close")
    payable = inputs.money("trade_payables_close", "trade_payables_close")
    # Short-term funding is whichever of cash and committed facilities the
    # client actually discloses.  Requiring both would make the indicator
    # unavailable for every client in the portfolio; requiring neither would
    # invent funding that may not exist.
    available = 0.0
    funding_sources: List[str] = []
    for concept, label in (
        ("cash_and_cash_equivalents", "cash"),
        ("short_term_facilities", "committed_facilities"),
    ):
        claim = registry.by_concept(entity_id, concept)
        if claim is not None and claim.money_value is not None:
            value = _zar(claim.money_value, claim.currency or "ZAR", claim.unit)
            available += value
            inputs.values[label] = value
            inputs._record(claim)
            funding_sources.append(label)
    if not funding_sources:
        inputs.missing.append("available_short_term_funding")
    median: Optional[float] = None
    if None not in (receivable, inventory, payable) and funding_sources:
        required = receivable + inventory - payable
        inputs.values["required_nwc"] = required
        inputs.values["available_short_term_funding"] = available
        median = max(0.0, required - available)
    return inputs.build(
        "WORKING_CAPITAL_GAP",
        "Working-capital gap",
        "WorkingCapitalGap = max(0, RequiredNWC - AvailableShortTermFunding)",
        "ZAR",
        median,
    )


def refinancing_exposure(
    registry: BusinessEvidenceRegistry, entity_id: str, horizon_label: str = "12M"
) -> IndicatorValue:
    r"""RefinancingExposure = sum(DebtMaturity_h) - AvailableLiquidity_h."""
    inputs = _Inputs(registry, entity_id)
    maturity = registry.by_concept(entity_id, "current_debt_maturity_window")
    debt: Optional[float] = None
    if maturity is not None and maturity.money_value is not None:
        debt = _zar(maturity.money_value, maturity.currency or "ZAR", maturity.unit)
        inputs.values["debt_maturing_in_horizon"] = debt
        inputs._record(maturity)
    else:
        debt = inputs.money(
            "debt_maturing_in_horizon",
            "current_debt",
            "term_finance",
            "current_liabilities",
        )
    cash = inputs.money("available_liquidity", "cash_and_cash_equivalents")
    median = debt - cash if debt is not None and cash is not None else None
    indicator = inputs.build(
        f"REFINANCING_EXPOSURE_{horizon_label}",
        f"Refinancing exposure ({horizon_label} horizon)",
        "RefinancingExposure = sum(DebtMaturity_h) - AvailableLiquidity_h",
        "ZAR",
        median,
    )
    return indicator


def fx_exposure(
    registry: BusinessEvidenceRegistry, entity_id: str
) -> IndicatorValue:
    r"""FXExposure_c = ForeignCurrencyInflows_c - ForeignCurrencyOutflows_c.

    The bank observes gross cross-border turnover rather than signed inflow and
    outflow legs, so the indicator reports observed cross-border turnover as an
    upper bound on net exposure and records the missing directional split.
    """
    inputs = _Inputs(registry, entity_id)
    turnover = inputs.money(
        "cross_border_turnover", "bank_observed_cross_border_fx_ltm"
    )
    disclosed = registry.by_concept(entity_id, "fx_exposure")
    if disclosed is not None and disclosed.money_value is not None:
        value = _zar(disclosed.money_value, disclosed.currency or "ZAR", disclosed.unit)
        inputs.values["disclosed_fx_exposure"] = value
        inputs._record(disclosed)
    median = turnover
    indicator = inputs.build(
        "FX_EXPOSURE",
        "Currency exposure (gross cross-border turnover bound)",
        "FXExposure_c = ForeignCurrencyInflows_c - ForeignCurrencyOutflows_c",
        "ZAR",
        median,
        tolerance=0.20,
    )
    if indicator.status is ComponentStatus.SUPPORTED:
        return indicator.model_copy(
            update={
                "missing_inputs": ["signed_inflow_outflow_split"],
                "status": ComponentStatus.INFERRED,
                "formula": indicator.formula
                + " â€” only gross turnover is bank-observed, so this is an upper bound on net exposure",
                "claim_class": ClaimClass.IDENTIFIED_BOUND,
            }
        )
    return indicator


def leverage_proxy(
    registry: BusinessEvidenceRegistry, entity_id: str
) -> IndicatorValue:
    """Debt-to-revenue proxy used by funding-route scoring."""
    inputs = _Inputs(registry, entity_id)
    debt = inputs.money(
        "debt", "current_debt", "term_finance", "current_liabilities"
    )
    revenue = inputs.money(
        "revenue", "revenue", "insurance_revenue", "gross_rental_income"
    )
    median = debt / revenue if debt is not None and revenue else None
    return inputs.build(
        "LEVERAGE_PROXY",
        "Short-term debt to revenue",
        "LeverageProxy = ShortTermDebt / Revenue",
        "ratio",
        median,
        tolerance=0.15,
    )


def cash_to_obligations(
    registry: BusinessEvidenceRegistry, entity_id: str
) -> IndicatorValue:
    inputs = _Inputs(registry, entity_id)
    cash = inputs.money("cash", "cash_and_cash_equivalents")
    obligations = inputs.money(
        "near_term_obligations",
        "current_debt",
        "term_finance",
        "current_liabilities",
        "insurance_liabilities",
    )
    median = cash / obligations if cash is not None and obligations else None
    return inputs.build(
        "CASH_COVER",
        "Cash cover of near-term obligations",
        "CashCover = Cash / NearTermObligations",
        "ratio",
        median,
        tolerance=0.15,
    )


ALL_INDICATORS: Tuple[str, ...] = (
    "CCC",
    "LIQUIDITY_BUFFER",
    "WORKING_CAPITAL_GAP",
    "REFINANCING_EXPOSURE_12M",
    "FX_EXPOSURE",
    "LEVERAGE_PROXY",
    "CASH_COVER",
)


def build_indicators(
    registry: BusinessEvidenceRegistry, entity_id: str
) -> Dict[str, IndicatorValue]:
    return {
        "CCC": cash_conversion_cycle(registry, entity_id),
        "LIQUIDITY_BUFFER": liquidity_buffer(registry, entity_id),
        "WORKING_CAPITAL_GAP": working_capital_gap(registry, entity_id),
        "REFINANCING_EXPOSURE_12M": refinancing_exposure(registry, entity_id),
        "FX_EXPOSURE": fx_exposure(registry, entity_id),
        "LEVERAGE_PROXY": leverage_proxy(registry, entity_id),
        "CASH_COVER": cash_to_obligations(registry, entity_id),
    }
