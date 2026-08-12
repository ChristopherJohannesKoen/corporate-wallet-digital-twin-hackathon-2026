"""V3.1 Decision Twin contracts.

The principal analytical object moves from ``(client, product)`` to
``(client, stakeholder, business problem, solution bundle, engagement window)``.
V2/V3 contracts remain the governed substrate and are re-used unchanged, so
every V3.1 object still carries claim class, evidence tier, provenance and
point-in-time metadata.

Interpretation boundaries preserved from V2/V3:

* ``OBSERVED``       - measured in the bank's own books.
* ``IDENTIFIED_BOUND`` - a bound that holds without a probabilistic prior.
* ``POSTERIOR``      - a probability under a stated, testable assumption.
* ``SCENARIO``       - a governed what-if, not a calibrated probability.
* ``CAUSAL``         - withheld until a randomized trial closes.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from pydantic import Field, model_validator

from wallet_twin_v2.contracts import (
    ApprovalStatus,
    ArtifactReference,
    ClaimClass,
    CuratedMetadata,
    DataProvenanceClass,
    EvidenceTier,
    StrictModel,
)

from .taxonomy import (
    BankingSolution,
    BusinessClaimKind,
    BusinessProblem,
    BusinessTwinDomain,
    ClientValueStatus,
    ComponentStatus,
    ConversationAction,
    EligibilityDecision,
    FeasibilityGate,
    FundingRoute,
    GateStatus,
    MappingStrength,
    SolutionFamily,
    StakeholderRole,
)

V31_VERSION = "3.1.0"


def conversation_id(
    entity_id: str,
    stakeholder: StakeholderRole,
    problem: BusinessProblem,
    solutions: Sequence[BankingSolution],
    window_key: str,
    snapshot_version: str,
) -> str:
    """Stable hash of the five conversation coordinates plus snapshot version."""
    parts = "|".join(
        [
            entity_id,
            stakeholder.value,
            problem.value,
            "+".join(sorted(item.value for item in solutions)),
            window_key,
            snapshot_version,
        ]
    )
    return "conv:" + hashlib.sha256(parts.encode("utf-8")).hexdigest()[:24]


# ---------------------------------------------------------------------------
# Shared numeric primitives
# ---------------------------------------------------------------------------
class SignedInterval(StrictModel):
    """An interval that may be negative.

    Client and bank value can legitimately be negative (a cost-to-win exceeding
    contribution, or an FX position that moves against the client), so the V3
    non-negative ``AmountInterval`` is not reusable here.
    """

    lower: float
    median: float
    upper: float
    currency: str = "ZAR"
    unit: str = "ZAR"

    @model_validator(mode="after")
    def ordered(self) -> "SignedInterval":
        if not self.lower <= self.median <= self.upper:
            raise ValueError("interval must satisfy lower <= median <= upper")
        return self


class IndicatorValue(StrictModel):
    """A transparent, evidence-linked derived indicator."""

    indicator_id: str
    label: str
    formula: str
    interval: Optional[SignedInterval] = None
    unit: str
    inputs: Dict[str, float] = Field(default_factory=dict)
    evidence_claim_ids: List[str] = Field(default_factory=list)
    pending_evidence_claim_ids: List[str] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)
    status: ComponentStatus
    transformation_version: str
    claim_class: ClaimClass = ClaimClass.IDENTIFIED_BOUND

    @model_validator(mode="after")
    def unknown_has_no_value(self) -> "IndicatorValue":
        if self.status is ComponentStatus.UNKNOWN and self.interval is not None:
            raise ValueError("an UNKNOWN indicator must not carry a value")
        if self.status is ComponentStatus.SUPPORTED and self.interval is None:
            raise ValueError("a SUPPORTED indicator must carry a value")
        if self.missing_inputs and self.status is ComponentStatus.SUPPORTED:
            raise ValueError("SUPPORTED indicators cannot have missing inputs")
        if self.pending_evidence_claim_ids and self.status is ComponentStatus.SUPPORTED:
            raise ValueError(
                "an indicator resting on pending-review evidence is INFERRED, never "
                "SUPPORTED; only approved evidence can support a client-facing claim"
            )
        return self

    @property
    def governed(self) -> bool:
        """True when every input comes from approved evidence."""
        return (
            self.status is ComponentStatus.SUPPORTED
            and not self.pending_evidence_claim_ids
        )

    @property
    def available(self) -> bool:
        return self.interval is not None


# ---------------------------------------------------------------------------
# Typed business evidence
# ---------------------------------------------------------------------------
class BusinessEvidenceClaim(StrictModel):
    """Typed business evidence.

    ``EvidenceFact`` remains the numeric contract for wallet estimation. This
    contract carries the non-numeric business evidence V3.1 needs: categorical
    facts, textual strategy/risk claims, corporate-structure relationships,
    maturity windows and events.
    """

    claim_id: str
    entity_id: str
    domains: List[BusinessTwinDomain] = Field(min_length=1)
    kind: BusinessClaimKind
    concept: str
    # exactly one typed payload is populated for each kind
    money_value: Optional[float] = None
    currency: Optional[str] = None
    unit: Optional[str] = None
    ratio_value: Optional[float] = None
    count_value: Optional[int] = None
    date_value: Optional[date] = None
    maturity_window_start: Optional[date] = None
    maturity_window_end: Optional[date] = None
    categorical_value: Optional[str] = None
    text_value: Optional[str] = None
    relationship_subject: Optional[str] = None
    relationship_predicate: Optional[str] = None
    relationship_object: Optional[str] = None
    # provenance and point-in-time governance
    period_start: date
    period_end: date
    source_date: date
    available_date: date
    source_title: str
    source_url: str
    source_hash: str = Field(min_length=16)
    page: Optional[int] = Field(default=None, gt=0)
    bounding_box: Optional[List[float]] = None
    supporting_text: Optional[str] = None
    extraction_method: str
    extraction_model_version: Optional[str] = None
    tier: EvidenceTier
    claim_class: ClaimClass
    provenance: DataProvenanceClass
    approval_status: ApprovalStatus
    reviewer_id: Optional[str] = None
    reviewer_role: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    supersedes_claim_id: Optional[str] = None
    restatement_reason: Optional[str] = None
    material: bool = False
    critical_path: bool = False
    legacy_fact_id: Optional[str] = None
    metadata: CuratedMetadata

    @model_validator(mode="after")
    def point_in_time_and_payload(self) -> "BusinessEvidenceClaim":
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        if self.available_date < self.period_end:
            raise ValueError("available_date cannot precede the reported period end")
        if self.source_date > self.available_date:
            raise ValueError("source_date cannot postdate availability")
        payloads = {
            BusinessClaimKind.MONEY: self.money_value is not None,
            BusinessClaimKind.RATIO: self.ratio_value is not None,
            BusinessClaimKind.COUNT: self.count_value is not None,
            BusinessClaimKind.DATE_OR_MATURITY: self.date_value is not None
            or self.maturity_window_start is not None,
            BusinessClaimKind.CATEGORICAL: bool(self.categorical_value),
            BusinessClaimKind.TEXTUAL: bool(self.text_value),
            BusinessClaimKind.STRUCTURE_RELATIONSHIP: bool(
                self.relationship_subject
                and self.relationship_predicate
                and self.relationship_object
            ),
            BusinessClaimKind.EVENT_OR_PROJECT: bool(self.categorical_value)
            or self.date_value is not None,
        }
        if not payloads[self.kind]:
            raise ValueError(f"claim kind {self.kind.value} requires its typed payload")
        if self.kind is BusinessClaimKind.MONEY and not self.currency:
            raise ValueError("money claims require a currency")
        if (
            self.maturity_window_start is not None
            and self.maturity_window_end is not None
            and self.maturity_window_end < self.maturity_window_start
        ):
            raise ValueError("maturity window must not close before it opens")
        if self.approval_status is ApprovalStatus.APPROVED and not self.reviewer_id:
            raise ValueError("approved claims require reviewer lineage")
        return self

    @property
    def usable_for_client_facing_statement(self) -> bool:
        return self.approval_status is ApprovalStatus.APPROVED


class EvidenceGap(StrictModel):
    """An explicit record that a material domain has no supporting evidence."""

    gap_id: str
    entity_id: str
    domain: BusinessTwinDomain
    reason: str
    material: bool = True
    blocking_problems: List[BusinessProblem] = Field(default_factory=list)
    acquisition_route: str


# ---------------------------------------------------------------------------
# Business Model Twin
# ---------------------------------------------------------------------------
class BusinessTwinComponent(StrictModel):
    domain: BusinessTwinDomain
    label: str
    status: ComponentStatus
    facts: Dict[str, Any] = Field(default_factory=dict)
    evidence_claim_ids: List[str] = Field(default_factory=list)
    claim_class: ClaimClass
    evidence_tier: EvidenceTier
    materiality: float = Field(ge=0, le=1)
    freshness_days: Optional[int] = Field(default=None, ge=0)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    available_date: Optional[date] = None
    assumptions: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    indicators: List[IndicatorValue] = Field(default_factory=list)
    decision_impacts: Dict[str, List[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unknown_is_never_silently_zero(self) -> "BusinessTwinComponent":
        if self.status is ComponentStatus.UNKNOWN:
            if self.facts:
                raise ValueError(
                    "UNKNOWN components must stay empty; unknown is never defaulted"
                )
            if not self.missing_information:
                raise ValueError("UNKNOWN components must state what is missing")
        if self.status is ComponentStatus.SUPPORTED and not self.evidence_claim_ids:
            raise ValueError("SUPPORTED components require evidence claims")
        return self


class BusinessTwinSnapshot(StrictModel):
    snapshot_id: str
    entity_id: str
    entity_name: str
    sector: str
    as_of: date
    snapshot_version: str = V31_VERSION
    legal_entity_ids: List[str] = Field(default_factory=list)
    components: List[BusinessTwinComponent] = Field(min_length=12, max_length=12)
    evidence_gaps: List[EvidenceGap] = Field(default_factory=list)
    claim_count: int = Field(ge=0)
    approved_claim_count: int = Field(ge=0)
    supported_domain_count: int = Field(ge=0, le=12)
    watermark: str
    artifacts: ArtifactReference

    @model_validator(mode="after")
    def one_component_per_domain(self) -> "BusinessTwinSnapshot":
        domains = [component.domain for component in self.components]
        if len(set(domains)) != 12:
            raise ValueError("a Business Twin must carry exactly one of each domain")
        if self.approved_claim_count > self.claim_count:
            raise ValueError("approved claims cannot exceed total claims")
        return self

    def component(self, domain: BusinessTwinDomain) -> BusinessTwinComponent:
        for component in self.components:
            if component.domain is domain:
                return component
        raise KeyError(domain)


# ---------------------------------------------------------------------------
# Dynamic business knowledge graph
# ---------------------------------------------------------------------------
class GraphLayer(str, Enum):
    ATTRIBUTE = "ATTRIBUTE"
    EVENT = "EVENT"


class NodeType(str, Enum):
    CLIENT = "CLIENT"
    LEGAL_ENTITY = "LEGAL_ENTITY"
    SUBSIDIARY = "SUBSIDIARY"
    SPV = "SPV"
    PROJECT = "PROJECT"
    STAKEHOLDER_ROLE = "STAKEHOLDER_ROLE"
    COUNTRY = "COUNTRY"
    CURRENCY = "CURRENCY"
    COMMODITY = "COMMODITY"
    BUSINESS_MODEL_COMPONENT = "BUSINESS_MODEL_COMPONENT"
    RISK = "RISK"
    PROBLEM = "PROBLEM"
    EVENT = "EVENT"
    BANKING_SOLUTION = "BANKING_SOLUTION"
    CLIENT_VALUE_COMPONENT = "CLIENT_VALUE_COMPONENT"
    BANK_VALUE_COMPONENT = "BANK_VALUE_COMPONENT"
    EVIDENCE_CLAIM = "EVIDENCE_CLAIM"


class ReviewState(str, Enum):
    REVIEW_CANDIDATE = "REVIEW_CANDIDATE"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DETERMINISTIC = "DETERMINISTIC"


class GraphNode(StrictModel):
    node_id: str
    layer: GraphLayer
    node_type: NodeType
    label: str
    entity_id: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    available_date: Optional[date] = None
    claim_class: ClaimClass = ClaimClass.OBSERVED
    evidence_tier: EvidenceTier = EvidenceTier.E0
    review_state: ReviewState = ReviewState.DETERMINISTIC


class GraphEdge(StrictModel):
    edge_id: str
    layer: GraphLayer
    edge_type: str
    source: str
    target: str
    directed: bool = True
    weight: Optional[float] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    available_date: Optional[date] = None
    claim_class: ClaimClass
    evidence_tier: EvidenceTier
    approval_status: ApprovalStatus
    source_claim_ids: List[str] = Field(default_factory=list)
    source_fact_ids: List[str] = Field(default_factory=list)
    transformation_artifact: str
    confidence_semantics: str
    review_state: ReviewState

    @property
    def explainable(self) -> bool:
        """Only approved or explicitly scenario-labelled edges may be shown.

        An edge awaiting review is never explainable, whatever its claim class:
        labelling something SCENARIO does not substitute for the review that
        an extracted or resolved relationship still needs.
        """
        if self.review_state in (ReviewState.REVIEW_CANDIDATE, ReviewState.REJECTED):
            return False
        return (
            self.approval_status is ApprovalStatus.APPROVED
            or self.claim_class is ClaimClass.SCENARIO
        )


class ExplanationStep(StrictModel):
    step: str
    node_id: str
    label: str
    claim_class: ClaimClass
    evidence_claim_ids: List[str] = Field(default_factory=list)
    edge_id: Optional[str] = None


class ExplanationPath(StrictModel):
    """Event -> BusinessImpact -> Problem -> Stakeholder -> Solution -> ClientValue -> BankValue."""

    path_id: str
    entity_id: str
    steps: List[ExplanationStep] = Field(min_length=5)
    evidence_backed: bool
    unsupported_steps: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def evidence_backed_implies_support(self) -> "ExplanationPath":
        if self.evidence_backed and self.unsupported_steps:
            raise ValueError("an evidence-backed path cannot contain unsupported steps")
        return self


class BusinessGraphSnapshot(StrictModel):
    graph_id: str
    entity_id: str
    as_of: date
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    explanation_paths: List[ExplanationPath] = Field(default_factory=list)
    attribute_node_count: int = Field(ge=0)
    event_node_count: int = Field(ge=0)
    review_candidate_edges: int = Field(ge=0)
    identity_resolution_status: str
    measurement_status: str

    @model_validator(mode="after")
    def no_dangling_edges(self) -> "BusinessGraphSnapshot":
        known = {node.node_id for node in self.nodes}
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError(f"dangling edge: {edge.edge_id}")
        return self


class BusinessEvent(StrictModel):
    event_key: str
    entity_id: str
    event_type: str
    label: str
    event_date: date
    available_date: date
    horizon_days: Optional[int] = Field(default=None, ge=0)
    magnitude: Optional[SignedInterval] = None
    affected_domains: List[BusinessTwinDomain] = Field(default_factory=list)
    implied_problems: List[BusinessProblem] = Field(default_factory=list)
    evidence_claim_ids: List[str] = Field(default_factory=list)
    claim_class: ClaimClass
    evidence_tier: EvidenceTier
    review_state: ReviewState


class ChangeDigestItem(StrictModel):
    change_type: str
    subject: str
    before: Optional[str] = None
    after: Optional[str] = None
    materiality: float = Field(ge=0, le=1)
    evidence_claim_ids: List[str] = Field(default_factory=list)
    decision_impact: str


class ChangeDigest(StrictModel):
    digest_id: str
    entity_id: str
    since: date
    as_of: date
    items: List[ChangeDigestItem] = Field(default_factory=list)
    no_change_statement: Optional[str] = None

    @model_validator(mode="after")
    def empty_digest_is_explicit(self) -> "ChangeDigest":
        if self.since > self.as_of:
            raise ValueError("since must not exceed as_of")
        if not self.items and not self.no_change_statement:
            raise ValueError("an empty digest must state that nothing changed")
        return self


# ---------------------------------------------------------------------------
# Problem, stakeholder, solution
# ---------------------------------------------------------------------------
class ProblemEvidenceItem(StrictModel):
    reason_code: str
    statement: str
    claim_class: ClaimClass
    evidence_claim_ids: List[str] = Field(default_factory=list)
    bank_observed: bool = False
    weight: float = Field(ge=0, le=1)


class ProblemHypothesis(StrictModel):
    problem_id: str
    entity_id: str
    problem: BusinessProblem
    label: str
    as_of: date
    identified: bool
    intensity: SignedInterval
    intensity_unit: str
    supporting_evidence: List[ProblemEvidenceItem] = Field(default_factory=list)
    disconfirming_evidence: List[ProblemEvidenceItem] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)
    probability: Optional[float] = Field(default=None, ge=0, le=1)
    claim_class: ClaimClass
    calibration_status: str
    critical_signal_is_governed: bool
    commercially_eligible: bool
    detector_version: str
    affected_domains: List[BusinessTwinDomain] = Field(default_factory=list)

    @model_validator(mode="after")
    def eligibility_requires_governed_signal(self) -> "ProblemHypothesis":
        if self.commercially_eligible and not self.critical_signal_is_governed:
            raise ValueError(
                "commercial eligibility requires a bank-observed, approved E1 or "
                "approved E2 critical signal"
            )
        if self.identified and not self.supporting_evidence:
            raise ValueError("an identified problem requires supporting evidence")
        return self


class StakeholderResolution(StrictModel):
    resolution_id: str
    entity_id: str
    problem: BusinessProblem
    primary_role: StakeholderRole
    secondary_roles: List[StakeholderRole] = Field(default_factory=list)
    responsibility_weight: float = Field(ge=0, le=1)
    weight_semantics: str
    ownership_rationale: str
    supporting_solutions: List[BankingSolution] = Field(default_factory=list)
    requires_rm_confirmation: bool = True
    attestation_status: str = "NOT_ATTESTED"
    named_contact_status: str = "NAMED_CONTACT_UNAVAILABLE_IN_DEMONSTRATION"
    matrix_version: str


class SolutionEstimate(StrictModel):
    """One (client, solution) projection.  320 per snapshot for 20x16."""

    estimate_id: str
    entity_id: str
    solution: BankingSolution
    solution_label: str
    family: SolutionFamily
    principal_quantity: str
    as_of: date
    available: bool
    unavailable_reason: Optional[str] = None
    identification_bounds: Optional[SignedInterval] = None
    #: How the identification bound relates to the amount interval.  The two are
    #: not always the same quantity: for the five legacy products the bound is a
    #: public-anchor range on total addressable activity while the amount is the
    #: shrunk posterior wallet, so the amount can legitimately sit below the
    #: bound.  Stating the relationship is safer than assuming containment.
    bounds_semantics: str = "AMOUNT_WITHIN_BOUNDS"
    amount_interval: Optional[SignedInterval] = None
    need_probability: Optional[float] = Field(default=None, ge=0, le=1)
    need_semantics: str
    timing_probability_30d: Optional[float] = Field(default=None, ge=0, le=1)
    timing_probability_60d: Optional[float] = Field(default=None, ge=0, le=1)
    timing_probability_90d: Optional[float] = Field(default=None, ge=0, le=1)
    claim_class: ClaimClass
    evidence_tier: EvidenceTier
    calibration_status: str
    model_status: str
    evidence_claim_ids: List[str] = Field(default_factory=list)
    legacy_opportunity_id: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    estimator_version: str

    @model_validator(mode="after")
    def fail_closed(self) -> "SolutionEstimate":
        if not self.available:
            if not self.unavailable_reason:
                raise ValueError("an unavailable estimate must state why")
            if self.amount_interval is not None or self.need_probability is not None:
                raise ValueError("an unavailable estimate must not carry quantities")
        else:
            if self.amount_interval is None:
                raise ValueError("an available estimate requires an amount interval")
            if self.amount_interval.lower < 0:
                raise ValueError(
                    "a wallet, exposure, facility or flow quantity cannot be negative"
                )
            if self.identification_bounds is not None:
                bounds = self.identification_bounds
                if bounds.lower < 0:
                    raise ValueError("an identification bound cannot start below zero")
                inside = (
                    bounds.lower - 1e-6
                    <= self.amount_interval.median
                    <= bounds.upper + 1e-6
                )
                if self.bounds_semantics == "AMOUNT_WITHIN_BOUNDS" and not inside:
                    raise ValueError(
                        "amount interval median sits outside its identification bounds; "
                        "declare the relationship in bounds_semantics rather than "
                        "silently allowing it"
                    )
        horizons = (
            self.timing_probability_30d,
            self.timing_probability_60d,
            self.timing_probability_90d,
        )
        if all(item is not None for item in horizons):
            if not horizons[0] <= horizons[1] <= horizons[2]:
                raise ValueError("timing probabilities must be monotone")
        return self


class SolutionBundle(StrictModel):
    bundle_id: str
    primary: BankingSolution
    supporting: List[BankingSolution] = Field(default_factory=list, max_length=2)
    strengths: Dict[str, MappingStrength] = Field(default_factory=dict)
    prerequisites: List[str] = Field(default_factory=list)
    matrix_version: str

    @model_validator(mode="after")
    def bundle_shape(self) -> "SolutionBundle":
        if self.primary in self.supporting:
            raise ValueError("the primary solution cannot repeat as supporting")
        if len(set(self.supporting)) != len(self.supporting):
            raise ValueError("supporting solutions must be distinct")
        return self

    @property
    def solutions(self) -> List[BankingSolution]:
        return [self.primary, *self.supporting]


# ---------------------------------------------------------------------------
# Timing, value, feasibility
# ---------------------------------------------------------------------------
class EngagementWindow(StrictModel):
    window_id: str
    trigger_name: str
    trigger_supported: bool
    trigger_event_key: Optional[str] = None
    trigger_date: Optional[date] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    lead_time_days: int = Field(ge=0)
    probability_30d: float = Field(ge=0, le=1)
    probability_60d: float = Field(ge=0, le=1)
    probability_90d: float = Field(ge=0, le=1)
    why_now: str
    claim_class: ClaimClass
    calibration_status: str

    @model_validator(mode="after")
    def monotone_and_honest(self) -> "EngagementWindow":
        if not self.probability_30d <= self.probability_60d <= self.probability_90d:
            raise ValueError("horizon probabilities must be monotone")
        if not self.trigger_supported and self.trigger_date is not None:
            raise ValueError("an unsupported trigger cannot carry a trigger date")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("window end must not precede window start")
        return self


class ClientValueComponent(StrictModel):
    component_id: str
    label: str
    status: ClientValueStatus
    formula: Optional[str] = None
    interval: Optional[SignedInterval] = None
    dimension: str
    qualitative_statement: Optional[str] = None
    assumptions: List[str] = Field(default_factory=list)
    evidence_claim_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_matches_payload(self) -> "ClientValueComponent":
        if self.status in (ClientValueStatus.MONETISED, ClientValueStatus.PROXY):
            if self.interval is None:
                raise ValueError("monetised/proxy components require an interval")
            if not self.formula:
                raise ValueError("monetised/proxy components require a formula")
        else:
            if self.interval is not None:
                raise ValueError(
                    "qualitative or unavailable client value must never be silently "
                    "converted to ZAR"
                )
            if not self.qualitative_statement:
                raise ValueError("non-monetised components require a statement")
        return self


class ClientValue(StrictModel):
    entity_id: str
    monetised_total: Optional[SignedInterval] = None
    components: List[ClientValueComponent] = Field(default_factory=list)
    non_monetised_dimensions: List[str] = Field(default_factory=list)
    risk_reduction_statement: Optional[str] = None
    guaranteed_saving_claimed: bool = False
    assumptions: List[str] = Field(default_factory=list)
    claim_class: ClaimClass = ClaimClass.SCENARIO
    watermark: str

    @model_validator(mode="after")
    def risk_reduction_is_not_pnl(self) -> "ClientValue":
        if self.guaranteed_saving_claimed:
            raise ValueError(
                "V3.1 never claims a guaranteed P&L saving; risk reduction is "
                "reported separately from monetised benefit"
            )
        return self


class BankValueComponent(StrictModel):
    component_id: str
    label: str
    amount: float
    sign: int = Field(ge=-1, le=1)
    basis: str
    rate_card_ref: Optional[str] = None
    approved: bool = False


class BankValue(StrictModel):
    entity_id: str
    status: str
    direct_contribution: Optional[SignedInterval] = None
    components: List[BankValueComponent] = Field(default_factory=list)
    cost_to_win: Optional[SignedInterval] = None
    coverage_hours: Optional[float] = Field(default=None, ge=0)
    onboarding_effort_days: Optional[float] = Field(default=None, ge=0)
    credit_legal_effort_days: Optional[float] = Field(default=None, ge=0)
    systems_integration_days: Optional[float] = Field(default=None, ge=0)
    relationship_value_3y: Optional[SignedInterval] = None
    relationship_value_semantics: str
    causal_incremental_value: None = None
    causal_status: str = "CAUSAL_INCREMENTAL_VALUE_WITHHELD"
    double_count_guard: str
    reason_codes: List[str] = Field(default_factory=list)
    rate_card_versions: List[str] = Field(default_factory=list)
    watermark: str

    @model_validator(mode="after")
    def causal_stays_null(self) -> "BankValue":
        if self.causal_incremental_value is not None:
            raise ValueError("causal incremental value must remain null until trial")
        if self.status == "BLOCKED" and self.direct_contribution is not None:
            raise ValueError("blocked bank economics must not publish a contribution")
        return self


class GateResult(StrictModel):
    gate: FeasibilityGate
    status: GateStatus
    required: bool
    reason: str
    required_confirmation: Optional[str] = None
    attested_by_role: Optional[str] = None
    attested_at: Optional[datetime] = None


class FeasibilityAssessment(StrictModel):
    assessment_id: str
    entity_id: str
    bundle_id: str
    gates: List[GateResult] = Field(min_length=6, max_length=6)
    blocked: bool
    material_unknowns: List[FeasibilityGate] = Field(default_factory=list)
    permitted_action: ConversationAction
    friction_score: float = Field(ge=0, le=1)
    risk_score: float = Field(ge=0, le=1)
    feasibility_multiplier: float = Field(ge=0, le=1)
    required_confirmations: List[str] = Field(default_factory=list)
    banker_confirmation_notice: str
    policy_version: str

    @model_validator(mode="after")
    def gate_logic(self) -> "FeasibilityAssessment":
        seen = {result.gate for result in self.gates}
        if len(seen) != 6:
            raise ValueError("all six feasibility gates must be assessed")
        failed = [item for item in self.gates if item.status is GateStatus.FAIL]
        if failed and not self.blocked:
            raise ValueError("a failed gate must block the solution bundle")
        if self.blocked and self.permitted_action is ConversationAction.PRODUCT_PROPOSAL:
            raise ValueError("a blocked bundle cannot support a product proposal")
        if (
            self.material_unknowns
            and self.permitted_action is ConversationAction.PRODUCT_PROPOSAL
        ):
            raise ValueError(
                "material unknown feasibility converts the action into discovery"
            )
        return self


# ---------------------------------------------------------------------------
# Funding-route intelligence
# ---------------------------------------------------------------------------
class FundingRouteScore(StrictModel):
    route: FundingRoute
    probability: float = Field(ge=0, le=1)
    score: float
    drivers: Dict[str, float] = Field(default_factory=dict)


class FundingRouteProjection(StrictModel):
    projection_id: str
    entity_id: str
    as_of: date
    requirement: Optional[SignedInterval] = None
    requirement_status: ComponentStatus
    routes: List[FundingRouteScore] = Field(min_length=6, max_length=6)
    inputs: Dict[str, float] = Field(default_factory=dict)
    missing_inputs: List[str] = Field(default_factory=list)
    method: str
    model_status: str
    challenger_status: str
    claim_class: ClaimClass = ClaimClass.SCENARIO
    evidence_claim_ids: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def probabilities_sum_to_one(self) -> "FundingRouteProjection":
        total = sum(item.probability for item in self.routes)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"funding-route probabilities must sum to one, got {total}")
        if len({item.route for item in self.routes}) != 6:
            raise ValueError("every funding route must be scored")
        return self


# ---------------------------------------------------------------------------
# Decision engineering
# ---------------------------------------------------------------------------
class ParetoStatus(StrictModel):
    client_frontier_member: bool
    portfolio_frontier_member: bool
    client_frontier_probability: float = Field(ge=0, le=1)
    portfolio_frontier_probability: float = Field(ge=0, le=1)
    dominated_by: List[str] = Field(default_factory=list)
    dominance_threshold: float = Field(ge=0, le=1)
    scenario_draws: int = Field(ge=32)
    policy_version: str


class PolicyRank(StrictModel):
    weekly_rank: Optional[int] = Field(default=None, ge=1)
    selected: bool
    benefit: float
    adjusted_benefit_expected: float
    adjusted_benefit_cvar10: float
    objective_contribution: float
    selection_stability: float = Field(ge=0, le=1)
    reasons: List[str] = Field(default_factory=list)
    weights_version: str
    solver_status: str


class AnswerState(StrictModel):
    state_id: str
    label: str
    probability: float = Field(ge=0, le=1)
    implied_shift: float


class InformationQuestion(StrictModel):
    question_id: str
    entity_id: str
    conversation_id: str
    variable_id: str
    variable_label: str
    question_text: str
    stakeholder_role: StakeholderRole
    answer_states: List[AnswerState] = Field(min_length=2)
    expected_utility_with_answer: float
    expected_utility_without_answer: float
    cost_zar: float = Field(ge=0)
    delay_penalty_zar: float = Field(ge=0)
    net_voi_zar: float
    can_change_rank: bool
    can_change_bundle: bool
    can_change_feasibility: bool
    can_change_abstention: bool
    scenario_draws: int = Field(ge=32)
    selected: bool
    policy_version: str

    @model_validator(mode="after")
    def only_decision_relevant_questions(self) -> "InformationQuestion":
        total = sum(item.probability for item in self.answer_states)
        if abs(total - 1.0) > 1e-6:
            raise ValueError("answer-state probabilities must sum to one")
        if self.selected:
            if self.net_voi_zar <= 0:
                raise ValueError("only positive-net-VOI questions may be selected")
            if not any(
                (
                    self.can_change_rank,
                    self.can_change_bundle,
                    self.can_change_feasibility,
                    self.can_change_abstention,
                )
            ):
                raise ValueError(
                    "a question with no possible decision effect must be rejected"
                )
        return self


class ClientAnswer(StrictModel):
    answer_id: str
    question_id: str
    entity_id: str
    respondent_role: StakeholderRole
    respondent_type: str
    answer_state_id: str
    free_text: Optional[str] = None
    consent_reference: str = Field(min_length=8)
    scope: str
    valid_from: date
    valid_to: Optional[date] = None
    source: str
    submitted_at: datetime
    approval_status: ApprovalStatus = ApprovalStatus.PENDING_REVIEW
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    resulting_claim_id: Optional[str] = None
    tier: EvidenceTier = EvidenceTier.E2

    @model_validator(mode="after")
    def pending_answers_cannot_be_promoted(self) -> "ClientAnswer":
        if (
            self.approval_status is not ApprovalStatus.APPROVED
            and self.resulting_claim_id is not None
        ):
            raise ValueError(
                "a pending or rejected answer must not create an approved claim"
            )
        if self.approval_status is ApprovalStatus.APPROVED and not self.reviewer_id:
            raise ValueError("approved answers require reviewer lineage")
        return self


class ConversationBrief(StrictModel):
    brief_id: str
    conversation_id: str
    headline: str
    why: str
    how: str
    what: str
    client_value_statement: str
    bank_value_statement: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    feasibility_statement: str
    primary_question: Optional[str] = None
    prohibited_claims: List[str] = Field(default_factory=list)
    abstentions: List[str] = Field(default_factory=list)
    compiler: str
    provider_used: bool = False
    fallback_available: bool = True


class ConversationCandidate(StrictModel):
    """The canonical V3.1 decision object."""

    conversation_id: str
    entity_id: str
    entity_name: str
    sector: str
    legal_entity_ids: List[str] = Field(default_factory=list)
    as_of: date
    week_start: date
    stakeholder: StakeholderResolution
    problem: ProblemHypothesis
    solution_bundle: SolutionBundle
    solution_estimates: List[SolutionEstimate] = Field(min_length=1, max_length=3)
    engagement_window: EngagementWindow
    client_value: ClientValue
    bank_value: BankValue
    risk_and_feasibility: FeasibilityAssessment
    pareto_status: ParetoStatus
    policy_rank: PolicyRank
    next_best_question: Optional[InformationQuestion] = None
    explanation_path: ExplanationPath
    why: str
    how: str
    what: str
    action: ConversationAction
    eligibility: EligibilityDecision
    eligibility_reasons: List[str] = Field(default_factory=list)
    artifacts: ArtifactReference
    claim_classes: List[ClaimClass] = Field(default_factory=list)
    provenance: List[DataProvenanceClass] = Field(default_factory=list)
    evidence_tiers: List[EvidenceTier] = Field(default_factory=list)
    evidence_claim_ids: List[str] = Field(default_factory=list)
    watermark: str

    @model_validator(mode="after")
    def action_and_eligibility_agree(self) -> "ConversationCandidate":
        if self.eligibility is EligibilityDecision.BLOCKED and not self.eligibility_reasons:
            raise ValueError("a blocked conversation requires reasons")
        if (
            self.action is ConversationAction.PRODUCT_PROPOSAL
            and self.eligibility is not EligibilityDecision.ELIGIBLE
        ):
            raise ValueError("only an eligible conversation may propose a product")
        if (
            self.eligibility is EligibilityDecision.ELIGIBLE
            and not self.problem.commercially_eligible
        ):
            raise ValueError(
                "commercial eligibility requires a governed critical problem signal"
            )
        if self.solution_bundle.primary != self.solution_estimates[0].solution:
            raise ValueError("the first estimate must be the primary solution")
        return self


class CoveragePlanEntry(StrictModel):
    rank: int = Field(ge=1)
    conversation_id: str
    entity_id: str
    entity_name: str
    stakeholder_role: StakeholderRole
    problem: BusinessProblem
    problem_label: str
    primary_solution: BankingSolution
    solution_label: str
    family: SolutionFamily
    action: ConversationAction
    why_now: str
    client_value_median: Optional[float] = None
    client_value_status: ClientValueStatus
    bank_value_median: Optional[float] = None
    bank_value_status: str
    selection_stability: float = Field(ge=0, le=1)
    frontier_state: str
    eligibility: EligibilityDecision
    adjusted_benefit_expected: float
    adjusted_benefit_cvar10: float


class CoveragePlan(StrictModel):
    plan_id: str
    as_of: date
    week_start: date
    capacity: int = Field(gt=0)
    entries: List[CoveragePlanEntry] = Field(default_factory=list)
    objective_value: float
    expected_adjusted_benefit: float
    cvar10_adjusted_benefit: float
    solver: str
    solver_status: str
    degraded_fallback: bool = False
    constraints: Dict[str, int] = Field(default_factory=dict)
    constraint_report: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    scenario_draws: int = Field(ge=32)
    weights_version: str
    above_the_fold: int = 5
    commercial_status: str = "REPRESENTATIVE_SCENARIO_NOT_BANK_APPROVED"
    causal_status: str = "CAUSAL_INCREMENTAL_VALUE_WITHHELD"

    @model_validator(mode="after")
    def within_capacity(self) -> "CoveragePlan":
        if len(self.entries) > self.capacity:
            raise ValueError("the weekly plan cannot exceed RM capacity")
        ranks = [entry.rank for entry in self.entries]
        if ranks != sorted(ranks) or len(set(ranks)) != len(ranks):
            raise ValueError("coverage-plan ranks must be unique and ordered")
        if self.degraded_fallback and self.solver_status != "DEGRADED_FALLBACK":
            raise ValueError("a greedy fallback must be labelled DEGRADED_FALLBACK")
        return self
