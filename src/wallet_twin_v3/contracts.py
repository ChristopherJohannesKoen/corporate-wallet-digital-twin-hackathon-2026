from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List

from pydantic import Field, model_validator

from wallet_twin_v2.contracts import (
    ClaimClass,
    DataProvenanceClass,
    EvidenceTier,
    StrictModel,
)


class V3ModelStatus(str, Enum):
    REPRESENTATIVE_VALIDATION = "REPRESENTATIVE_VALIDATION"
    SHADOW_ELIGIBLE = "SHADOW_ELIGIBLE"
    PRODUCTION_BLOCKED = "PRODUCTION_BLOCKED"


class AmountInterval(StrictModel):
    lower: float = Field(ge=0)
    median: float = Field(ge=0)
    upper: float = Field(ge=0)
    currency: str = "ZAR"

    @model_validator(mode="after")
    def ordered(self) -> "AmountInterval":
        if not self.lower <= self.median <= self.upper:
            raise ValueError("amount interval must satisfy lower <= median <= upper")
        return self


class ShadowFlow(StrictModel):
    edge_id: str
    entity_id: str
    product: str
    corridor: str
    provider_node: str
    amount: AmountInterval
    observed_by_bank: bool
    claim_class: ClaimClass
    provenance: DataProvenanceClass


class ShadowWalletReconstruction(StrictModel):
    reconstruction_id: str
    opportunity_id: str
    entity_id: str
    product: str
    as_of: date
    observed_bank_flow: float = Field(ge=0)
    total_wallet: AmountInterval
    latent_external_wallet: AmountInterval
    bank_share: AmountInterval
    flows: List[ShadowFlow]
    normalized_entropy: float = Field(ge=0, le=1)
    ensemble_draws: int = Field(ge=32)
    method: str
    claim_class: ClaimClass = ClaimClass.SCENARIO
    provenance: DataProvenanceClass = DataProvenanceClass.SYNTHETIC_SIMULATION
    measurement_status: str = "RECONSTRUCTED_NOT_MEASURED"

    @model_validator(mode="after")
    def balances(self) -> "ShadowWalletReconstruction":
        expected = max(0.0, self.total_wallet.median - self.observed_bank_flow)
        tolerance = max(1.0, expected * 1e-6)
        if abs(self.latent_external_wallet.median - expected) > tolerance:
            raise ValueError(
                "latent wallet must reconcile to total minus observed flow"
            )
        external = sum(
            flow.amount.median for flow in self.flows if not flow.observed_by_bank
        )
        if abs(external - self.latent_external_wallet.median) > tolerance:
            raise ValueError("external shadow flows must reconcile to latent wallet")
        return self


class ProductNeedEstimate(StrictModel):
    opportunity_id: str
    entity_id: str
    product: str
    positive_label_observed: bool
    labelled_positive_probability: float = Field(ge=0, le=1)
    product_need_probability: float = Field(ge=0, le=1)
    selection_constant: float = Field(gt=0, le=1)
    assumptions: List[str]
    method: str = "Elkan-Noto SCAR correction over transparent logistic base learner"
    claim_class: ClaimClass = ClaimClass.POSTERIOR
    evidence_tier: EvidenceTier = EvidenceTier.E0


class ChangePointSignal(StrictModel):
    opportunity_id: str
    entity_id: str
    product: str
    as_of: date
    current_probability: float = Field(ge=0, le=1)
    recent_peak_probability: float = Field(ge=0, le=1)
    run_length_mode_months: int = Field(ge=0)
    signed_level_shift: float
    probability_30d: float = Field(ge=0, le=1)
    probability_60d: float = Field(ge=0, le=1)
    probability_90d: float = Field(ge=0, le=1)
    method: str
    calibration_status: str
    claim_class: ClaimClass = ClaimClass.POSTERIOR

    @model_validator(mode="after")
    def monotone(self) -> "ChangePointSignal":
        if not self.probability_30d <= self.probability_60d <= self.probability_90d:
            raise ValueError("horizon probabilities must be monotone")
        return self


class LeakageAlarm(StrictModel):
    opportunity_id: str
    entity_id: str
    product: str
    alarm_probability: float = Field(ge=0, le=1)
    expected_external_flow_at_risk_zar: float = Field(ge=0)
    observed_level_decline: float = Field(ge=0, le=1)
    severity: str
    reason_codes: List[str]
    claim_class: ClaimClass = ClaimClass.POSTERIOR
    measurement_status: str = "MODELLED_SIGNAL_NOT_CONFIRMED_LEAKAGE"


class PortfolioAction(StrictModel):
    action_id: str
    opportunity_id: str
    entity_id: str
    entity_name: str
    sector: str
    product: str
    robust_score: float
    expected_scenario_value_zar: float = Field(ge=0)
    downside_cvar_zar: float = Field(ge=0)
    need_probability: float = Field(ge=0, le=1)
    leakage_probability: float = Field(ge=0, le=1)
    evidence_tier: EvidenceTier
    claim_class: ClaimClass = ClaimClass.SCENARIO


class RobustActionPortfolio(StrictModel):
    portfolio_id: str
    as_of: date
    capacity: int = Field(gt=0)
    selected_actions: List[PortfolioAction]
    expected_scenario_value_zar: float = Field(ge=0)
    downside_cvar_zar: float = Field(ge=0)
    product_counts: dict[str, int]
    sector_counts: dict[str, int]
    constraints: dict[str, int]
    scenario_draws: int = Field(ge=100)
    method: str
    commercial_status: str = "REPRESENTATIVE_SCENARIO_NOT_BANK_APPROVED"
    causal_status: str = "CAUSAL_INCREMENTAL_VALUE_WITHHELD"


class EvidenceAcquisitionCandidate(StrictModel):
    candidate_id: str
    opportunity_id: str
    entity_id: str
    product: str
    evidence_type: str
    expected_decision_value_zar: float = Field(ge=0)
    acquisition_cost_zar: float = Field(ge=0)
    latency_penalty_zar: float = Field(ge=0)
    net_value_of_information_zar: float
    expected_interval_width_reduction: float = Field(ge=0, le=1)
    expected_rank_flip_probability: float = Field(ge=0, le=1)
    retrieve: bool
    required_approval: str


class EvidenceAcquisitionPlan(StrictModel):
    plan_id: str
    as_of: date
    capacity: int = Field(gt=0)
    selected: List[EvidenceAcquisitionCandidate]
    deferred: List[EvidenceAcquisitionCandidate]
    total_expected_net_voi_zar: float = Field(ge=0)
    policy: str
    autonomous_external_retrieval: bool = False


class V3OpportunityView(StrictModel):
    opportunity_id: str
    entity_id: str
    entity_name: str
    sector: str
    product: str
    as_of: date
    v2_rank: int | None
    need: ProductNeedEstimate
    shadow_wallet: ShadowWalletReconstruction
    change_point: ChangePointSignal
    leakage: LeakageAlarm
    decision_score: float
    evidence_tier: EvidenceTier
    commercial_status: str
