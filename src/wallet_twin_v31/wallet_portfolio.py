"""Wallet-first V3.1.1 projection and forensic drill-down.

The Decision Twin remains the action layer.  This module restores the latent
share-of-wallet chain as the primary read model without changing the governed
V2 estimates underneath it.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, Optional, Sequence

from wallet_twin_v2.contracts import OpportunityView
from wallet_twin_v2.measurement_policy import DEFAULT_MEASUREMENT_POLICY
from wallet_twin_v2.public_evidence import ANCHOR_ACTIVATION_POLICY_VERSION
from wallet_twin_v2.repository import ShadowRepository

from .contracts import (
    ConversationCandidate,
    WalletOpportunityDetail,
    WalletPortfolioCell,
    WalletPortfolioProjection,
    WalletProductSummary,
    WalletValueInterval,
)
from .taxonomy import BankingSolution, LEGACY_PRODUCT_SOLUTION


#: Placeholder written by the exporter and replaced by the canonical build.
#: A published artifact must never carry a submission verdict it did not compute:
#: an artifact that guesses is worse than one that says it does not know.
HACKATHON_STATUS_PENDING = "HACKATHON_STATUS_PENDING_CANONICAL_BUILD"

PRODUCTS = ["Collections", "Payments", "Liquidity", "Cross-border FX", "Trade finance"]
QUANTITY_SEMANTICS = {
    "Collections": "transaction activity wallet",
    "Payments": "transaction activity wallet",
    "Liquidity": "liquidity-flow opportunity proxy; not a stock balance or banking spend",
    "Cross-border FX": "cross-border exposure proxy; not executed FX revenue or measured competitor flow",
    "Trade finance": "eligible trade-flow wallet",
}


def _contestable(observation: OpportunityView) -> WalletValueInterval:
    target = observation.commercial.target_share or 0.0
    values = [
        max(target * total - float(observation.observed_activity.normalized_amount), 0.0)
        for total in (
            observation.posterior_wallet.lower,
            observation.posterior_wallet.median,
            observation.posterior_wallet.upper,
        )
    ]
    return WalletValueInterval(
        lower=round(values[0], 2),
        median=round(values[1], 2),
        upper=round(values[2], 2),
        unit="annual_activity",
    )


def _contribution(observation: OpportunityView, gap: WalletValueInterval) -> Optional[WalletValueInterval]:
    commercial = observation.commercial.contestable_scenario_contribution
    if commercial is None or gap.median <= 0:
        return None
    median = float(commercial.normalized_amount)
    unit_rate = median / gap.median
    return WalletValueInterval(
        lower=round(gap.lower * unit_rate, 2),
        median=round(median, 2),
        upper=round(gap.upper * unit_rate, 2),
        unit="annual_scenario_contribution",
    )


def _approval_state(observation: OpportunityView) -> str:
    if observation.anchor_activation.value == "ACTIVATED":
        return "APPROVED"
    if observation.pending_evidence_fact_ids:
        return "PENDING_REVIEW_EXCLUDED"
    return "NO_ACTIVE_PUBLIC_ANCHOR"


def _actions(observation: OpportunityView) -> tuple[str, str]:
    if observation.anchor_activation.value == "ACTIVATED":
        return (
            "VALIDATE_WALLET_AND_FEASIBILITY",
            "If the client confirms external wallet and required feasibility gates, develop a governed commercial proposal.",
        )
    return (
        "DISCOVER_TOTAL_WALLET_AND_VALIDATE_PUBLIC_CANDIDATE",
        "If the missing wallet fact is confirmed and finance-SME approval is recorded, rerun the point-in-time estimate before any proposal.",
    )


def build_cell(observation: OpportunityView) -> WalletPortfolioCell:
    gap = _contestable(observation)
    current, conditional = _actions(observation)
    return WalletPortfolioCell(
        opportunity_id=observation.opportunity_id,
        entity_id=observation.entity_id,
        entity_name=observation.entity_name,
        sector=observation.sector,
        product=observation.product,
        product_quantity_semantics=QUANTITY_SEMANTICS[observation.product],
        as_of=observation.as_of,
        observed_activity=observation.observed_activity,
        identification_bounds=observation.identification_bounds,
        posterior_wallet=observation.posterior_wallet,
        share_interval=observation.share_interval,
        target_share_scenario=observation.commercial.target_share or 0.0,
        contestable_activity=gap,
        scenario_contribution=_contribution(observation, gap),
        timing=observation.timing,
        evidence_tier=observation.evidence_tier,
        approval_state=_approval_state(observation),
        anchor_activation=observation.anchor_activation.value,
        calibration_status=observation.calibration_status.value,
        share_claim_class=observation.share_claim,
        rank=observation.rank,
        active_fact_ids=list(observation.evidence_fact_ids),
        pending_fact_ids=list(observation.pending_evidence_fact_ids),
        permitted_action_now=current,
        conditional_action=conditional,
        artifact_versions=observation.artifacts,
    )


def build_wallet_portfolio(
    source: ShadowRepository,
    *,
    entitled_client_ids: Sequence[str] = ("*",),
) -> WalletPortfolioProjection:
    allow_all = "*" in entitled_client_ids
    observations = [
        item for item in source.opportunities
        if allow_all or item.entity_id in entitled_client_ids
    ]
    cells = [build_cell(item) for item in observations]
    cells.sort(key=lambda item: (item.entity_id, PRODUCTS.index(item.product)))
    summaries: Dict[str, Dict[str, float | int]] = defaultdict(
        lambda: {"cells": 0, "observed": 0.0, "contribution": 0.0, "approved": 0, "prior": 0}
    )
    for cell in cells:
        summary = summaries[cell.product]
        summary["cells"] += 1
        summary["observed"] += float(cell.observed_activity.normalized_amount)
        summary["contribution"] += cell.scenario_contribution.median if cell.scenario_contribution else 0.0
        summary["approved" if cell.anchor_activation == "ACTIVATED" else "prior"] += 1

    client_count = len({cell.entity_id for cell in cells})
    approved = sum(cell.anchor_activation == "ACTIVATED" for cell in cells)
    return WalletPortfolioProjection(
        as_of=source.as_of,
        clients=client_count,
        products=PRODUCTS,
        cells=cells,
        product_summaries=[
            WalletProductSummary(
                product=product,
                cells=int(summaries[product]["cells"]),
                observed_activity_zar=round(float(summaries[product]["observed"]), 2),
                scenario_contribution_zar=round(float(summaries[product]["contribution"]), 2),
                approved_anchor_cells=int(summaries[product]["approved"]),
                prior_led_cells=int(summaries[product]["prior"]),
            )
            for product in PRODUCTS
            if summaries[product]["cells"]
        ],
        top_opportunity_ids=[
            item.opportunity_id for item in sorted(
                cells,
                key=lambda item: (
                    -(item.scenario_contribution.median if item.scenario_contribution else 0.0),
                    item.opportunity_id,
                ),
            )[:10]
        ],
        approved_anchor_cells=approved,
        prior_led_cells=len(cells) - approved,
        approved_source_facts=int(source.evidence_coverage["approved_e1_facts"]),
        pending_source_facts=int(source.evidence_coverage["pending_sme_facts"]),
        active_anchor_policy_version=ANCHOR_ACTIVATION_POLICY_VERSION,
        measurement_policy_version=DEFAULT_MEASUREMENT_POLICY.version,
        claim_boundary={
            "observed": "Syn Bank supplied simulated activity; no competitor transaction is observed.",
            "identified": "Bounds are assumption-light sets, not probability intervals.",
            "posterior": "Wallet and share intervals are model-based and prior-led unless an approved E1 anchor activates.",
            "scenario": "Target share and contribution use representative inputs, not approved bank pricing.",
            "causal": "Causal incremental value is withheld; no measured competitor-share or uplift claim is made.",
        },
        release={
            # The wallet surface is exported before the live-provider comparison
            # exists, so it cannot compute a submission verdict. Asserting one
            # here is how the workbench came to display BLOCKED while the judging
            # manifest claimed READY. The canonical status is stamped in by
            # scripts/build_submission.py once the inputs it depends on resolve.
            "hackathon_status": HACKATHON_STATUS_PENDING,
            "hackathon_status_source": "outputs/judging_manifest_v3.1.1.json",
            # Invariant by design, not a computed verdict: every governance test
            # asserts this value and no run may change it.
            "bank_production_status": "NOT_PROMOTABLE",
            "data_mode": source.metadata["deployment_mode"],
        },
    )


def build_wallet_detail(
    source: ShadowRepository,
    opportunity_id: str,
    *,
    conversations: Iterable[ConversationCandidate] = (),
) -> WalletOpportunityDetail:
    observation = source.opportunity(opportunity_id, source.as_of)
    cell = build_cell(observation)
    facts = [source.facts[fact_id] for fact_id in cell.active_fact_ids if fact_id in source.facts]
    pending = [source.facts[fact_id] for fact_id in cell.pending_fact_ids if fact_id in source.facts]
    action = None
    solution: BankingSolution = LEGACY_PRODUCT_SOLUTION[cell.product]
    choices = [
        item for item in conversations
        if item.entity_id == cell.entity_id and solution in item.solution_bundle.solutions
    ]
    if choices:
        choice = sorted(
            choices,
            key=lambda item: (
                item.policy_rank.weekly_rank is None,
                item.policy_rank.weekly_rank or 10_000,
                -item.policy_rank.selection_stability,
            ),
        )[0]
        action = {
            "conversation_id": choice.conversation_id,
            "stakeholder_role": choice.stakeholder.primary_role.value,
            "problem": choice.problem.label,
            "solution_bundle": [item.value for item in choice.solution_bundle.solutions],
            "why_now": choice.engagement_window.why_now,
            "permitted_action": choice.action.value,
            "conditional_action": cell.conditional_action,
        }
    return WalletOpportunityDetail(
        cell=cell,
        explanation={
            "A": {"value": float(cell.observed_activity.normalized_amount), "unit": cell.observed_activity.source_unit, "claim_class": "OBSERVED"},
            "T": {"p10": cell.posterior_wallet.lower, "p50": cell.posterior_wallet.median, "p90": cell.posterior_wallet.upper, "claim_class": "POSTERIOR"},
            "q": {"p10": cell.share_interval.lower, "p50": cell.share_interval.median, "p90": cell.share_interval.upper, "identity_check": math.isclose(float(cell.observed_activity.normalized_amount) / cell.posterior_wallet.median, cell.share_interval.median, rel_tol=1e-4, abs_tol=1e-6), "declared_tolerance": "relative 1e-4; independently summarized posterior quantiles"},
            "q_star": {"value": cell.target_share_scenario, "claim_class": "SCENARIO"},
            "G": {"p10": cell.contestable_activity.lower, "p50": cell.contestable_activity.median, "p90": cell.contestable_activity.upper, "claim_class": "SCENARIO"},
        },
        supporting_facts=[
            {**fact, "use_in_estimate": True, "qa_and_approval_state": "APPROVED_ACTIVE"}
            for fact in facts
        ] + [
            {**fact, "use_in_estimate": False, "qa_and_approval_state": "PENDING_REVIEW_EXCLUDED"}
            for fact in pending
        ],
        decision_twin_action=action,
        claim_boundary=build_wallet_portfolio(source).claim_boundary,
    )
