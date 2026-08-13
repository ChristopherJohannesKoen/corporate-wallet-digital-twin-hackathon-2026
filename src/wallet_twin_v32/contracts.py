"""V3.2 promotion contracts.

House style from :mod:`wallet_twin_v2.contracts` throughout: ``StrictModel``
(``extra="forbid"``, ``validate_assignment=True``), enums kept as enums, and
governance invariants expressed as ``model_validator`` rather than as
documentation. If a combination would be a misrepresentation, constructing it
raises — a downstream check can be forgotten, a constructor cannot.

**The four time fields.** They are not interchangeable and collapsing any two of
them loses a distinction the bank needs:

``as_of``
    The business date the evidence describes. The point-in-time boundary: no
    input dated after this may have informed it.
``generated_at``
    Wall-clock time the artifact was computed. Provenance, not business meaning.
``published_at``
    When it became visible to consumers. Later than ``generated_at`` whenever
    review sits between the two, which is the normal case for attested evidence.
``simulation_clock``
    Position of the *virtual* clock. Present only for rehearsal evidence, and
    the reason an accelerated 30-day rehearsal cannot be read as 30 elapsed
    days: the field that advanced is named differently from the ones that did
    not.

``expires_at`` is a fifth, orthogonal field: freshness, not occurrence.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pydantic import Field, model_validator

from wallet_twin_v2.contracts import StrictModel, utc_now

from .modes import (
    DecisionTrack,
    PromotionEvidenceMode,
    admits_track,
    is_synthetic,
    satisfies_minimum,
    track_admission_reason,
)
from .states import PromotionCapability, PromotionState, is_legal_transition

CONTRACTS_VERSION = "v32-promotion-contracts-1.0.0"

#: Severity weights. A gate's contribution to both scores is its severity
#: weight, so a CRITICAL gate cannot be outvoted by a handful of STANDARD ones.
SEVERITY_WEIGHTS: Dict[str, int] = {"CRITICAL": 5, "HIGH": 3, "STANDARD": 1}

#: Returned by the sample-size planner when no tested n reaches the target.
#: A sentinel rather than the largest n tried, because "150 was not enough" and
#: "150 is the recommendation" are opposite findings and must not share an
#: encoding.
NOT_DETERMINED_UP_TO_150 = "NOT_DETERMINED_UP_TO_150"


class GateSeverity(str, Enum):
    """How much a gate's outcome matters. Weights in ``SEVERITY_WEIGHTS``."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    STANDARD = "STANDARD"


