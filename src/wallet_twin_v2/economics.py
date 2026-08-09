from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable, List, Optional

from .contracts import (
    ApprovalStatus,
    CommercialResult,
    CommercialStatus,
    DeploymentEnvironment,
    Money,
    RateCard,
)


class EconomicsService:
    """Fail-closed contribution calculations over effective-dated rate cards."""

    _cost_fields = (
        "client_discount_bps",
        "ftp_bps",
        "liquidity_bps",
        "expected_loss_bps",
        "capital_bps",
        "hedging_bps",
        "execution_bps",
        "servicing_bps",
        "operating_cost_bps",
        "tax_bps",
    )

    @classmethod
    def net_bps(cls, rate_card: RateCard) -> Decimal:
        costs = sum((getattr(rate_card, field) for field in cls._cost_fields), Decimal("0"))
        return rate_card.gross_price_bps - costs

    @staticmethod
    def _money(value: Decimal) -> Money:
        return Money(
            amount=value,
            currency="ZAR",
            normalized_amount=value,
            normalized_currency="ZAR",
            source_unit="annual_contribution",
            fx_policy_ref="identity-zar",
        )

    def evaluate(
        self,
        *,
        as_of: date,
        environment: DeploymentEnvironment,
        rate_card: Optional[RateCard],
        observed_activity: float,
        wallet_median: float,
        current_share: float,
        target_share: float,
        capacity: Optional[float] = None,
        causal_uplift: Optional[float] = None,
        causal_model_approved: bool = False,
    ) -> CommercialResult:
        reasons: List[str] = []
        if rate_card is None:
            reasons.append("RATE_CARD_MISSING")
        else:
            if rate_card.approval_status != ApprovalStatus.APPROVED:
                reasons.append("RATE_CARD_NOT_APPROVED")
            if rate_card.reconciliation_status != "RECONCILED":
                reasons.append("RATE_CARD_NOT_RECONCILED")
            if not rate_card.effective_from <= as_of <= rate_card.effective_to:
                reasons.append("RATE_CARD_NOT_EFFECTIVE")
            if environment in {DeploymentEnvironment.SHADOW, DeploymentEnvironment.PILOT, DeploymentEnvironment.PRODUCTION} and rate_card.synthetic:
                reasons.append("SYNTHETIC_RATE_BLOCKED_IN_CONTROLLED_ENVIRONMENT")
        if reasons:
            return CommercialResult(status=CommercialStatus.BLOCKED, reason_codes=reasons)

        assert rate_card is not None
        net_bps = self.net_bps(rate_card)
        if net_bps <= rate_card.approved_hurdle_bps:
            return CommercialResult(
                status=CommercialStatus.BLOCKED,
                net_unit_contribution_bps=float(net_bps),
                rate_card_ref=f"{rate_card.rate_card_id}:{rate_card.version}",
                reason_codes=["NET_CONTRIBUTION_BELOW_APPROVED_HURDLE"],
            )

        contestable_activity = max(target_share * wallet_median - observed_activity, 0.0)
        if capacity is not None:
            contestable_activity = min(contestable_activity, max(capacity - observed_activity, 0.0))
        rate = net_bps / Decimal("10000")
        observed = Decimal(str(observed_activity)) * rate
        contestable = Decimal(str(contestable_activity)) * rate - rate_card.acquisition_cost
        contestable = max(Decimal("0"), contestable)

        simulated = rate_card.synthetic or environment in {
            DeploymentEnvironment.FIXTURE,
            DeploymentEnvironment.DEVELOPMENT,
            DeploymentEnvironment.CLIENT_DEMO,
        }
        status = CommercialStatus.SIMULATED if simulated else CommercialStatus.APPROVED_SCENARIO
        causal_value = None
        if causal_uplift is not None:
            if causal_model_approved:
                causal_value = self._money(contestable * Decimal(str(causal_uplift)))
                status = CommercialStatus.CAUSAL
            else:
                reasons.append("CAUSAL_VALUE_WITHHELD_UNTIL_VALIDATION")

        return CommercialResult(
            status=status,
            observed_contribution=self._money(observed),
            contestable_scenario_contribution=self._money(contestable),
            causal_expected_incremental_value=causal_value,
            net_unit_contribution_bps=float(net_bps),
            target_share=target_share,
            watermark=(
                "CLIENT-DEMO SCENARIO ECONOMICS — REPRESENTATIVE INPUTS — NOT BANK-APPROVED PRICING"
                if environment == DeploymentEnvironment.CLIENT_DEMO
                else "SIMULATED NON-PRODUCTION ECONOMICS"
            ) if simulated else None,
            reason_codes=reasons,
            rate_card_ref=f"{rate_card.rate_card_id}:{rate_card.version}",
        )

    def scenario_frontier(
        self,
        *,
        shares: Iterable[float],
        **kwargs: object,
    ) -> List[CommercialResult]:
        return [self.evaluate(target_share=share, **kwargs) for share in shares]
