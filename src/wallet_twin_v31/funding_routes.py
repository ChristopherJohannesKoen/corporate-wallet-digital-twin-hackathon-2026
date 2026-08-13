"""Funding Route Intelligence.

For a material funding requirement, estimate a distribution over six routes.
V3.1 ships a *transparent scorecard*, not a learned classifier: every input,
every weight and every partial score is exposed, and the probabilities are a
softmax over auditable scores rather than a fitted model output.

A multinomial challenger is registered but cannot replace the scorecard until a
point-in-time panel contains at least 500 labelled financing events with at
least 50 per promoted route, validated issuer-held-out and temporally.  Until
then the challenger is ``REGISTERED_NOT_ELIGIBLE`` and the champion is the
scorecard.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Dict, List, Mapping, Optional

from wallet_twin_v2.contracts import ClaimClass

from .business_evidence import BusinessEvidenceRegistry
from .contracts import (
    ComponentStatus,
    FundingRouteProjection,
    FundingRouteScore,
    IndicatorValue,
    SignedInterval,
)
from .taxonomy import FundingRoute as R

SCORECARD_VERSION = "v31-funding-route-scorecard-3.1.1"
CHALLENGER_VERSION = "v31-funding-route-multinomial-challenger-3.1.1"

CHALLENGER_STATUS = (
    "REGISTERED_NOT_ELIGIBLE â€” a multinomial challenger is registered but cannot replace "
    "the scorecard until a point-in-time panel holds at least 500 labelled financing "
    "events with at least 50 events per promoted route, validated issuer-held-out and "
    "temporally"
)
MODEL_STATUS = (
    "TRANSPARENT_SCORECARD_BASELINE_NOT_EMPIRICALLY_VALIDATED â€” route weights are "
    "governed policy, not fitted coefficients"
)

#: Base scores per route before evidence.  Reflect the observed South African
#: corporate funding mix at a coarse level and are governed policy.
BASE_SCORES: Mapping[R, float] = {
    R.BANK_DEBT: 1.10,
    R.BOND_DCM: 0.70,
    R.EQUITY: 0.10,
    R.PROJECT_FINANCE: 0.15,
    R.INTERNAL_CASH: 0.80,
    R.HYBRID_OTHER: 0.05,
}

#: Sectors where a bond programme is materially more common.
DCM_ACTIVE_SECTORS = frozenset({"telecoms", "real_estate", "mining", "insurance"})
PROJECT_SECTORS = frozenset({"mining", "telecoms", "real_estate"})


class FundingRouteEngine:
    version = SCORECARD_VERSION

    def __init__(self, registry: BusinessEvidenceRegistry, as_of: date) -> None:
        self.registry = registry
        self.as_of = as_of

    def project(
        self,
        entity_id: str,
        *,
        sector: str,
        indicators: Mapping[str, IndicatorValue],
        has_project_evidence: bool = False,
        historical_route: Optional[R] = None,
    ) -> FundingRouteProjection:
        scores: Dict[R, float] = dict(BASE_SCORES)
        drivers: Dict[R, Dict[str, float]] = {route: {} for route in R}
        inputs: Dict[str, float] = {}
        missing: List[str] = []
        claim_ids: List[str] = []

        def bump(route: R, name: str, amount: float) -> None:
            scores[route] += amount
            drivers[route][name] = round(amount, 4)

        leverage = indicators.get("LEVERAGE_PROXY")
        if leverage is not None and leverage.available:
            value = leverage.interval.median
            inputs["leverage_proxy"] = value
            claim_ids.extend(leverage.evidence_claim_ids)
            # More leverage pushes towards capital markets and away from
            # additional bilateral bank debt.
            bump(R.BANK_DEBT, "leverage", -0.60 * min(value, 1.0))
            bump(R.BOND_DCM, "leverage", 0.55 * min(value, 1.0))
            bump(R.EQUITY, "leverage", 0.35 * min(value, 1.0))
        else:
            missing.append("leverage_proxy")

        cash_cover = indicators.get("CASH_COVER")
        if cash_cover is not None and cash_cover.available:
            value = cash_cover.interval.median
            inputs["cash_cover"] = value
            claim_ids.extend(cash_cover.evidence_claim_ids)
            # Strong cash cover means the requirement may simply be self-funded.
            bump(R.INTERNAL_CASH, "cash_cover", 0.80 * min(value, 2.0))
            bump(R.BANK_DEBT, "cash_cover", -0.20 * min(value, 2.0))
        else:
            missing.append("cash_cover")

        exposure = indicators.get("REFINANCING_EXPOSURE_12M")
        if exposure is not None and exposure.available:
            value = exposure.interval.median
            inputs["refinancing_exposure_zar"] = value
            claim_ids.extend(exposure.evidence_claim_ids)
            if value > 0:
                bump(R.BANK_DEBT, "near_term_maturity", 0.45)
                bump(R.BOND_DCM, "near_term_maturity", 0.35)
                bump(R.INTERNAL_CASH, "near_term_maturity", -0.35)
        else:
            missing.append("refinancing_exposure")

        if sector in DCM_ACTIVE_SECTORS:
            bump(R.BOND_DCM, "sector_capital_market_activity", 0.35)
        if sector in PROJECT_SECTORS and has_project_evidence:
            bump(R.PROJECT_FINANCE, "project_evidence", 0.90)
        elif sector in PROJECT_SECTORS:
            # A project-intensive sector is not the same as an evidenced project.
            bump(R.PROJECT_FINANCE, "project_sector_without_evidence", 0.15)
            missing.append("reviewed_project_or_spv_evidence")

        if historical_route is not None:
            bump(historical_route, "historical_route_preference", 0.50)
            inputs["historical_route_known"] = 1.0
        else:
            missing.append("historical_funding_route")

        total = sum(math.exp(value) for value in scores.values())
        route_scores = [
            FundingRouteScore(
                route=route,
                probability=math.exp(scores[route]) / total,
                score=round(scores[route], 4),
                drivers=drivers[route],
            )
            for route in R
        ]
        # Renormalise defensively so the contract invariant holds exactly.
        mass = sum(item.probability for item in route_scores)
        route_scores = [
            item.model_copy(update={"probability": item.probability / mass})
            for item in route_scores
        ]

        requirement: Optional[SignedInterval] = None
        requirement_status = ComponentStatus.UNKNOWN
        if exposure is not None and exposure.available and exposure.interval.median > 0:
            requirement = exposure.interval
            requirement_status = (
                ComponentStatus.SUPPORTED
                if exposure.governed
                else ComponentStatus.INFERRED
            )

        return FundingRouteProjection(
            projection_id=f"funding-route:{entity_id}:{self.as_of.isoformat()}",
            entity_id=entity_id,
            as_of=self.as_of,
            requirement=requirement,
            requirement_status=requirement_status,
            routes=route_scores,
            inputs=inputs,
            missing_inputs=sorted(set(missing)),
            method=(
                "transparent additive scorecard over leverage, cash cover, near-term "
                "maturity, sector capital-market activity, project evidence and historical "
                "route, mapped to probabilities by softmax"
            ),
            model_status=MODEL_STATUS,
            challenger_status=CHALLENGER_STATUS,
            claim_class=ClaimClass.SCENARIO,
            evidence_claim_ids=sorted(set(claim_ids)),
        )


CHALLENGER_GATE = {
    "challenger": CHALLENGER_VERSION,
    "champion": SCORECARD_VERSION,
    "promotion_allowed": False,
    "required_labelled_events": 500,
    "required_events_per_promoted_route": 50,
    "required_validation": [
        "issuer-held-out split",
        "temporal (point-in-time) split",
        "route-level calibration",
    ],
    "current_labelled_events": 0,
    "reason": "no labelled financing-event panel exists in the demonstration boundary",
}