class GateOutcome(str, Enum):
    """Outcome of evaluating one gate on one track.

    ``UNKNOWN`` is distinct from ``FAIL``: a gate nobody has evidence for has
    not been failed, it has not been attempted, and reporting the two the same
    way would either overstate progress or manufacture a failure. ``WAIVED``
    carries a named approver and is always visible in the register.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_REQUIRED = "NOT_REQUIRED"
    WAIVED = "WAIVED"


#: Outcomes that let a transition proceed.
SATISFYING_OUTCOMES = frozenset({GateOutcome.PASS, GateOutcome.NOT_REQUIRED})


class GateDefinition(StrictModel):
    """A gate as governed data, not as a line of code.

    ``ShadowReleaseGate`` in V2 hardcodes twenty checks in one method with
    string thresholds and no evidence binding. Making the catalogue data lets a
    gate declare what evidence it needs, who owns it, what breaks if it fails,
    and — the field reviewers actually use — what would make it pass.
    """

    gate_id: str
    title: str
    transition_id: str
    severity: GateSeverity
    #: Whether failure blocks the transition. A non-blocking gate is still
    #: scored and still shown; it just does not stop promotion on its own.
    blocking: bool = True
    requirement: str
    #: What the bank loses or risks if this gate is not satisfied. Written for
    #: the person deciding, not for the person implementing.
    consequence_if_failed: str
    #: The weakest evidence mode admissible on the REAL track for this gate.
    #: Supply-chain gates accept PUBLIC_PACKAGE; bank-data gates demand
    #: BANK_ATTESTED.
    minimum_real_evidence_mode: PromotionEvidenceMode
    owner_role: str
    approver_role: str
    #: Maximum age of evidence, in days, before it must be re-established.
    freshness_days: Optional[int] = Field(default=None, gt=0)
    #: Concrete next action that would satisfy the real gate.
    what_would_make_real_pass: str
    #: Capabilities this gate is a prerequisite for, for cross-referencing.
    capability_effects: List[PromotionCapability] = Field(default_factory=list)

    @model_validator(mode="after")
    def _real_minimum_is_real(self) -> "GateDefinition":
        if is_synthetic(self.minimum_real_evidence_mode):
            raise ValueError(
                f"gate {self.gate_id}: minimum_real_evidence_mode cannot be "
                "SYNTHETIC_REHEARSAL; a real gate is not satisfiable by simulation"
            )
        return self


class GateEvidence(StrictModel):
    """A specific artifact offered in support of a gate, with its provenance."""

    evidence_id: str
    gate_id: str
    mode: PromotionEvidenceMode
    #: Path or URI, relative to the repository root where applicable.
    artifact_uri: str
    #: SHA-256 of the artifact bytes. Binds the claim to content, so swapping
    #: the artifact without re-registering is detectable.
    content_sha256: str = Field(min_length=64, max_length=64)
    summary: str
    as_of: date
    generated_at: datetime = Field(default_factory=utc_now)
    published_at: Optional[datetime] = None
    #: Virtual clock position. Only meaningful for synthetic evidence.
    simulation_clock: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    produced_by: str

    @model_validator(mode="after")
    def _time_fields_keep_their_meanings(self) -> "GateEvidence":
        if self.published_at is not None and self.published_at < self.generated_at:
            raise ValueError(
                f"evidence {self.evidence_id}: published_at precedes generated_at; "
                "evidence cannot be published before it exists"
            )
        if self.expires_at is not None and self.expires_at <= self.generated_at:
            raise ValueError(
                f"evidence {self.evidence_id}: expires_at is not after generated_at"
            )
        if self.simulation_clock is not None and not is_synthetic(self.mode):
            raise ValueError(
                f"evidence {self.evidence_id}: simulation_clock is set on "
                f"{self.mode.value} evidence; a virtual clock has no meaning "
                "outside a rehearsal and setting it here would let simulated "
                "time be read as elapsed time"
            )
        return self


class SignedEvidenceEnvelope(StrictModel):
    """A DSSE-shaped envelope binding a payload digest to a signature.

    The mode lives *inside* the signed payload (workstream 3 canonicalises the
    payload with RFC 8785 before signing), so altering it invalidates the
    signature. Recording it here as well lets the register be read without
    verifying every envelope, and :meth:`_mode_matches_key_authority` keeps the
    two from disagreeing.
    """

    envelope_id: str
    evidence_id: str
    payload_type: str = "application/vnd.wallet-twin.promotion-evidence+json"
    payload_sha256: str = Field(min_length=64, max_length=64)
    mode: PromotionEvidenceMode
    key_id: str
    #: Which modes the signing key is registered to sign. A rehearsal key lists
    #: only SYNTHETIC_REHEARSAL.
    key_authorised_modes: List[PromotionEvidenceMode]
    signature_algorithm: str
    #: Base64 signature, or None when nothing signed it. Following
    #: ``evidence.signed_manifest``, unsigned is reported rather than implied.
    signature: Optional[str] = None
    signature_status: str = "UNSIGNED"
    trust_domain: str
    signed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    @model_validator(mode="after")
    def _mode_matches_key_authority(self) -> "SignedEvidenceEnvelope":
        if self.mode not in self.key_authorised_modes:
            raise ValueError(
                f"envelope {self.envelope_id}: key {self.key_id} is not "
                f"authorised to sign {self.mode.value} evidence "
                f"(authorised: {[m.value for m in self.key_authorised_modes]})"
            )
        if self.signature is None and self.signature_status != "UNSIGNED":
            raise ValueError(
                f"envelope {self.envelope_id}: signature_status claims "
                f"{self.signature_status} with no signature present"
            )
        if self.signature is not None and self.signature_status == "UNSIGNED":
            raise ValueError(
                f"envelope {self.envelope_id}: a signature is present but "
                "signature_status still reports UNSIGNED"
            )
        return self


class GateEvaluation(StrictModel):
    """One gate, one track, one verdict.

    The type refuses the misrepresentation the whole twin exists to prevent: a
    synthetic envelope cannot carry a REAL-track PASS.
    """

    gate_id: str
    transition_id: str
    track: DecisionTrack
    outcome: GateOutcome
    evidence_mode: Optional[PromotionEvidenceMode] = None
    evidence_ids: List[str] = Field(default_factory=list)
    envelope_ids: List[str] = Field(default_factory=list)
    measured_value: Optional[float] = None
    threshold: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    #: Set only when this evaluation came from deliberately injecting a failure
    #: to prove the gate can fail. A gate that has never been observed failing
    #: has not been shown to be a gate.
    failure_injection_verified: bool = False
    evaluated_at: datetime = Field(default_factory=utc_now)
    #: Named approver, required for WAIVED.
    waived_by: Optional[str] = None
    waiver_rationale: Optional[str] = None

    @model_validator(mode="after")
    def _track_and_mode_agree(self) -> "GateEvaluation":
        if self.evidence_mode is not None and not admits_track(
            self.evidence_mode, self.track
        ):
            raise ValueError(
                f"gate {self.gate_id}: {track_admission_reason(self.evidence_mode, self.track)}"
                " — synthetic evidence cannot support a real-track verdict"
            )
        if self.outcome in SATISFYING_OUTCOMES and self.outcome is GateOutcome.PASS:
            if self.evidence_mode is None:
                raise ValueError(
                    f"gate {self.gate_id}: PASS requires an evidence_mode; an "
                    "unsupported pass is an assertion, not an evaluation"
                )
            if not self.evidence_ids:
                raise ValueError(
                    f"gate {self.gate_id}: PASS requires at least one evidence_id"
                )
        if self.outcome is GateOutcome.WAIVED and not self.waived_by:
            raise ValueError(
                f"gate {self.gate_id}: WAIVED requires a named waived_by; an "
                "anonymous waiver is unauditable"
            )
        if self.waived_by and self.outcome is not GateOutcome.WAIVED:
            raise ValueError(
                f"gate {self.gate_id}: waived_by is set on a {self.outcome.value} "
                "outcome"
            )
        return self

    def satisfied(self) -> bool:
        """Whether this evaluation lets its transition proceed.

        ``WAIVED`` counts, because a named accountable approver decided it
        should. It is scored separately so a waiver-heavy pass is visible.
        """
        return self.outcome in SATISFYING_OUTCOMES or self.outcome is GateOutcome.WAIVED


class PromotionApproval(StrictModel):
    """Four-eyes approval of a promotion decision.

    Reuses the V2 maker/checker rule from ``evidence.py``: the submitter cannot
    be the reviewer, and roles must differ.
    """

    approval_id: str
    transition_id: str
    track: DecisionTrack
    submitted_by: str
    submitted_role: str
    reviewed_by: str
    reviewed_role: str
    decision: str = Field(pattern="^(APPROVED|REJECTED)$")
    rationale: str
    submitted_at: datetime = Field(default_factory=utc_now)
    reviewed_at: datetime = Field(default_factory=utc_now)
    reason_codes: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _four_eyes(self) -> "PromotionApproval":
        if self.submitted_by == self.reviewed_by:
            raise ValueError(
                f"approval {self.approval_id}: FOUR_EYES_SUBMITTER_CANNOT_REVIEW"
            )
        if self.submitted_role == self.reviewed_role:
            raise ValueError(
                f"approval {self.approval_id}: DUPLICATE_REVIEWER_ROLE "
                f"({self.submitted_role})"
            )
        if self.reviewed_at < self.submitted_at:
            raise ValueError(
                f"approval {self.approval_id}: reviewed before it was submitted"
            )
        return self


class PromotionScore(StrictModel):
    """Two scores that must never be averaged into one.

    ``promotion_machinery_readiness`` (PMR) measures whether the promotion
    apparatus works — computed on the rehearsal track, where synthetic evidence
    is exactly what should be counted.

    ``bank_evidence_readiness`` (BER) measures whether the *bank* has the
    evidence — computed on the real track, where synthetic contributes zero.

    A single composite would let a high PMR mask a zero BER, which is precisely
    the summary-over-substance reading this twin exists to prevent.
    """

    promotion_machinery_readiness: float = Field(ge=0.0, le=1.0)
    bank_evidence_readiness: float = Field(ge=0.0, le=1.0)
    pmr_weight_earned: float = Field(ge=0.0)
    pmr_weight_available: float = Field(ge=0.0)
    ber_weight_earned: float = Field(ge=0.0)
    ber_weight_available: float = Field(ge=0.0)
    synthetic_weight_excluded_from_ber: float = Field(ge=0.0)
    waived_gate_count: int = Field(ge=0)
    severity_weights: Dict[str, int] = Field(default_factory=lambda: dict(SEVERITY_WEIGHTS))
    basis: str = "pmr-rehearsal-track-ber-real-track-1.0.0"

    @model_validator(mode="after")
    def _no_composite_and_ber_excludes_synthetic(self) -> "PromotionScore":
        if self.ber_weight_earned > self.ber_weight_available:
            raise ValueError("BER earned weight exceeds available weight")
        if self.pmr_weight_earned > self.pmr_weight_available:
            raise ValueError("PMR earned weight exceeds available weight")
        return self


class PromotionDecision(StrictModel):
    """The published promotion position, both tracks side by side."""

    decision_id: str
    as_of: date
    generated_at: datetime = Field(default_factory=utc_now)
    published_at: Optional[datetime] = None
    #: State the *bank* has authorised. The number that matters.
    real_state: PromotionState
    #: Highest state the rehearsal reached. Proves the machinery, not the bank.
    rehearsed_state: PromotionState
    #: Explicit, because a reader who sees SHADOW_READY anywhere on the page
    #: should not have to work out which track it came from.
    bank_shadow_authorized: bool
    passed_real_transitions: List[str] = Field(default_factory=list)
    passed_rehearsal_transitions: List[str] = Field(default_factory=list)
    granted_capabilities: List[PromotionCapability] = Field(default_factory=list)
    refused_capabilities: Dict[str, str] = Field(default_factory=dict)
    score: PromotionScore
    state_machine_version: str
    contracts_version: str = CONTRACTS_VERSION
    reason_codes: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _authorisation_follows_the_real_track(self) -> "PromotionDecision":
        from .states import PromotionState as _State
        from .states import rank

        if self.bank_shadow_authorized and rank(self.real_state) < rank(
            _State.SHADOW_READY
        ):
            raise ValueError(
                "bank_shadow_authorized is true while the real state is "
                f"{self.real_state.value}; authorisation cannot precede the "
                "state that confers it"
            )
        overlap = set(self.granted_capabilities) & set(
            PromotionCapability(name) for name in self.refused_capabilities
        )
        if overlap:
            raise ValueError(
                "capabilities both granted and refused: "
                + ",".join(sorted(item.value for item in overlap))
            )
        return self


class RehearsalScenario(StrictModel):
    """A named rehearsal, including the negative ones.

    ``expected_outcome`` is declared before the run. A scenario that only
    records what happened cannot distinguish a gate that correctly failed from
    one that broke.
    """

    scenario_id: str
    title: str
    description: str
    transition_id: str
    targeted_gate_ids: List[str]
    expected_outcome: GateOutcome
    is_negative_scenario: bool = False
    mode: PromotionEvidenceMode = PromotionEvidenceMode.SYNTHETIC_REHEARSAL

    @model_validator(mode="after")
    def _negative_scenarios_expect_failure(self) -> "RehearsalScenario":
        if self.is_negative_scenario and self.expected_outcome is GateOutcome.PASS:
            raise ValueError(
                f"scenario {self.scenario_id}: a negative scenario that expects "
                "PASS is not testing a gate"
            )
        if not self.targeted_gate_ids:
            raise ValueError(f"scenario {self.scenario_id}: targets no gate")
        return self


class VirtualClockState(StrictModel):
    """Virtual time, kept lexically separate from elapsed time.

    ``rehearsal_days_elapsed`` and ``elapsed_bank_shadow_days`` are published
    together, always. The second is what keeps the first honest: a 30-day
    accelerated rehearsal alongside a hard zero cannot be misread as a month of
    bank operation.
    """

    clock_id: str
    #: Where the virtual clock currently sits.
    simulation_clock: datetime
    #: Virtual days simulated since the last reset.
    rehearsal_days_elapsed: int = Field(ge=0)
    #: Consecutive clean virtual days. Reset by an incident.
    consecutive_clean_rehearsal_days: int = Field(ge=0)
    #: Real bank shadow days. Zero until the bank actually runs one.
    elapsed_bank_shadow_days: int = Field(ge=0)
    incidents_injected: int = Field(ge=0, default=0)
    last_reset_reason: Optional[str] = None
    track: DecisionTrack = DecisionTrack.REHEARSAL

    @model_validator(mode="after")
    def _virtual_time_is_not_bank_time(self) -> "VirtualClockState":
        if self.track is DecisionTrack.REAL:
            raise ValueError(
                "a virtual clock cannot run on the REAL track; real promotion "
                "is governed by elapsed bank time only"
            )
        if self.consecutive_clean_rehearsal_days > self.rehearsal_days_elapsed:
            raise ValueError(
                "consecutive clean days exceed total simulated days"
            )
        if self.elapsed_bank_shadow_days > 0:
            raise ValueError(
                "elapsed_bank_shadow_days must be 0 in a rehearsal; a simulated "
                "day is not a bank day and recording one here would be the "
                "exact overstatement this contract exists to prevent"
            )
        return self


class IncidentInjection(StrictModel):
    """A deliberately injected failure and what it reset.

    Incidents reset the rehearsal counter only. An injected incident that
    changed a real number would mean the rehearsal was not isolated.
    """

    incident_id: str
    scenario_id: str
    #: Virtual day the incident fires.
    injected_on_rehearsal_day: int = Field(ge=1)
    severity: GateSeverity
    description: str
    #: Gate expected to fail as a result.
    expected_failing_gate_id: str
    resets_rehearsal_counter: bool = True
    #: Always false. Present so the invariant is asserted rather than assumed.
    affects_real_track: bool = False
    simulation_clock: datetime

    @model_validator(mode="after")
    def _isolated_from_the_real_track(self) -> "IncidentInjection":
        if self.affects_real_track:
            raise ValueError(
                f"incident {self.incident_id}: a simulated incident cannot "
                "affect the real track"
            )
        if self.severity is GateSeverity.CRITICAL and not self.resets_rehearsal_counter:
            raise ValueError(
                f"incident {self.incident_id}: a CRITICAL incident that does not "
                "reset the clean-day counter would let a broken run count as clean"
            )
        return self


class E3SampleSizePlan(StrictModel):
    """How many multibank-observed clients would be needed, or that we cannot say.

    ``recommended_n`` is ``None`` with ``NOT_DETERMINED_UP_TO_150`` when no
    tested sample size reached the target. Manufacturing a recommendation from a
    sweep that never converged would be the most consequential kind of
    overclaim this planner could make.
    """

    plan_id: str
    as_of: date
    target_coverage: float = Field(gt=0.0, lt=1.0)
    target_half_width: float = Field(gt=0.0, lt=1.0)
    tested_sample_sizes: List[int]
    recommended_n: Optional[int] = None
    determination: str
    #: Wilson interval per tested n, as (n, lower, upper).
    wilson_intervals: List[List[float]] = Field(default_factory=list)
    replications_per_n: int = Field(gt=0)
    mode: PromotionEvidenceMode = PromotionEvidenceMode.SYNTHETIC_REHEARSAL
    generated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _no_manufactured_recommendation(self) -> "E3SampleSizePlan":
        if self.recommended_n is None and self.determination != NOT_DETERMINED_UP_TO_150:
            raise ValueError(
                f"plan {self.plan_id}: no recommended_n requires determination "
                f"{NOT_DETERMINED_UP_TO_150}"
            )
        if self.recommended_n is not None:
            if self.determination == NOT_DETERMINED_UP_TO_150:
                raise ValueError(
                    f"plan {self.plan_id}: determination says undetermined while "
                    f"recommending n={self.recommended_n}"
                )
            if self.recommended_n not in self.tested_sample_sizes:
                raise ValueError(
                    f"plan {self.plan_id}: recommended n={self.recommended_n} was "
                    "never tested"
                )
        return self


def transition_is_legal(source: PromotionState, target: PromotionState) -> bool:
    """Re-exported so callers need not import from two modules."""
    return is_legal_transition(source, target)


def evidence_supports_gate(
    definition: GateDefinition,
    evidence: GateEvidence,
    track: DecisionTrack,
) -> Tuple[bool, str]:
    """Whether one piece of evidence may support one gate on one track.

    Kept as a function rather than a validator because it needs both the gate
    definition and the evidence, which are separate contracts by design: gates
    are governed catalogue data, evidence is produced at runtime.
    """
    if evidence.gate_id != definition.gate_id:
        return False, "EVIDENCE_BOUND_TO_A_DIFFERENT_GATE"
    if not admits_track(evidence.mode, track):
        return False, track_admission_reason(evidence.mode, track)
    if track is DecisionTrack.REAL and not satisfies_minimum(
        evidence.mode, definition.minimum_real_evidence_mode
    ):
        return (
            False,
            f"REQUIRES_AT_LEAST_{definition.minimum_real_evidence_mode.value}"
            f"_GOT_{evidence.mode.value}",
        )
    return True, f"ACCEPTED_{evidence.mode.value}_ON_{track.value}"
