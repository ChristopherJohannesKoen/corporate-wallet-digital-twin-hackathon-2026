from __future__ import annotations

from datetime import date
from typing import Sequence

from wallet_twin_v2.contracts import OpportunityView

from .contracts import (
    EvidenceAcquisitionCandidate,
    EvidenceAcquisitionPlan,
    PortfolioAction,
    ShadowWalletReconstruction,
)


class DecisionDirectedEvidencePlanner:
    """Selects evidence only when expected decision utility exceeds cost/latency."""

    def plan(
        self,
        opportunities: Sequence[OpportunityView],
        selected_actions: Sequence[PortfolioAction],
        shadows: dict[str, ShadowWalletReconstruction],
        as_of: date,
        capacity: int = 8,
    ) -> EvidenceAcquisitionPlan:
        selected_ids = {action.opportunity_id for action in selected_actions}
        candidates: list[EvidenceAcquisitionCandidate] = []
        for opportunity in opportunities:
            if opportunity.opportunity_id not in selected_ids:
                continue
            shadow = shadows[opportunity.opportunity_id]
            commercial = opportunity.commercial.contestable_scenario_contribution
            base_value = float(commercial.normalized_amount) if commercial else 0.0
            width = (shadow.total_wallet.upper - shadow.total_wallet.lower) / max(
                shadow.total_wallet.median, 1.0
            )
            rank_uncertainty = 1.0 - float(opportunity.rank_probability or 0.0)
            specifications = [
                (
                    "E3 multibank share observation",
                    0.52,
                    0.42,
                    90_000.0,
                    0.08,
                    "data-owner + client consent",
                ),
                (
                    "finance-approved product rate card",
                    0.31,
                    0.28,
                    35_000.0,
                    0.04,
                    "product finance + Treasury",
                ),
                (
                    "E2 client/RM attestation",
                    0.22,
                    0.18,
                    8_000.0,
                    0.02,
                    "RM + client attestation workflow",
                ),
            ]
            for (
                evidence_type,
                narrowing,
                rank_factor,
                cost,
                latency_rate,
                approval,
            ) in specifications:
                decision_value = (
                    base_value
                    * min(1.5, width)
                    * (0.25 + rank_uncertainty)
                    * rank_factor
                )
                latency_penalty = base_value * latency_rate
                net = decision_value - cost - latency_penalty
                candidates.append(
                    EvidenceAcquisitionCandidate(
                        candidate_id=f"voi:{opportunity.opportunity_id}:{evidence_type.lower().replace(' ', '-')}",
                        opportunity_id=opportunity.opportunity_id,
                        entity_id=opportunity.entity_id,
                        product=opportunity.product,
                        evidence_type=evidence_type,
                        expected_decision_value_zar=max(0.0, decision_value),
                        acquisition_cost_zar=cost,
                        latency_penalty_zar=max(0.0, latency_penalty),
                        net_value_of_information_zar=net,
                        expected_interval_width_reduction=narrowing,
                        expected_rank_flip_probability=min(
                            1.0, rank_uncertainty * rank_factor + 0.05
                        ),
                        retrieve=net > 0,
                        required_approval=approval,
                    )
                )

        ordered = sorted(
            candidates,
            key=lambda item: (-item.net_value_of_information_zar, item.candidate_id),
        )
        selected = [item for item in ordered if item.retrieve][:capacity]
        selected_keys = {item.candidate_id for item in selected}
        deferred = [item for item in ordered if item.candidate_id not in selected_keys]
        return EvidenceAcquisitionPlan(
            plan_id=f"decision-directed-evidence:{as_of.isoformat()}:v3.0.0",
            as_of=as_of,
            capacity=capacity,
            selected=selected,
            deferred=deferred,
            total_expected_net_voi_zar=sum(
                item.net_value_of_information_zar for item in selected
            ),
            policy="retrieve only positive-net-VOI evidence for capacity-selected decisions; require source entitlement and human approval",
        )
