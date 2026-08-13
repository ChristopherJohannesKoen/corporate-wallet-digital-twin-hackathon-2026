"""The promotion gate catalogue: governed data, not hardcoded checks.

Three things were wrong with how gates existed before V3.2.

1. ``ShadowReleaseGate`` hardcodes twenty checks in a single method with string
   thresholds, no evidence binding, no owner, and no statement of what failure
   costs. It can compute a verdict; it cannot explain one.
2. ``config/mlflow_promotion_policy.json`` declares gate ids for exactly two
   transitions — ``candidate_to_shadow`` and ``shadow_to_champion`` — and **no
   code ever parses it**. ``production_target.py`` only greps it for substrings.
   A policy nothing reads is a document, not a control.
3. The two vocabularies share no identifiers. ``release_gates.py`` says
   ``interval-coverage-90``; the MLflow policy says
   ``90pct_coverage_between_85pct_and_95pct``. The same requirement under two
   names cannot be reconciled by anything but a human reading both.

This module fixes all three: one catalogue, five transitions, machine-read,
with each gate carrying its legacy identifiers so the older artifacts remain
traceable rather than being silently orphaned.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Tuple

from .contracts import GateDefinition, GateSeverity, SEVERITY_WEIGHTS
from .modes import PromotionEvidenceMode as Mode
from .states import PromotionCapability as Cap
from .states import PromotionState, transition_id

CATALOGUE_VERSION = "v32-promotion-gate-catalogue-1.0.0"

_OFFLINE_TO_SHADOW = transition_id(
    PromotionState.OFFLINE_CANDIDATE, PromotionState.SHADOW_READY
)
_SHADOW_TO_PILOT = transition_id(PromotionState.SHADOW_READY, PromotionState.PILOT_READY)
_PILOT_TO_SCALE = transition_id(PromotionState.PILOT_READY, PromotionState.SCALE_READY)
_SCALE_TO_CHAMPION = transition_id(
    PromotionState.SCALE_READY, PromotionState.CAUSAL_CHAMPION
)

#: Legacy identifiers each gate subsumes, keyed by V3.2 gate id. Kept as data so
#: ``scripts`` and older reports can be mapped forward without a lookup living
#: in someone's head. Sources are ``release_gates.py`` (hyphenated) and
#: ``config/mlflow_promotion_policy.json`` (snake_case).
LEGACY_GATE_ALIASES: Mapping[str, Tuple[str, ...]] = {
    "point-in-time-zero-leakage": (
        "pit-zero-leakage",
        "zero_point_in_time_leakage",
    ),
    "reconciliation-exact": (
        "critical-reconciliation",
        "shadow_wallet_mass_balance_exact",
    ),
    "interval-coverage-90": (
        "interval-coverage-90",
        "90pct_coverage_between_85pct_and_95pct",
    ),
    "crps-improvement": ("crps-improvement", "crps_improvement_at_least_10pct"),
    "independent-reproduction": ("independent_reproduction",),
    "genai-schema-and-fidelity": (
        "genai-schema",
        "genai-critical-facts",
        "genai-precision",
        "genai-abstention",
        "genai-numeric-preservation",
        "genai-critical-unsupported",
        "v31_genai_schema_and_golden_set_report",
    ),
    "prompt-injection-resistance": ("prompt-injection",),
    "entitlement-negative-tests": (
        "entitlement-negative-tests",
        "security_and_entitlement_approval",
    ),
    "supply-chain-clean": ("vulnerabilities", "sbom", "container-signature"),
    "service-availability": ("availability",),
    "read-latency-p95": ("p95-latency",),
    "event-latency": ("event-latency",),
    "refresh-by-0600-sast": ("refresh-by-0600",),
    "no-unresolved-sev1-sev2": ("no-sev1-sev2",),
    "elapsed-clean-shadow-days": (
        "shadow-operating-period",
        "30_elapsed_clean_shadow_days",
    ),
    "e3-multibank-observation-approved": (
        "no_measured_competitor_share_without_e3",
        "approved_e3_calibration_panel",
    ),
    "bank-approved-economics-registered": (
        "approved-economics",
        "approved_economics",
        "solution_specific_economics_approved",
    ),
    "randomised-trial-validated": (
        "no_causal_incremental_value_without_trial_validation",
    ),
    "model-risk-approval": ("model_risk_approval",),
    "feasibility-gates-block-selection": (
        "failed_feasibility_gates_block_selection",
        "unknown_material_gates_create_discovery_only",
    ),
}


def _gate(
    gate_id: str,
    title: str,
    transition: str,
    severity: GateSeverity,
    requirement: str,
    consequence: str,
    minimum_mode: Mode,
    owner: str,
    approver: str,
    what_would_pass: str,
    *,
    blocking: bool = True,
    freshness_days: Optional[int] = None,
    capabilities: Optional[List[Cap]] = None,
) -> GateDefinition:
    return GateDefinition(
        gate_id=gate_id,
        title=title,
        transition_id=transition,
        severity=severity,
        blocking=blocking,
        requirement=requirement,
        consequence_if_failed=consequence,
        minimum_real_evidence_mode=minimum_mode,
        owner_role=owner,
        approver_role=approver,
        freshness_days=freshness_days,
        what_would_make_real_pass=what_would_pass,
        capability_effects=capabilities or [],
    )


#: OFFLINE_CANDIDATE → SHADOW_READY. Can this system be allowed to score live
#: bank flow, with nothing reaching a banker?
_OFFLINE_TO_SHADOW_GATES: Tuple[GateDefinition, ...] = (
    _gate(
        "independent-reproduction",
        "Independent reproduction from a clean commit",
        _OFFLINE_TO_SHADOW,
        GateSeverity.CRITICAL,
        "A second party rebuilds every gated artifact byte-identically from the "
        "named commit.",
        "Numbers that cannot be reproduced cannot be defended in a model-risk "
        "review, and no later gate means anything if the artifact under review "
        "is not the artifact that was built.",
        Mode.PUBLIC_PACKAGE,
        "ENGINEERING",
        "MODEL_RISK",
        "A reviewer outside the build machine runs scripts/build_submission.py "
        "at the tagged commit and reports matching digests for all 74 gated "
        "artifacts.",
        freshness_days=90,
    ),
    _gate(
        "point-in-time-zero-leakage",
        "Zero point-in-time leakage",
        _OFFLINE_TO_SHADOW,
        GateSeverity.CRITICAL,
        "No input dated after a record's as_of informs that record.",
        "Leakage inflates every accuracy number the bank would rely on, and it "
        "does so invisibly — the model looks better precisely where it is most "
        "wrong.",
        Mode.PUBLIC_PACKAGE,
        "DATA_ENGINEERING",
        "MODEL_RISK",
        "The V3 validation report shows point_in_time_violations = 0 on bank "
        "data rather than on the public fixture.",
        freshness_days=30,
    ),
    _gate(
        "reconciliation-exact",
        "Critical reconciliation is exact",
        _OFFLINE_TO_SHADOW,
        GateSeverity.CRITICAL,
        "Shadow wallet mass balance reconciles exactly, with no tolerance.",
        "An unreconciled wallet means the twin and the bank disagree about how "
        "much money exists; every downstream share and value is then arithmetic "
        "on an unknown base.",
        Mode.REAL_BANK,
        "FINANCE_OPERATIONS",
        "FINANCE_CONTROLLER",
        "Reconciliation runs against real bank balances for a full cycle and "
        "reports a rate of exactly 1.0.",
        freshness_days=7,
    ),
    _gate(
        "interval-coverage-90",
        "90% interval coverage lands in 0.85–0.95",
        _OFFLINE_TO_SHADOW,
        GateSeverity.HIGH,
        "Empirical coverage of the nominal 90% interval falls within 0.85–0.95.",
        "An interval that does not cover at its stated rate is a false precision "
        "claim; bankers would read a tight band as confidence the model has not "
        "earned.",
        Mode.REAL_BANK,
        "DATA_SCIENCE",
        "MODEL_RISK",
        "Coverage is measured on held-out real bank outcomes, not on the "
        "synthetic calibration lab.",
        freshness_days=90,
    ),
    _gate(
        "crps-improvement",
        "CRPS improves at least 10% over baseline",
        _OFFLINE_TO_SHADOW,
        GateSeverity.HIGH,
        "Continuous ranked probability score improves ≥10% against the "
        "registered baseline.",
        "Without a margin over the baseline the twin costs money and governance "
        "overhead to reproduce what the bank already had.",
        Mode.REAL_BANK,
        "DATA_SCIENCE",
        "MODEL_RISK",
        "The comparison is run on real bank outcomes with the baseline frozen "
        "before the comparison.",
        freshness_days=90,
    ),
    _gate(
        "genai-schema-and-fidelity",
        "Narrative generation is schema-valid and factually bounded",
        _OFFLINE_TO_SHADOW,
        GateSeverity.HIGH,
        "First-attempt schema compliance with no repair or retry; every critical "
        "fact traceable; no unsupported critical claim; numerics preserved.",
        "A narrative that invents a number is worse than no narrative: it is "
        "delivered in the bank's voice and will be read as the bank's position.",
        Mode.PUBLIC_PACKAGE,
        "ENGINEERING",
        "MODEL_RISK",
        "At least three accepted live-provider briefs across providers, produced "
        "with rotated credentials injected at runtime.",
        freshness_days=30,
    ),
    _gate(
        "prompt-injection-resistance",
        "Zero successful prompt injections",
        _OFFLINE_TO_SHADOW,
        GateSeverity.CRITICAL,
        "No injection attempt in the registered corpus causes the model to "
        "exceed its closed fact pack.",
        "A successful injection lets client-supplied text steer what the bank "
        "tells another client.",
        Mode.PUBLIC_PACKAGE,
        "SECURITY",
        "SECURITY_OFFICER",
        "The injection corpus is run against the live provider path rather than "
        "the offline stub.",
        freshness_days=30,
    ),
    _gate(
        "entitlement-negative-tests",
        "Entitlement negative tests all pass",
        _OFFLINE_TO_SHADOW,
        GateSeverity.CRITICAL,
        "Every cross-client, cross-region and wrong-role request is denied.",
        "One entitlement gap in a corporate bank is a client-confidentiality "
        "breach, which is a regulatory matter rather than a quality one.",
        Mode.PUBLIC_PACKAGE,
        "SECURITY",
        "SECURITY_OFFICER",
        "Denials are proven against the request path with OPA enforcing, not "
        "against in-process entitlement computation.",
        freshness_days=30,
        capabilities=[Cap.HIDDEN_SHADOW_SCORING],
    ),
    _gate(
        "supply-chain-clean",
        "Signed image, SBOM, no unresolved critical or high vulnerabilities",
        _OFFLINE_TO_SHADOW,
        GateSeverity.HIGH,
        "Container image signed, SBOM published, zero unresolved CRITICAL/HIGH "
        "findings.",
        "An unsigned or vulnerable image cannot be admitted to a bank runtime, "
        "regardless of how good the model is.",
        Mode.PUBLIC_PACKAGE,
        "PLATFORM_ENGINEERING",
        "SECURITY_OFFICER",
        "CI publishes a cosign signature and SBOM for the released digest and "
        "Trivy reports zero unresolved CRITICAL/HIGH.",
        freshness_days=14,
    ),
    _gate(
        "feasibility-gates-block-selection",
        "Failed feasibility blocks selection; unknown yields discovery only",
        _OFFLINE_TO_SHADOW,
        GateSeverity.STANDARD,
        "A failed material feasibility gate removes a solution from selection; "
        "an unknown one downgrades it to discovery.",
        "Recommending something the client cannot execute wastes the RM's "
        "credibility, which is the scarcest resource in the relationship.",
        Mode.PUBLIC_PACKAGE,
        "DATA_SCIENCE",
        "PRODUCT_OWNER",
        "The rule is exercised against real client feasibility data rather than "
        "the fixture.",
    ),
)

#: SHADOW_READY → PILOT_READY. Can real RMs see this, supervised?
_SHADOW_TO_PILOT_GATES: Tuple[GateDefinition, ...] = (
    _gate(
        "elapsed-clean-shadow-days",
        "Thirty elapsed clean bank shadow days",
        _SHADOW_TO_PILOT,
        GateSeverity.CRITICAL,
        "Thirty consecutive calendar days of shadow operation with no critical "
        "incident, measured in elapsed bank time.",
        "Shadow exists to surface the failures that only appear under real "
        "traffic over real time. A simulated month surfaces none of them.",
        Mode.BANK_ATTESTED,
        "PRODUCTION_OPERATIONS",
        "HEAD_OF_OPERATIONS",
        "The bank runs the system in shadow for thirty consecutive clean "
        "calendar days. No rehearsal can substitute; this gate is why "
        "elapsed_bank_shadow_days is published beside every rehearsal count.",
        freshness_days=60,
        capabilities=[Cap.SUPERVISED_RM_PILOT],
    ),
    _gate(
        "service-availability",
        "Availability at or above 99.9%",
        _SHADOW_TO_PILOT,
        GateSeverity.HIGH,
        "Measured availability ≥ 0.999 over the shadow period.",
        "An RM who finds the twin down mid-meeting stops opening it, and "
        "adoption never recovers.",
        Mode.REAL_BANK,
        "PRODUCTION_OPERATIONS",
        "HEAD_OF_OPERATIONS",
        "Availability is measured from bank monitoring over the elapsed shadow "
        "window.",
        freshness_days=30,
    ),
    _gate(
        "read-latency-p95",
        "p95 read latency below 750 ms",
        _SHADOW_TO_PILOT,
        GateSeverity.STANDARD,
        "p95 read latency < 750 ms under bank load.",
        "Latency above roughly a second turns a decision aid into an "
        "interruption.",
        Mode.REAL_BANK,
        "PLATFORM_ENGINEERING",
        "HEAD_OF_OPERATIONS",
        "p95 is measured on bank infrastructure under production-shaped load, "
        "not on the build machine.",
        freshness_days=30,
    ),
    _gate(
        "event-latency",
        "Event propagation under 300 s",
        _SHADOW_TO_PILOT,
        GateSeverity.STANDARD,
        "Domain events reach consumers in under 300 seconds.",
        "Stale events mean two bankers see different answers to the same "
        "question on the same morning.",
        Mode.REAL_BANK,
        "PLATFORM_ENGINEERING",
        "HEAD_OF_OPERATIONS",
        "Latency is measured across the bank's actual broker.",
        freshness_days=30,
    ),
    _gate(
        "refresh-by-0600-sast",
        "Daily refresh completes by 06:00 SAST",
        _SHADOW_TO_PILOT,
        GateSeverity.STANDARD,
        "The overnight refresh completes before 06:00 SAST.",
        "A refresh that lands after the RM's first meeting is a day late for "
        "the decision it was meant to inform.",
        Mode.REAL_BANK,
        "PRODUCTION_OPERATIONS",
        "HEAD_OF_OPERATIONS",
        "Completion time is observed over the elapsed shadow window.",
        freshness_days=30,
    ),
    _gate(
        "no-unresolved-sev1-sev2",
        "No unresolved Sev-1 or Sev-2 incidents",
        _SHADOW_TO_PILOT,
        GateSeverity.CRITICAL,
        "Zero unresolved Sev-1/Sev-2 at the promotion decision point.",
        "Promoting over an open severe incident widens its blast radius to real "
        "client conversations.",
        Mode.BANK_ATTESTED,
        "PRODUCTION_OPERATIONS",
        "HEAD_OF_OPERATIONS",
        "The bank incident register shows none open against this system.",
        freshness_days=7,
    ),
    _gate(
        "model-risk-approval",
        "Model risk sign-off",
        _SHADOW_TO_PILOT,
        GateSeverity.CRITICAL,
        "Model risk management approves the model card, limitations and "
        "monitoring plan.",
        "Without model-risk approval the bank has no accountable owner for what "
        "the model tells an RM to do.",
        Mode.BANK_ATTESTED,
        "MODEL_RISK",
        "CHIEF_RISK_OFFICER",
        "Model risk reviews the V3.2 model card and records an approval with a "
        "named accountable owner.",
        freshness_days=365,
    ),
)

#: PILOT_READY → SCALE_READY. Can this become ordinary RM tooling?
_PILOT_TO_SCALE_GATES: Tuple[GateDefinition, ...] = (
    _gate(
        "supervised-pilot-completed",
        "Supervised RM pilot completed with real participants",
        _PILOT_TO_SCALE,
        GateSeverity.CRITICAL,
        "A named RM cohort completes at least five real supervised sessions "
        "each, with recorded outcomes.",
        "Scaling a tool nobody has used in anger scales its unknown failure "
        "modes along with it.",
        Mode.BANK_ATTESTED,
        "COMMERCIAL_BANKING",
        "HEAD_OF_COVERAGE",
        "Real RMs run real client sessions. Fixture persona sessions carry "
        "real_participant=False by construction and can never satisfy this.",
        freshness_days=180,
        capabilities=[Cap.PRODUCTION_RM_DECISION_SUPPORT],
    ),
    _gate(
        "bank-approved-economics-registered",
        "Bank-approved economics registered and unexpired",
        _PILOT_TO_SCALE,
        GateSeverity.CRITICAL,
        "Every monetised value traces to a bank-approved, in-date rate card.",
        "A money number without approved economics is the bank quoting itself a "
        "price it never agreed.",
        Mode.BANK_ATTESTED,
        "PRODUCT_FINANCE",
        "FINANCE_CONTROLLER",
        "Product finance approves rate cards covering every product in the grid "
        "and registers them with expiry dates.",
        freshness_days=365,
        capabilities=[Cap.COMMERCIAL_VALUE_CLAIM],
    ),
    _gate(
        "rollback-restores-prior-state",
        "Rollback restores the prior champion exactly",
        _PILOT_TO_SCALE,
        GateSeverity.HIGH,
        "A rehearsed rollback restores the previous model alias and its outputs "
        "exactly.",
        "Without a proven rollback, the decision to promote is effectively "
        "irreversible, which changes the risk of every promotion after it.",
        Mode.PUBLIC_PACKAGE,
        "PLATFORM_ENGINEERING",
        "HEAD_OF_OPERATIONS",
        "A rollback is exercised in the bank environment and the restored "
        "outputs are compared digest-for-digest.",
        freshness_days=90,
    ),
    _gate(
        "e3-multibank-observation-approved",
        "E3 multibank observation panel approved",
        _PILOT_TO_SCALE,
        GateSeverity.HIGH,
        "An approved panel provides multibank observation sufficient to identify "
        "competitor share.",
        "Without E3 the twin can bound a competitor's share but cannot measure "
        "it. Reporting an estimate as measured would misstate what is known.",
        Mode.BANK_ATTESTED,
        "DATA_STRATEGY",
        "CHIEF_DATA_OFFICER",
        "A multibank data source is contracted, approved and calibrated. Until "
        "then MEASURED_SHARE_REPORTING stays refused — this gate does not block "
        "hidden shadow scoring, which needs no share measurement.",
        blocking=False,
        freshness_days=365,
        capabilities=[Cap.MEASURED_SHARE_REPORTING],
    ),
)

#: SCALE_READY → CAUSAL_CHAMPION. Did it actually cause anything?
_SCALE_TO_CHAMPION_GATES: Tuple[GateDefinition, ...] = (
    _gate(
        "randomised-trial-validated",
        "Cluster-randomised trial shows incremental value",
        _SCALE_TO_CHAMPION,
        GateSeverity.CRITICAL,
        "A pre-registered cluster-randomised trial reports an ITT effect with "
        "cluster-robust inference and randomization-inference confirmation.",
        "Every observational uplift figure is confounded by which clients the "
        "RMs chose to visit. Only randomisation separates the tool's effect "
        "from the selection.",
        Mode.BANK_ATTESTED,
        "DATA_SCIENCE",
        "CHIEF_RISK_OFFICER",
        "The bank runs a pre-registered cluster-randomised trial to its planned "
        "sample size and the analysis is independently reviewed.",
        freshness_days=365,
        capabilities=[Cap.CAUSAL_VALUE_CLAIM],
    ),
    _gate(
        "trial-first-stage-strength-adequate",
        "Trial first stage is not weak",
        _SCALE_TO_CHAMPION,
        GateSeverity.CRITICAL,
        "First-stage compliance strength is at or above 0.10.",
        "A weak first stage makes the instrument uninformative: the confidence "
        "interval is wide and badly behaved, and a point estimate drawn from it "
        "would be presented with precision it does not have.",
        Mode.BANK_ATTESTED,
        "DATA_SCIENCE",
        "MODEL_RISK",
        "Observed compliance in the trial reaches the pre-registered strength "
        "threshold. If it does not, the honest outcome is a null result and the "
        "system stays SCALE_READY.",
        freshness_days=365,
        capabilities=[Cap.CAUSAL_VALUE_CLAIM],
    ),
    _gate(
        "sustained-adoption",
        "Sustained RM adoption",
        _SCALE_TO_CHAMPION,
        GateSeverity.HIGH,
        "The RM cohort sustains use beyond the supervised period without "
        "prompting.",
        "A causal champion nobody opens is a claim about a system that is not "
        "in use.",
        Mode.BANK_ATTESTED,
        "COMMERCIAL_BANKING",
        "HEAD_OF_COVERAGE",
        "Adoption is measured from real RM sessions over a sustained window.",
        freshness_days=180,
    ),
)

GATE_CATALOGUE: Tuple[GateDefinition, ...] = (
    _OFFLINE_TO_SHADOW_GATES
    + _SHADOW_TO_PILOT_GATES
    + _PILOT_TO_SCALE_GATES
    + _SCALE_TO_CHAMPION_GATES
)

GATES_BY_ID: Mapping[str, GateDefinition] = {
    gate.gate_id: gate for gate in GATE_CATALOGUE
}


def gates_for_transition(transition: str) -> Tuple[GateDefinition, ...]:
    return tuple(gate for gate in GATE_CATALOGUE if gate.transition_id == transition)


def blocking_gates_for_transition(transition: str) -> Tuple[GateDefinition, ...]:
    return tuple(gate for gate in gates_for_transition(transition) if gate.blocking)


def severity_weight(gate: GateDefinition) -> int:
    return SEVERITY_WEIGHTS[gate.severity.value]


def resolve_legacy_alias(alias: str) -> Optional[str]:
    """Map a V2/MLflow gate id onto its V3.2 gate, or None if unmapped."""
    for gate_id, aliases in LEGACY_GATE_ALIASES.items():
        if alias in aliases:
            return gate_id
    return None


def catalogue_summary() -> Dict[str, object]:
    """Machine-readable description of the catalogue, for publication."""
    by_transition: Dict[str, Dict[str, object]] = {}
    for gate in GATE_CATALOGUE:
        entry = by_transition.setdefault(
            gate.transition_id,
            {"gates": 0, "blocking": 0, "weight": 0, "critical": 0},
        )
        entry["gates"] = int(entry["gates"]) + 1
        entry["weight"] = int(entry["weight"]) + severity_weight(gate)
        if gate.blocking:
            entry["blocking"] = int(entry["blocking"]) + 1
        if gate.severity is GateSeverity.CRITICAL:
            entry["critical"] = int(entry["critical"]) + 1
    return {
        "catalogue_version": CATALOGUE_VERSION,
        "total_gates": len(GATE_CATALOGUE),
        "severity_weights": dict(SEVERITY_WEIGHTS),
        "by_transition": by_transition,
        "legacy_aliases_mapped": sum(
            len(aliases) for aliases in LEGACY_GATE_ALIASES.values()
        ),
    }
