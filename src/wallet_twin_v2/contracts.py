from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=False,
    )


class EvidenceTier(str, Enum):
    E0 = "E0"
    E1 = "E1"
    E2 = "E2"
    E3 = "E3"
    E4 = "E4"


class ClaimClass(str, Enum):
    OBSERVED = "OBSERVED"
    IDENTIFIED_BOUND = "IDENTIFIED_BOUND"
    POSTERIOR = "POSTERIOR"
    SCENARIO = "SCENARIO"
    CAUSAL = "CAUSAL"


class ApprovalStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class QualityStatus(str, Enum):
    VALID = "VALID"
    QUARANTINED = "QUARANTINED"
    LEGACY_INCOMPLETE = "LEGACY_INCOMPLETE"


class DeploymentEnvironment(str, Enum):
    FIXTURE = "FIXTURE"
    DEVELOPMENT = "DEVELOPMENT"
    CLIENT_DEMO = "CLIENT_DEMO"
    SHADOW = "SHADOW"
    PILOT = "PILOT"
    PRODUCTION = "PRODUCTION"


class DataProvenanceClass(str, Enum):
    BANK_OBSERVED = "BANK_OBSERVED"
    PUBLIC_AUDITED = "PUBLIC_AUDITED"
    CLIENT_ATTESTED = "CLIENT_ATTESTED"
    MULTIBANK_OBSERVED = "MULTIBANK_OBSERVED"
    REPRESENTATIVE_PUBLIC = "REPRESENTATIVE_PUBLIC"
    SYNTHETIC_SIMULATION = "SYNTHETIC_SIMULATION"


class DataUsageClass(str, Enum):
    PRODUCTION_ELIGIBLE = "PRODUCTION_ELIGIBLE"
    CLIENT_DEMO_AND_VALIDATION = "CLIENT_DEMO_AND_VALIDATION"
    VALIDATION_ONLY = "VALIDATION_ONLY"


class EligibilityState(str, Enum):
    BLOCKED = "BLOCKED"
    SHADOW_ONLY = "SHADOW_ONLY"
    ALLOWED = "ALLOWED"


class CommercialStatus(str, Enum):
    BLOCKED = "BLOCKED"
    SIMULATED = "SIMULATED"
    APPROVED_SCENARIO = "APPROVED_SCENARIO"
    CAUSAL = "CAUSAL"


class CalibrationStatus(str, Enum):
    PRIOR_LED = "PRIOR_LED"
    PUBLICLY_ANCHORED = "PUBLICLY_ANCHORED"
    CLIENT_VALIDATED = "CLIENT_VALIDATED"
    EMPIRICALLY_CALIBRATED = "EMPIRICALLY_CALIBRATED"


class EventType(str, Enum):
    ELIGIBILITY_RECORDED = "EligibilityRecorded"
    RECOMMENDATION_ASSIGNED = "RecommendationAssigned"
    RECOMMENDATION_DISPLAYED = "RecommendationDisplayed"
    RECOMMENDATION_OPENED = "RecommendationOpened"
    RECOMMENDATION_DISMISSED = "RecommendationDismissed"
    BANKER_ACTION_RECORDED = "BankerActionRecorded"
    PIPELINE_MILESTONE_RECORDED = "PipelineMilestoneRecorded"
    OUTCOME_RECORDED = "OutcomeRecorded"
    EVIDENCE_APPROVED = "EvidenceApproved"
    ACCESS_DECISION_LOGGED = "AccessDecisionLogged"


class CuratedMetadata(StrictModel):
    business_key: str
    source_system_key: str
    event_time: datetime
    valid_from: datetime
    valid_to: Optional[datetime] = None
    ingestion_time: datetime = Field(default_factory=utc_now)
    source_hash: str = Field(min_length=16)
    transformation_version: str
    quality_status: QualityStatus = QualityStatus.VALID
    data_owner: str
    entitlement_domain: str

    @model_validator(mode="after")
    def temporal_order(self) -> "CuratedMetadata":
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be later than valid_from")
        return self


