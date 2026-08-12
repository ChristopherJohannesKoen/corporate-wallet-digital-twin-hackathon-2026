"""Interpretable business-problem detectors.

One detector per problem type.  Each detector:

* applies deterministic evidence rules that set identification status and
  reason codes;
* combines public facts, bank-observed activity, V3 PU estimates, change points
  and governed priors into a *scenario weight*, not a calibrated posterior;
* stores supporting and disconfirming evidence separately, so a banker can see
  what argues against the hypothesis;
* returns intensity as an interval, never a bare score;
* marks the hypothesis commercially eligible only when at least one critical
  signal is bank-observed, approved E1 or approved E2.

Without adjudicated labels there is no calibration set, so probabilities are
labelled ``SCENARIO`` and ``calibration_status`` says so.  The only exception
is the wallet-leakage detector, which inherits the V3 change-point posterior
and is labelled ``POSTERIOR`` with the V3 calibration caveat carried through.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from wallet_twin_v2.contracts import ApprovalStatus, ClaimClass, EvidenceTier

from .business_evidence import BusinessEvidenceRegistry
from .contracts import (
    BusinessEvent,
    BusinessTwinSnapshot,
    IndicatorValue,
    ProblemEvidenceItem,
    ProblemHypothesis,
    SignedInterval,
)
from .taxonomy import (
    BusinessProblem as P,
    BusinessTwinDomain as D,
    ComponentStatus,
    PROBLEM_LABELS,
)

DETECTOR_VERSION = "v31-problem-detectors-3.1.1"

SCENARIO_CALIBRATION = (
    "GOVERNED_SCENARIO_NOT_EMPIRICALLY_CALIBRATED â€” no adjudicated problem labels exist, "
    "so this weight is a governed scenario and not a validated probability"
)
POSTERIOR_CALIBRATION = (
    "REPRESENTATIVE_TEMPORAL_REPLAY_NOT_RM_OUTCOME_CALIBRATED â€” inherited from the V3 "
    "change-point posterior"
)

#: Governed prior weight per problem, before evidence.  These express how often
#: a corporate of this kind plausibly has the problem at all; they are policy,
#: and they are shown to the reviewer.
BASE_PRIORS: Mapping[P, float] = {
    P.WORKING_CAPITAL_PRESSURE: 0.30,
    P.FX_EXPOSURE: 0.35,
    P.INTEREST_RATE_EXPOSURE: 0.30,
    P.COMMODITY_EXPOSURE: 0.15,
    P.LIQUIDITY_FRAGMENTATION: 0.25,
    P.REFINANCING_CLIFF: 0.20,
    P.NEW_FUNDING_REQUIREMENT: 0.20,
    P.PAYMENTS_INEFFICIENCY: 0.25,
    P.COLLECTIONS_INEFFICIENCY: 0.25,
    P.SUPPLY_CHAIN_RISK: 0.20,
    P.PROJECT_MOBILISATION: 0.12,
    P.GUARANTEE_OR_COLLATERAL_REQUIREMENT: 0.18,
    P.TREASURY_CENTRALISATION: 0.22,
    P.CAPITAL_STRUCTURE_EVENT: 0.12,
    P.MA_OR_STRATEGIC_EVENT: 0.10,
    P.ESG_TRANSITION_FUNDING: 0.12,
    P.WALLET_LEAKAGE: 0.20,
    P.OPERATIONAL_RESILIENCE: 0.18,
}

SECTOR_COMMODITY_LINKED = frozenset({"mining"})
SECTOR_PROJECT_LINKED = frozenset({"mining", "telecoms", "real_estate"})
SECTOR_INVENTORY_LINKED = frozenset({"consumer", "industrials_pharma", "mining"})


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class _Builder:
    """Accumulates evidence for one problem hypothesis."""

    def __init__(
        self,
        entity_id: str,
        problem: P,
        as_of: date,
        registry: BusinessEvidenceRegistry,
    ) -> None:
        self.entity_id = entity_id
        self.problem = problem
        self.as_of = as_of
        self.registry = registry
        self.support: List[ProblemEvidenceItem] = []
        self.against: List[ProblemEvidenceItem] = []
        self.reason_codes: List[str] = []
        self.domains: List[D] = []

    def add(
        self,
        reason_code: str,
        statement: str,
        weight: float,
        *,
        claim_ids: Sequence[str] = (),
        bank_observed: bool = False,
        claim_class: ClaimClass = ClaimClass.IDENTIFIED_BOUND,
        disconfirming: bool = False,
    ) -> None:
        item = ProblemEvidenceItem(
            reason_code=reason_code,
            statement=statement,
            claim_class=claim_class,
            evidence_claim_ids=list(claim_ids),
            bank_observed=bank_observed,
            weight=_clamp(weight),
        )
        (self.against if disconfirming else self.support).append(item)
        self.reason_codes.append(reason_code)

    def critical_signal_is_governed(self) -> bool:
        """True when a supporting signal is bank-observed or approved E1/E2."""
        for item in self.support:
            if item.bank_observed:
                return True
            for claim_id in item.evidence_claim_ids:
                claim = self.registry.get(claim_id)
                if claim is None:
                    continue
                if claim.approval_status is not ApprovalStatus.APPROVED:
                    continue
                if claim.tier in (EvidenceTier.E1, EvidenceTier.E2):
                    return True
        return False

    def weight(self) -> float:
        prior = BASE_PRIORS[self.problem]
        positive = sum(item.weight for item in self.support)
        negative = sum(item.weight for item in self.against)
        # Additive evidence on a bounded scale, deliberately transparent: a
        # logistic combination would hide how much each signal contributed.
        return _clamp(prior + 0.55 * positive - 0.45 * negative)

    def build(
        self,
        *,
        identified: bool,
        intensity: Optional[SignedInterval],
        intensity_unit: str,
        claim_class: ClaimClass = ClaimClass.SCENARIO,
        calibration_status: str = SCENARIO_CALIBRATION,
        domains: Sequence[D] = (),
    ) -> ProblemHypothesis:
        governed = self.critical_signal_is_governed()
        if intensity is None:
            intensity = SignedInterval(lower=0.0, median=0.0, upper=0.0, unit="none")
            intensity_unit = "UNQUANTIFIED"
        probability = self.weight()
        eligible = bool(identified and governed and self.support)
        if not identified:
            self.reason_codes.append("NOT_IDENTIFIED_INSUFFICIENT_EVIDENCE")
        if identified and not governed:
            self.reason_codes.append("NO_GOVERNED_CRITICAL_SIGNAL_DISCOVERY_ONLY")
        return ProblemHypothesis(
            problem_id=f"problem:{self.entity_id}:{self.problem.value.lower()}",
            entity_id=self.entity_id,
            problem=self.problem,
            label=PROBLEM_LABELS[self.problem],
            as_of=self.as_of,
            identified=identified,
            intensity=intensity,
            intensity_unit=intensity_unit,
            supporting_evidence=self.support,
            disconfirming_evidence=self.against,
            reason_codes=sorted(set(self.reason_codes)),
            probability=probability,
            claim_class=claim_class,
            calibration_status=calibration_status,
            critical_signal_is_governed=governed,
            commercially_eligible=eligible,
            detector_version=DETECTOR_VERSION,
            affected_domains=list(domains),
        )


class ProblemDetectorSuite:
    """Runs all eighteen detectors for one client."""

    version = DETECTOR_VERSION

    def __init__(
        self,
        registry: BusinessEvidenceRegistry,
        as_of: date,
    ) -> None:
        self.registry = registry
        self.as_of = as_of

    # -- shared context ----------------------------------------------------
    def _context(
        self,
        entity_id: str,
        twin: BusinessTwinSnapshot,
        events: Sequence[BusinessEvent],
        v3_signals: Mapping[str, Any],
    ) -> Dict[str, Any]:
        indicators: Dict[str, IndicatorValue] = {}
        for component in twin.components:
            for indicator in component.indicators:
                indicators[indicator.indicator_id] = indicator
        claims = {claim.concept: claim for claim in self.registry.claims_for(entity_id)}
        return {
            "twin": twin,
            "sector": twin.sector,
            "indicators": indicators,
            "claims": claims,
            "events": {event.event_type: event for event in events},
            "event_list": list(events),
            "needs": v3_signals.get("needs", {}),
            "changes": v3_signals.get("changes", {}),
            "leakages": v3_signals.get("leakages", {}),
            "shadows": v3_signals.get("shadows", {}),
        }

    @staticmethod
    def _money(claims: Mapping[str, Any], concept: str) -> Optional[float]:
        claim = claims.get(concept)
        return float(claim.money_value) if claim is not None and claim.money_value else None

    @staticmethod
    def _ratio(claims: Mapping[str, Any], concept: str) -> Optional[float]:
        claim = claims.get(concept)
        return (
            float(claim.ratio_value)
            if claim is not None and claim.ratio_value is not None
            else None
        )

    @staticmethod
    def _count(claims: Mapping[str, Any], concept: str) -> Optional[int]:
        claim = claims.get(concept)
        return claim.count_value if claim is not None else None

    @staticmethod
    def _interval_from(
        value: float, spread: float = 0.25, unit: str = "ZAR"
    ) -> SignedInterval:
        return SignedInterval(
            lower=min(value * (1 - spread), value * (1 + spread)),
            median=value,
            upper=max(value * (1 - spread), value * (1 + spread)),
            unit=unit,
        )

    def _client_leakage(self, entity_id: str, context: Dict[str, Any]) -> Tuple[float, float, List[str]]:
        alarms = [
            alarm
            for alarm in context["leakages"].values()
            if alarm.entity_id == entity_id
        ]
        if not alarms:
            return 0.0, 0.0, []
        worst = max(alarms, key=lambda item: item.alarm_probability)
        at_risk = sum(item.expected_external_flow_at_risk_zar for item in alarms)
        return worst.alarm_probability, at_risk, list(worst.reason_codes)

    def _client_need(self, entity_id: str, product: str, context: Dict[str, Any]) -> Optional[float]:
        for need in context["needs"].values():
            if need.entity_id == entity_id and need.product == product:
                return need.product_need_probability
        return None

    # -- detectors ---------------------------------------------------------
    def detect_all(
        self,
        entity_id: str,
        twin: BusinessTwinSnapshot,
        events: Sequence[BusinessEvent],
        v3_signals: Mapping[str, Any],
    ) -> Dict[P, ProblemHypothesis]:
        context = self._context(entity_id, twin, events, v3_signals)
        detectors = (
            self._working_capital_pressure,
            self._fx_exposure,
            self._interest_rate_exposure,
            self._commodity_exposure,
            self._liquidity_fragmentation,
            self._refinancing_cliff,
            self._new_funding_requirement,
            self._payments_inefficiency,
            self._collections_inefficiency,
            self._supply_chain_risk,
            self._project_mobilisation,
            self._guarantee_requirement,
            self._treasury_centralisation,
            self._capital_structure_event,
            self._ma_strategic_event,
            self._esg_transition_funding,
            self._wallet_leakage,
            self._operational_resilience,
        )
        results: Dict[P, ProblemHypothesis] = {}
        for detector in detectors:
            hypothesis = detector(entity_id, context)
            results[hypothesis.problem] = hypothesis
        if len(results) != 18:
            raise RuntimeError("every problem type must produce a hypothesis")
        return results

    # 1 ------------------------------------------------------------------
    def _working_capital_pressure(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.WORKING_CAPITAL_PRESSURE, self.as_of, self.registry)
        claims, indicators = context["claims"], context["indicators"]
        ccc = indicators.get("CCC")
        gap = indicators.get("WORKING_CAPITAL_GAP")
        intensity: Optional[SignedInterval] = None
        unit = "ZAR"
        identified = False

        if ccc is not None and ccc.available and ccc.interval.median > 30:
            identified = True
            builder.add(
                "LONG_CASH_CONVERSION_CYCLE",
                f"Cash conversion cycle of {ccc.interval.median:.0f} days ties up working capital.",
                min(0.6, ccc.interval.median / 120.0),
                claim_ids=ccc.evidence_claim_ids,
            )
        elif ccc is not None and ccc.available:
            builder.add(
                "SHORT_CASH_CONVERSION_CYCLE",
                f"Cash conversion cycle is only {ccc.interval.median:.0f} days.",
                0.35,
                claim_ids=ccc.evidence_claim_ids,
                disconfirming=True,
            )

        if gap is not None and gap.available and gap.interval.median > 0:
            identified = True
            intensity = gap.interval
            builder.add(
                "POSITIVE_WORKING_CAPITAL_GAP",
                f"Required net working capital exceeds disclosed short-term funding by "
                f"ZAR {gap.interval.median:,.0f}.",
                0.55,
                claim_ids=gap.evidence_claim_ids,
            )

        intensity_index = self._ratio(claims, "bank_observed_working_capital_intensity_index")
        if intensity_index is not None and intensity_index > 0.6:
            identified = True
            builder.add(
                "HIGH_WORKING_CAPITAL_INTENSITY",
                f"Bank-observed working-capital intensity index is {intensity_index:.2f}.",
                0.35,
                claim_ids=[claims["bank_observed_working_capital_intensity_index"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )

        trade_flow = self._money(claims, "bank_observed_trade_finance_ltm")
        if trade_flow and intensity is None:
            intensity = self._interval_from(trade_flow, 0.35)
            unit = "ZAR (bank-observed trade flow proxy)"
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit=unit,
            domains=[D.WORKING_CAPITAL_CYCLE, D.COST_ENGINE, D.REVENUE_ENGINE],
        )

    # 2 ------------------------------------------------------------------
    def _fx_exposure(self, entity_id: str, context: Dict[str, Any]) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.FX_EXPOSURE, self.as_of, self.registry)
        claims, indicators = context["claims"], context["indicators"]
        fx = indicators.get("FX_EXPOSURE")
        countries = self._count(claims, "bank_observed_active_country_count") or 0
        turnover = self._money(claims, "bank_observed_cross_border_fx_ltm")
        identified = False
        intensity: Optional[SignedInterval] = None

        if turnover and turnover > 0:
            identified = True
            intensity = self._interval_from(turnover, 0.30)
            builder.add(
                "OBSERVED_CROSS_BORDER_TURNOVER",
                f"Bank-observed cross-border turnover of ZAR {turnover:,.0f} over the last twelve months.",
                0.55,
                claim_ids=[claims["bank_observed_cross_border_fx_ltm"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if countries >= 10:
            builder.add(
                "MULTI_COUNTRY_FOOTPRINT",
                f"Activity is observed across {countries} countries.",
                0.30,
                claim_ids=[claims["bank_observed_active_country_count"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        disclosed = claims.get("fx_exposure")
        if disclosed is not None:
            builder.add(
                "AUDITED_FX_EXPOSURE_DISCLOSED",
                "The client discloses a currency exposure in its audited accounts.",
                0.40,
                claim_ids=[disclosed.claim_id],
            )
        if fx is not None and fx.missing_inputs:
            builder.add(
                "HEDGE_RATIO_UNKNOWN",
                "The hedge ratio is not observable, so residual exposure may already be covered.",
                0.30,
                disconfirming=True,
                claim_class=ClaimClass.SCENARIO,
            )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR gross cross-border turnover (upper bound on net exposure)",
            domains=[D.CURRENCY_AND_COMMODITY_EXPOSURE, D.GEOGRAPHIC_EXPOSURE],
        )

    # 3 ------------------------------------------------------------------
    def _interest_rate_exposure(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.INTEREST_RATE_EXPOSURE, self.as_of, self.registry)
        claims, indicators = context["claims"], context["indicators"]
        leverage = indicators.get("LEVERAGE_PROXY")
        debt_claim = (
            claims.get("current_debt")
            or claims.get("term_finance")
            or claims.get("current_liabilities")
        )
        identified = False
        intensity: Optional[SignedInterval] = None
        if debt_claim is not None and debt_claim.money_value:
            identified = True
            builder.add(
                "FLOATING_RATE_DEBT_DISCLOSED",
                "Short-term borrowings are disclosed and are typically floating-rate.",
                0.45,
                claim_ids=[debt_claim.claim_id],
            )
        if leverage is not None and leverage.available:
            intensity = leverage.interval
            if leverage.interval.median > 0.15:
                builder.add(
                    "MATERIAL_LEVERAGE",
                    f"Short-term debt is {leverage.interval.median:.0%} of revenue.",
                    0.35,
                    claim_ids=leverage.evidence_claim_ids,
                )
            else:
                builder.add(
                    "LOW_LEVERAGE",
                    f"Short-term debt is only {leverage.interval.median:.0%} of revenue.",
                    0.30,
                    claim_ids=leverage.evidence_claim_ids,
                    disconfirming=True,
                )
        builder.add(
            "FIXED_FLOATING_SPLIT_UNKNOWN",
            "The fixed/floating split and existing swap book are not disclosed.",
            0.25,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="short-term debt / revenue",
            domains=[D.FUNDING_STRUCTURE],
        )

    # 4 ------------------------------------------------------------------
    def _commodity_exposure(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.COMMODITY_EXPOSURE, self.as_of, self.registry)
        sector = context["sector"]
        claims = context["claims"]
        identified = sector in SECTOR_COMMODITY_LINKED
        intensity: Optional[SignedInterval] = None
        if identified:
            revenue_proxy = self._money(claims, "bank_observed_collections_ltm")
            if revenue_proxy:
                intensity = self._interval_from(revenue_proxy, 0.40)
            builder.add(
                "COMMODITY_LINKED_SECTOR",
                "Revenue is commodity-price linked for an extractive operator.",
                0.45,
                claim_ids=[claims["sector_operating_model"].claim_id]
                if "sector_operating_model" in claims
                else [],
                claim_class=ClaimClass.SCENARIO,
            )
            if revenue_proxy:
                builder.add(
                    "OBSERVED_COMMODITY_LINKED_INFLOWS",
                    f"Bank-observed inflows of ZAR {revenue_proxy:,.0f} are commodity-price sensitive.",
                    0.35,
                    claim_ids=[claims["bank_observed_collections_ltm"].claim_id],
                    bank_observed=True,
                    claim_class=ClaimClass.OBSERVED,
                )
        else:
            builder.add(
                "NON_COMMODITY_SECTOR",
                f"The {sector} sector has no direct commodity price linkage in the governed taxonomy.",
                0.50,
                disconfirming=True,
                claim_class=ClaimClass.SCENARIO,
            )
        builder.add(
            "EXISTING_HEDGE_PROGRAMME_UNKNOWN",
            "Any existing commodity hedge programme is not disclosed.",
            0.25,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR commodity-linked inflow proxy",
            domains=[D.CURRENCY_AND_COMMODITY_EXPOSURE, D.REVENUE_ENGINE],
        )

    # 5 ------------------------------------------------------------------
    def _liquidity_fragmentation(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.LIQUIDITY_FRAGMENTATION, self.as_of, self.registry)
        claims = context["claims"]
        countries = self._count(claims, "bank_observed_active_country_count") or 0
        volatility = self._ratio(claims, "bank_observed_liquidity_volatility_index")
        liquidity = self._money(claims, "bank_observed_liquidity_ltm")
        identified = countries >= 10
        intensity: Optional[SignedInterval] = None
        if identified:
            builder.add(
                "MULTI_JURISDICTION_CASH_FOOTPRINT",
                f"Cash is held across {countries} observed jurisdictions.",
                0.45,
                claim_ids=[claims["bank_observed_active_country_count"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if liquidity:
            intensity = self._interval_from(liquidity, 0.30)
            builder.add(
                "OBSERVED_LIQUIDITY_BALANCES",
                f"Bank-observed liquidity flow of ZAR {liquidity:,.0f} over twelve months.",
                0.30,
                claim_ids=[claims["bank_observed_liquidity_ltm"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if volatility is not None and volatility > 0.15:
            builder.add(
                "VOLATILE_BALANCES",
                f"Observed liquidity volatility index is {volatility:.2f}.",
                0.25,
                claim_ids=[claims["bank_observed_liquidity_volatility_index"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        builder.add(
            "EXISTING_POOLING_STRUCTURE_UNKNOWN",
            "Any existing cash-pooling or in-house-bank structure is not visible to this bank.",
            0.30,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR observed liquidity flow",
            domains=[D.LIQUIDITY_AND_BUFFER, D.GEOGRAPHIC_EXPOSURE],
        )

    # 6 ------------------------------------------------------------------
    def _refinancing_cliff(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.REFINANCING_CLIFF, self.as_of, self.registry)
        indicators, events = context["indicators"], context["events"]
        exposure = indicators.get("REFINANCING_EXPOSURE_12M")
        buffer_indicator = indicators.get("LIQUIDITY_BUFFER")
        identified = False
        intensity: Optional[SignedInterval] = None

        maturity_event = events.get("DEBT_MATURITY_WINDOW") or events.get(
            "DEBT_MATURITY_WINDOW_ELAPSED"
        )
        if maturity_event is not None:
            identified = True
            builder.add(
                "DATED_DEBT_MATURITY",
                maturity_event.label,
                0.50,
                claim_ids=maturity_event.evidence_claim_ids,
                claim_class=ClaimClass.IDENTIFIED_BOUND,
            )
        if exposure is not None and exposure.available:
            intensity = exposure.interval
            if exposure.interval.median > 0:
                builder.add(
                    "MATURITIES_EXCEED_LIQUIDITY",
                    f"Debt maturing inside the horizon exceeds disclosed liquidity by "
                    f"ZAR {exposure.interval.median:,.0f}.",
                    0.55,
                    claim_ids=exposure.evidence_claim_ids,
                )
            else:
                builder.add(
                    "LIQUIDITY_COVERS_MATURITIES",
                    f"Disclosed liquidity exceeds maturing debt by ZAR {abs(exposure.interval.median):,.0f}.",
                    0.45,
                    claim_ids=exposure.evidence_claim_ids,
                    disconfirming=True,
                )
        if buffer_indicator is not None and buffer_indicator.available:
            if buffer_indicator.interval.median < 0:
                builder.add(
                    "NEGATIVE_LIQUIDITY_BUFFER",
                    "Disclosed cash and facilities do not cover near-term obligations.",
                    0.40,
                    claim_ids=buffer_indicator.evidence_claim_ids,
                )
        builder.add(
            "UNDRAWN_FACILITY_HEADROOM_UNKNOWN",
            "Undrawn committed facility headroom is not disclosed and may already cover the maturity.",
            0.30,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR maturing debt net of disclosed liquidity",
            domains=[D.FUNDING_STRUCTURE, D.LIQUIDITY_AND_BUFFER],
        )

    # 7 ------------------------------------------------------------------
    def _new_funding_requirement(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.NEW_FUNDING_REQUIREMENT, self.as_of, self.registry)
        claims, indicators = context["claims"], context["indicators"]
        financing_need = self._ratio(claims, "bank_observed_financing_need_index")
        gap = indicators.get("WORKING_CAPITAL_GAP")
        exposure = indicators.get("REFINANCING_EXPOSURE_12M")
        identified = False
        intensity: Optional[SignedInterval] = None
        if financing_need is not None and financing_need > 0.4:
            identified = True
            builder.add(
                "ELEVATED_FINANCING_NEED_INDEX",
                f"Modelled financing-need index is {financing_need:.2f}.",
                0.40,
                claim_ids=[claims["bank_observed_financing_need_index"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        for indicator in (exposure, gap):
            if indicator is not None and indicator.available and indicator.interval.median > 0:
                identified = True
                intensity = indicator.interval if intensity is None else intensity
                builder.add(
                    f"QUANTIFIED_{indicator.indicator_id}",
                    f"{indicator.label} of ZAR {indicator.interval.median:,.0f} is unfunded.",
                    0.45,
                    claim_ids=indicator.evidence_claim_ids,
                )
        builder.add(
            "INTERNAL_CASH_GENERATION_UNKNOWN",
            "Free cash-flow generation may fund the requirement without new external debt.",
            0.30,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR unfunded requirement",
            domains=[D.FUNDING_STRUCTURE, D.WORKING_CAPITAL_CYCLE],
        )

    # 8 ------------------------------------------------------------------
    def _payments_inefficiency(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.PAYMENTS_INEFFICIENCY, self.as_of, self.registry)
        claims = context["claims"]
        payments = self._money(claims, "bank_observed_payments_ltm")
        countries = self._count(claims, "bank_observed_active_country_count") or 0
        need = self._client_need(entity_id, "Payments", context)
        identified = bool(payments)
        intensity = self._interval_from(payments, 0.25) if payments else None
        if payments:
            builder.add(
                "OBSERVED_PAYMENT_VOLUME",
                f"Bank-observed supplier payments of ZAR {payments:,.0f} over twelve months.",
                0.45,
                claim_ids=[claims["bank_observed_payments_ltm"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if countries >= 12:
            builder.add(
                "FRAGMENTED_PAYMENT_FOOTPRINT",
                f"Payments span {countries} countries, which typically implies multiple channels and formats.",
                0.30,
                claim_ids=[claims["bank_observed_active_country_count"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if need is not None and need > 0.6:
            builder.add(
                "PU_NEED_SIGNAL",
                f"V3 positive-unlabelled need estimate for Payments is {need:.0%} under the SCAR assumption.",
                0.25,
                claim_class=ClaimClass.POSTERIOR,
            )
        builder.add(
            "EXISTING_ERP_INTEGRATION_UNKNOWN",
            "The client may already run host-to-host or ERP-integrated payments elsewhere.",
            0.35,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR observed payment volume",
            domains=[D.COST_ENGINE, D.OPERATING_MODEL],
        )

    # 9 ------------------------------------------------------------------
    def _collections_inefficiency(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.COLLECTIONS_INEFFICIENCY, self.as_of, self.registry)
        claims, indicators = context["claims"], context["indicators"]
        collections = self._money(claims, "bank_observed_collections_ltm")
        ccc = indicators.get("CCC")
        identified = bool(collections)
        intensity = self._interval_from(collections, 0.25) if collections else None
        if collections:
            builder.add(
                "OBSERVED_COLLECTION_VOLUME",
                f"Bank-observed collections of ZAR {collections:,.0f} over twelve months.",
                0.45,
                claim_ids=[claims["bank_observed_collections_ltm"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if ccc is not None and ccc.available and ccc.inputs.get("DSO", 0) > 30:
            builder.add(
                "ELEVATED_DSO",
                f"Days sales outstanding is {ccc.inputs['DSO']:.0f} days.",
                0.40,
                claim_ids=ccc.evidence_claim_ids,
            )
        elif ccc is not None and ccc.available:
            builder.add(
                "LOW_DSO",
                f"Days sales outstanding is only {ccc.inputs.get('DSO', 0):.0f} days.",
                0.35,
                claim_ids=ccc.evidence_claim_ids,
                disconfirming=True,
            )
        builder.add(
            "RECONCILIATION_PROCESS_UNKNOWN",
            "Existing reconciliation automation and virtual-account usage are not visible.",
            0.30,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR observed collection volume",
            domains=[D.REVENUE_ENGINE, D.WORKING_CAPITAL_CYCLE],
        )

    # 10 -----------------------------------------------------------------
    def _supply_chain_risk(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.SUPPLY_CHAIN_RISK, self.as_of, self.registry)
        claims, events = context["claims"], context["events"]
        sector = context["sector"]
        trade_pipeline = events.get("TRADE_EVENT_PIPELINE")
        payments_growth = self._ratio(claims, "bank_observed_payments_yoy_change")
        identified = False
        intensity: Optional[SignedInterval] = None
        if trade_pipeline is not None:
            identified = True
            if trade_pipeline.magnitude is not None:
                intensity = trade_pipeline.magnitude
            builder.add(
                "DATED_TRADE_PIPELINE",
                trade_pipeline.label,
                0.45,
                claim_ids=trade_pipeline.evidence_claim_ids,
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if payments_growth is not None and payments_growth > 0.15:
            identified = True
            builder.add(
                "RISING_SUPPLIER_OUTFLOWS",
                f"Supplier payments are up {payments_growth:.0%} year on year.",
                0.35,
                claim_ids=[claims["bank_observed_payments_yoy_change"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if sector in SECTOR_INVENTORY_LINKED:
            builder.add(
                "INVENTORY_INTENSIVE_SECTOR",
                f"The {sector} sector carries inventory and supplier-concentration risk.",
                0.25,
                claim_class=ClaimClass.SCENARIO,
            )
        builder.add(
            "SUPPLIER_CONCENTRATION_UNKNOWN",
            "Supplier concentration and contractual terms are not disclosed.",
            0.35,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR dated trade-event value",
            domains=[D.COST_ENGINE, D.WORKING_CAPITAL_CYCLE, D.OPERATING_MODEL],
        )

    # 11 -----------------------------------------------------------------
    def _project_mobilisation(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.PROJECT_MOBILISATION, self.as_of, self.registry)
        twin: BusinessTwinSnapshot = context["twin"]
        projects = twin.component(D.PROJECTS_SUBSIDIARIES_SPVS)
        sector = context["sector"]
        builder.add(
            "NO_REVIEWED_PROJECT_OR_SPV_EVIDENCE",
            "No reviewed subsidiary, SPV or project disclosure exists, so no project can be "
            "asserted. Ownership is never inferred from name similarity.",
            0.55,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        if sector in SECTOR_PROJECT_LINKED:
            builder.add(
                "PROJECT_INTENSIVE_SECTOR",
                f"The {sector} sector typically runs long-cycle capital projects.",
                0.25,
                claim_class=ClaimClass.SCENARIO,
            )
        assert projects.status is ComponentStatus.UNKNOWN
        return builder.build(
            identified=False,
            intensity=None,
            intensity_unit="UNQUANTIFIED",
            domains=[D.PROJECTS_SUBSIDIARIES_SPVS],
        )

    # 12 -----------------------------------------------------------------
    def _guarantee_requirement(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.GUARANTEE_OR_COLLATERAL_REQUIREMENT, self.as_of, self.registry)
        pipeline = context["events"].get("TRADE_EVENT_PIPELINE")
        identified = False
        intensity: Optional[SignedInterval] = None
        if pipeline is not None and pipeline.magnitude is not None:
            identified = True
            # A guarantee typically covers a fraction of the underlying contract
            # value; the governed range is 10%-30%, shown explicitly.
            median = pipeline.magnitude.median * 0.20
            intensity = SignedInterval(
                lower=pipeline.magnitude.median * 0.10,
                median=median,
                upper=pipeline.magnitude.median * 0.30,
                unit="ZAR",
            )
            builder.add(
                "DATED_CONTRACT_PIPELINE",
                pipeline.label
                + " Contract performance typically requires guarantees at 10-30% of value.",
                0.40,
                claim_ids=pipeline.evidence_claim_ids,
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        builder.add(
            "EXISTING_CONTINGENT_LINES_UNKNOWN",
            "Existing guarantee and LC lines with other banks are not visible.",
            0.35,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR indicative contingent exposure",
            domains=[D.WORKING_CAPITAL_CYCLE, D.BUSINESS_AND_FINANCIAL_RISKS],
        )

    # 13 -----------------------------------------------------------------
    def _treasury_centralisation(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.TREASURY_CENTRALISATION, self.as_of, self.registry)
        claims = context["claims"]
        countries = self._count(claims, "bank_observed_active_country_count") or 0
        complexity = self._ratio(claims, "bank_observed_relationship_complexity_index")
        breadth = self._count(claims, "bank_observed_product_relationship_breadth") or 0
        identified = countries >= 12 or (complexity or 0) > 0.7
        intensity: Optional[SignedInterval] = None
        if complexity is not None:
            intensity = SignedInterval(
                lower=max(0.0, complexity - 0.1),
                median=complexity,
                upper=min(1.0, complexity + 0.1),
                unit="index_0_1",
            )
            builder.add(
                "HIGH_RELATIONSHIP_COMPLEXITY",
                f"Banking-relationship complexity index is {complexity:.2f}.",
                0.35 if complexity > 0.7 else 0.15,
                claim_ids=[claims["bank_observed_relationship_complexity_index"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if countries >= 12:
            builder.add(
                "WIDE_COUNTRY_FOOTPRINT",
                f"Treasury operations span {countries} countries.",
                0.35,
                claim_ids=[claims["bank_observed_active_country_count"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if breadth >= 5:
            builder.add(
                "BROAD_EXISTING_MANDATE",
                f"The bank already holds {breadth} of five product relationships, so the "
                "centralisation gap may be smaller than the footprint implies.",
                0.25,
                claim_ids=[claims["bank_observed_product_relationship_breadth"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
                disconfirming=True,
            )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="relationship complexity index",
            domains=[D.OPERATING_MODEL, D.LIQUIDITY_AND_BUFFER],
        )

    # 14 -----------------------------------------------------------------
    def _capital_structure_event(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.CAPITAL_STRUCTURE_EVENT, self.as_of, self.registry)
        claims = context["claims"]
        event_intensity = self._ratio(claims, "bank_observed_event_intensity_index")
        builder.add(
            "NO_ANNOUNCED_CORPORATE_ACTION",
            "No announced corporate action has been extracted from a reviewed source.",
            0.50,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        if event_intensity is not None and event_intensity > 0.8:
            builder.add(
                "ELEVATED_EVENT_INTENSITY",
                f"Bank-observed corporate-event intensity index is {event_intensity:.2f}.",
                0.30,
                claim_ids=[claims["bank_observed_event_intensity_index"].claim_id],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        return builder.build(
            identified=False,
            intensity=None,
            intensity_unit="UNQUANTIFIED",
            domains=[D.STRATEGY_ACTIONS_AND_ESG, D.FUNDING_STRUCTURE],
        )

    # 15 -----------------------------------------------------------------
    def _ma_strategic_event(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.MA_OR_STRATEGIC_EVENT, self.as_of, self.registry)
        builder.add(
            "NO_REVIEWED_TRANSACTION_EVIDENCE",
            "No announced or reviewed transaction evidence exists for this client.",
            0.55,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=False,
            intensity=None,
            intensity_unit="UNQUANTIFIED",
            domains=[D.STRATEGY_ACTIONS_AND_ESG],
        )

    # 16 -----------------------------------------------------------------
    def _esg_transition_funding(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.ESG_TRANSITION_FUNDING, self.as_of, self.registry)
        builder.add(
            "NO_EVIDENCE_BASED_ESG_ACTIVITY_EXTRACTED",
            "No reviewed transition target, eligible capex programme or use-of-proceeds "
            "framework has been extracted. Sustainable finance cannot be proposed on a "
            "sector assumption alone.",
            0.60,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=False,
            intensity=None,
            intensity_unit="UNQUANTIFIED",
            domains=[D.STRATEGY_ACTIONS_AND_ESG],
        )

    # 17 -----------------------------------------------------------------
    def _wallet_leakage(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.WALLET_LEAKAGE, self.as_of, self.registry)
        probability, at_risk, reasons = self._client_leakage(entity_id, context)
        claims = context["claims"]
        declines = [
            (product, self._ratio(claims, concept))
            for product, concept in (
                ("Payments", "bank_observed_payments_yoy_change"),
                ("Collections", "bank_observed_collections_yoy_change"),
                ("Cross-border FX", "bank_observed_cross_border_fx_yoy_change"),
                ("Liquidity", "bank_observed_liquidity_yoy_change"),
                ("Trade finance", "bank_observed_trade_finance_yoy_change"),
            )
        ]
        falling = [(product, value) for product, value in declines if value is not None and value < -0.05]
        identified = bool(falling) and probability > 0.0
        intensity: Optional[SignedInterval] = None
        if at_risk > 0:
            intensity = SignedInterval(
                lower=at_risk * 0.5, median=at_risk, upper=at_risk * 1.5, unit="ZAR"
            )
        for product, value in falling:
            builder.add(
                "OBSERVED_FLOW_DECLINE",
                f"Bank-observed {product} flow is down {abs(value):.0%} year on year.",
                min(0.45, abs(value)),
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
        if probability > 0:
            builder.add(
                "V3_LEAKAGE_ALARM",
                f"V3 change-point leakage alarm probability is {probability:.0%} against a "
                "reconstructed, not measured, external wallet.",
                probability * 0.6,
                claim_class=ClaimClass.POSTERIOR,
            )
        if not falling:
            builder.add(
                "NO_MATERIAL_OBSERVED_DECLINE",
                "No bank-observed product flow has declined materially.",
                0.50,
                disconfirming=True,
                claim_class=ClaimClass.OBSERVED,
                bank_observed=True,
            )
        builder.add(
            "EXTERNAL_WALLET_RECONSTRUCTED_NOT_MEASURED",
            "External provider flow is reconstructed under an entropy constraint and is not a "
            "measurement of competitor share.",
            0.20,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        for reason in reasons:
            builder.reason_codes.append(reason)
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR reconstructed external flow at risk",
            claim_class=ClaimClass.POSTERIOR,
            calibration_status=POSTERIOR_CALIBRATION,
            domains=[D.REVENUE_ENGINE, D.COST_ENGINE, D.OPERATING_MODEL],
        )

    # 18 -----------------------------------------------------------------
    def _operational_resilience(
        self, entity_id: str, context: Dict[str, Any]
    ) -> ProblemHypothesis:
        builder = _Builder(entity_id, P.OPERATIONAL_RESILIENCE, self.as_of, self.registry)
        claims = context["claims"]
        breadth = self._count(claims, "bank_observed_product_relationship_breadth") or 0
        countries = self._count(claims, "bank_observed_active_country_count") or 0
        identified = breadth >= 4 and countries >= 10
        intensity: Optional[SignedInterval] = None
        payments = self._money(claims, "bank_observed_payments_ltm")
        if identified:
            builder.add(
                "CONCENTRATED_OPERATIONAL_DEPENDENCE",
                f"The bank carries {breadth} of five product relationships across {countries} "
                "countries, which concentrates operational dependence.",
                0.35,
                claim_ids=[
                    claims["bank_observed_product_relationship_breadth"].claim_id,
                    claims["bank_observed_active_country_count"].claim_id,
                ],
                bank_observed=True,
                claim_class=ClaimClass.OBSERVED,
            )
            if payments:
                intensity = self._interval_from(payments, 0.20)
        builder.add(
            "CONTINUITY_ARRANGEMENTS_UNKNOWN",
            "Existing continuity, failover and secondary-bank arrangements are not disclosed.",
            0.40,
            disconfirming=True,
            claim_class=ClaimClass.SCENARIO,
        )
        return builder.build(
            identified=identified,
            intensity=intensity,
            intensity_unit="ZAR operationally dependent flow",
            domains=[D.OPERATING_MODEL, D.BUSINESS_AND_FINANCIAL_RISKS],
        )