class Money(StrictModel):
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    source_unit: str = "unit"
    normalized_amount: Decimal
    normalized_currency: str = Field(default="ZAR", min_length=3, max_length=3)
    fx_policy_ref: Optional[str] = None

    @field_validator("currency", "normalized_currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class IntervalEstimate(StrictModel):
    lower: float = Field(ge=0)
    median: float = Field(ge=0)
    upper: float = Field(ge=0)
    nominal_coverage: float = Field(gt=0, lt=1)
    model_version: str
    as_of: date
    claim_class: ClaimClass

    @model_validator(mode="after")
    def ordered(self) -> "IntervalEstimate":
        if not self.lower <= self.median <= self.upper:
            raise ValueError("interval must satisfy lower <= median <= upper")
        return self


class ArtifactReference(StrictModel):
    model_version: str
    dataset_version: str
    prior_version: str
    transformation_version: str
    rate_card_version: Optional[str] = None
    prompt_version: Optional[str] = None
    schema_version: str = "v1"


class RecommendationEligibility(StrictModel):
    state: EligibilityState
    reason_codes: List[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def blocked_has_reason(self) -> "RecommendationEligibility":
        if self.state != EligibilityState.ALLOWED and not self.reason_codes:
            raise ValueError("non-allowed eligibility requires a reason code")
        return self


class EntitlementContext(StrictModel):
    user_id: str
    roles: List[str]
    team: str
    regions: List[str]
    client_ids: List[str]
    legal_entities: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    environment: DeploymentEnvironment


class EvidenceFact(StrictModel):
    fact_id: str
    entity_id: str
    concept: str
    source_value: Decimal
    currency: str
    unit: str
    sign: int = Field(ge=-1, le=1)
    period_start: date
    period_end: date
    source_date: date
    available_date: date
    source_title: str
    source_url: str
    document_hash: str = Field(min_length=16)
    page: int = Field(gt=0)
    bounding_box: Optional[List[float]] = None
    supporting_text: Optional[str] = None
    extraction_method: str
    extraction_model_version: Optional[str] = None
    tier: EvidenceTier
    approval_status: ApprovalStatus
    material: bool = False
    supersedes_fact_id: Optional[str] = None
    metadata: CuratedMetadata

    @model_validator(mode="after")
    def point_in_time_coherence(self) -> "EvidenceFact":
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        if self.available_date < self.period_end:
            raise ValueError("available_date cannot precede the reported period end")
        return self


class CalibrationObservation(StrictModel):
    observation_id: str
    entity_id: str
    product: str
    sector: str
    measured_share: float = Field(gt=0, lt=1)
    total_wallet: float = Field(gt=0)
    tier: EvidenceTier
    selection_weight: float = Field(gt=0)
    as_of: date
    metadata: CuratedMetadata


class RateCard(StrictModel):
    rate_card_id: str
    version: str
    product: str
    revenue_driver: str
    gross_price_bps: Decimal
    client_discount_bps: Decimal = Decimal("0")
    ftp_bps: Decimal = Decimal("0")
    liquidity_bps: Decimal = Decimal("0")
    expected_loss_bps: Decimal = Decimal("0")
    capital_bps: Decimal = Decimal("0")
    hedging_bps: Decimal = Decimal("0")
    execution_bps: Decimal = Decimal("0")
    servicing_bps: Decimal = Decimal("0")
    operating_cost_bps: Decimal = Decimal("0")
    tax_bps: Decimal = Decimal("0")
    acquisition_cost: Decimal = Decimal("0")
    approved_hurdle_bps: Decimal = Decimal("0")
    currency: str = "ZAR"
    effective_from: date
    effective_to: date
    approval_status: ApprovalStatus
    reconciliation_status: str
    synthetic: bool
    owner: str
    metadata: CuratedMetadata

    @model_validator(mode="after")
    def effective_dates(self) -> "RateCard":
        if self.effective_to < self.effective_from:
            raise ValueError("effective_to must not precede effective_from")
        return self


class CommercialResult(StrictModel):
    status: CommercialStatus
    observed_contribution: Optional[Money] = None
    contestable_scenario_contribution: Optional[Money] = None
    causal_expected_incremental_value: Optional[Money] = None
    net_unit_contribution_bps: Optional[float] = None
    target_share: Optional[float] = None
    watermark: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    rate_card_ref: Optional[str] = None


class TimingPrediction(StrictModel):
    event_name: str
    probability_30d: float = Field(ge=0, le=1)
    probability_60d: float = Field(ge=0, le=1)
    probability_90d: float = Field(ge=0, le=1)
    method: str
    calibration_status: str
    as_of: date

    @model_validator(mode="after")
    def monotone_horizons(self) -> "TimingPrediction":
        if not self.probability_30d <= self.probability_60d <= self.probability_90d:
            raise ValueError("event probability must be monotone across horizons")
        return self


class WalletEstimate(StrictModel):
    opportunity_id: str
    entity_id: str
    product: str
    sector: str
    observed_activity: Money
    identification_bounds: IntervalEstimate
    posterior_wallet: IntervalEstimate
    share_interval: IntervalEstimate
    share_claim: ClaimClass
    evidence_tier: EvidenceTier
    calibration_status: CalibrationStatus
    diagnostics: Dict[str, Any]
    artifacts: ArtifactReference


class OpportunityView(StrictModel):
    opportunity_id: str
    entity_id: str
    entity_name: str
    sector: str
    product: str
    as_of: date
    observed_activity: Money
    identification_bounds: IntervalEstimate
    posterior_wallet: IntervalEstimate
    share_interval: IntervalEstimate
    share_claim: ClaimClass
    evidence_tier: EvidenceTier
    calibration_status: CalibrationStatus
    freshness_days: int = Field(ge=0)
    timing: TimingPrediction
    commercial: CommercialResult
    eligibility: RecommendationEligibility
    rank: Optional[int] = None
    rank_probability: Optional[float] = Field(default=None, ge=0, le=1)
    evidence_fact_ids: List[str] = Field(default_factory=list)
    artifacts: ArtifactReference


class EventEnvelope(StrictModel):
    event_id: str
    event_type: EventType
    schema_version: str = "1.0.0"
    occurred_at: datetime = Field(default_factory=utc_now)
    entity_id: Optional[str] = None
    product: Optional[str] = None
    recommendation_id: Optional[str] = None
    rm_id: Optional[str] = None
    team_id: Optional[str] = None
    as_of: Optional[date] = None
    assignment_arm: Optional[str] = None
    assignment_probability: Optional[float] = Field(default=None, gt=0, le=1)
    evidence_tier: Optional[EvidenceTier] = None
    rank: Optional[int] = None
    reason_codes: List[str] = Field(default_factory=list)
    artifacts: Optional[ArtifactReference] = None
    entitlement_context: Optional[EntitlementContext] = None
    censor_date: Optional[date] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class StartStopInterval(StrictModel):
    opportunity_id: str
    entity_id: str
    product: str
    start_at: datetime
    stop_at: datetime
    event_code: Optional[str] = None
    censored: bool
    covariates: Dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ordered_times(self) -> "StartStopInterval":
        if self.stop_at <= self.start_at:
            raise ValueError("stop_at must be later than start_at")
        return self


class AccessDecision(StrictModel):
    allowed: bool
    action: str
    resource_type: str
    resource_id: str
    reason_codes: List[str]
    evaluated_at: datetime = Field(default_factory=utc_now)


class ReleaseGateResult(StrictModel):
    gate_id: str
    passed: bool
    measured_value: Optional[float] = None
    threshold: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)
    blocking: bool = True


class ScenarioRequest(StrictModel):
    opportunity_id: str
    as_of: date
    target_share: float = Field(ge=0, le=1)
    capacity: Optional[float] = Field(default=None, gt=0)


class IngestionRecordRequest(StrictModel):
    record_id: str
    source_system: str
    contract_version: str
    event_time: datetime
    as_of: date
    source_hash: str = Field(min_length=64, max_length=64)
    required_fields: List[str] = Field(default_factory=list)
    payload: Dict[str, Any]


class TimingRequest(StrictModel):
    entity_id: str
    product: str
    as_of: date
    event_name: str
    seasonal_ratio: float = Field(gt=0)
    maturity_days: Optional[int] = Field(default=None, ge=0)
    recurrence: float = Field(default=0.5, ge=0, le=1)


class NarrativeRequest(StrictModel):
    opportunity_id: str
    as_of: date


class AccessEvaluationRequest(StrictModel):
    action: str
    resource_type: str
    resource_id: str
    client_id: Optional[str] = None
    product: Optional[str] = None
    sensitive_economics: bool = False


class InteractionRequest(StrictModel):
    interaction_type: EventType
    occurred_at: datetime = Field(default_factory=utc_now)
    reason_code: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class OutcomeRequest(StrictModel):
    recommendation_id: str
    entity_id: str
    product: str
    outcome_code: str
    outcome_at: datetime
    realised_revenue: Optional[Money] = None
    realised_contribution: Optional[Money] = None
    censor_date: Optional[date] = None


class PilotSessionRequest(StrictModel):
    task_ids: List[str] = Field(min_length=1, max_length=20)
    started_at: datetime = Field(default_factory=utc_now)
    consent_reference: str = Field(min_length=8)


class PilotFeedbackRequest(StrictModel):
    task_id: str
    completed: bool
    verification_seconds: int = Field(ge=0, le=7200)
    actionability: int = Field(ge=1, le=5)
    comprehension: int = Field(ge=1, le=5)
    omission_found: bool = False
    override: bool = False
    notes: str = Field(default="", max_length=2000)


class FactReviewRequest(StrictModel):
    reviewer_id: str
    reviewer_role: str
    decision: ApprovalStatus
    notes: str
    reviewed_at: datetime = Field(default_factory=utc_now)


class ExtractionCandidate(StrictModel):
    candidate_id: str
    entity_id: str
    concept: str
    source_value: Decimal
    currency: str
    unit: str
    sign: int = Field(ge=-1, le=1)
    period_start: date
    period_end: date
    source_date: date
    available_date: date
    source_title: str
    source_url: str
    document_hash: str = Field(min_length=16)
    page: int = Field(gt=0)
    bounding_box: List[float] = Field(min_length=4, max_length=4)
    supporting_text: str
    extraction_method: str
    extraction_model_version: str
    material: bool = False


PRODUCTS = (
    "Collections",
    "Payments",
    "Liquidity",
    "Cross-border FX",
    "Trade finance",
)
