"""Export the V3.2 promotion JSON Schemas and the gate catalogue.

The catalogue is exported as data rather than living only in code, for the same
reason the gates were moved out of ``ShadowReleaseGate``: a control nobody can
read is a control nobody can review. Unlike
``config/mlflow_promotion_policy.json`` — which declared gate ids that no code
ever parsed — this file is generated *from* the catalogue the engine uses, so
the published document and the enforced policy cannot drift apart.

    python scripts/export_v32_contracts.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.canonical import ARTIFACT_AS_OF, write_canonical_json  # noqa: E402
from wallet_twin_v32.laboratories import run_all  # noqa: E402
from wallet_twin_v32 import (  # noqa: E402
    CATALOGUE_VERSION,
    CONTRACTS_VERSION,
    ENGINE_VERSION,
    EVIDENCE_MODE_POLICY_VERSION,
    GATE_CATALOGUE,
    SCORING_VERSION,
    SEVERITY_WEIGHTS,
    STATE_MACHINE_VERSION,
    E3SampleSizePlan,
    GateDefinition,
    GateEvaluation,
    GateEvidence,
    IncidentInjection,
    PromotionApproval,
    PromotionDecision,
    PromotionScore,
    RehearsalScenario,
    SignedEvidenceEnvelope,
    VirtualClockState,
    catalogue_summary,
)
from wallet_twin_v32.catalogue import LEGACY_GATE_ALIASES  # noqa: E402
from wallet_twin_v32.dsse import DSSE_VERSION, PAYLOAD_TYPE  # noqa: E402
from wallet_twin_v32.events import (  # noqa: E402
    EVENTS_VERSION,
    PROMOTION_EVENT_TYPES,
    PromotionEventEnvelope,
    declared_topics,
)
from wallet_twin_v32.rfc8785 import JCS_VERSION  # noqa: E402
from wallet_twin_v32.signers import signer_capability_report  # noqa: E402
from wallet_twin_v32.trust import TRUST_REGISTRY_VERSION  # noqa: E402
from wallet_twin_v32.modes import (  # noqa: E402
    EVIDENCE_MODES,
    TRACKS,
    bank_evidence_weight,
)
from wallet_twin_v32.states import (  # noqa: E402
    CAPABILITY_STATE_THRESHOLD,
    EVIDENCE_PREREQUISITES,
    PERMANENTLY_WITHHELD,
    PROMOTION_ORDER,
    TRANSITION_IDS,
    CAPABILITIES,
)

CONTRACTS = ROOT / "contracts"
SCHEMAS = CONTRACTS / "jsonschema"
OUTPUTS = ROOT / "outputs" / "v32"

MODELS = {
    "v32-gate-definition": GateDefinition,
    "v32-gate-evidence": GateEvidence,
    "v32-signed-evidence-envelope": SignedEvidenceEnvelope,
    "v32-gate-evaluation": GateEvaluation,
    "v32-promotion-approval": PromotionApproval,
    "v32-promotion-score": PromotionScore,
    "v32-promotion-decision": PromotionDecision,
    "v32-rehearsal-scenario": RehearsalScenario,
    "v32-virtual-clock-state": VirtualClockState,
    "v32-incident-injection": IncidentInjection,
    "v32-e3-sample-size-plan": E3SampleSizePlan,
    "v32-promotion-event-envelope": PromotionEventEnvelope,
}


def gate_catalogue_document() -> Dict[str, Any]:
    gates: List[Dict[str, Any]] = []
    for gate in GATE_CATALOGUE:
        payload = gate.model_dump(mode="json")
        payload["severity_weight"] = SEVERITY_WEIGHTS[gate.severity.value]
        payload["legacy_aliases"] = list(LEGACY_GATE_ALIASES.get(gate.gate_id, ()))
        gates.append(payload)
    return {
        "catalogue_version": CATALOGUE_VERSION,
        "state_machine_version": STATE_MACHINE_VERSION,
        "contracts_version": CONTRACTS_VERSION,
        "purpose": (
            "The gates governing promotion, as data. Generated from the "
            "catalogue the engine evaluates, so the published policy and the "
            "enforced policy cannot diverge."
        ),
        "transitions": list(TRANSITION_IDS),
        "severity_weights": dict(SEVERITY_WEIGHTS),
        "gates": gates,
        "summary": catalogue_summary(),
    }


def promotion_policy_document() -> Dict[str, Any]:
    return {
        "policy_version": "v32-promotion-policy-1.0.0",
        "state_machine_version": STATE_MACHINE_VERSION,
        "evidence_mode_policy_version": EVIDENCE_MODE_POLICY_VERSION,
        "scoring_version": SCORING_VERSION,
        "engine_version": ENGINE_VERSION,
        "states": [state.value for state in PROMOTION_ORDER],
        "tracks": {
            track.value: (
                "governs actual bank authorisation"
                if track.value == "REAL"
                else "proves the promotion machinery works"
            )
            for track in TRACKS
        },
        "evidence_modes": {
            mode.value: {
                "bank_evidence_weight": bank_evidence_weight(mode),
                "admissible_on_real_track": mode.value != "SYNTHETIC_REHEARSAL",
            }
            for mode in EVIDENCE_MODES
        },
        "capabilities": {
            capability.value: {
                "minimum_state": CAPABILITY_STATE_THRESHOLD[capability].value,
                "required_real_gates": sorted(
                    EVIDENCE_PREREQUISITES.get(capability, frozenset())
                ),
                "permanently_withheld": capability in PERMANENTLY_WITHHELD,
            }
            for capability in CAPABILITIES
        },
        "scoring": {
            "promotion_machinery_readiness": (
                "rehearsal track; synthetic evidence counts, because the "
                "question is whether the machinery works"
            ),
            "bank_evidence_readiness": (
                "real track; synthetic evidence contributes zero, because the "
                "question is whether the bank has the evidence"
            ),
            "composite_prohibited": (
                "No single promotability figure is published. A composite would "
                "let a working rehearsal read as progress toward production."
            ),
        },
        "events": {
            "events_version": EVENTS_VERSION,
            "topics": list(declared_topics()),
            "event_types": [item.value for item in PROMOTION_EVENT_TYPES],
            "note": (
                "Every promotion event carries its track, so an audit reader can "
                "tell a rehearsal event from a real one without resolving "
                "anything else. Adding this topic required widening a hardcoded "
                "CHECK constraint in the Postgres outbox, which would otherwise "
                "have failed at insert time in production."
            ),
        },
        "legacy_vocabulary_unified": {
            "sources": [
                "src/wallet_twin_v2/release_gates.py",
                "config/mlflow_promotion_policy.json",
            ],
            "aliases_mapped": sum(
                len(aliases) for aliases in LEGACY_GATE_ALIASES.values()
            ),
            "note": (
                "The MLflow policy declared two transitions and was never parsed "
                "by any code. Its gate ids are preserved here as aliases so "
                "earlier artifacts remain traceable."
            ),
        },
    }


def signing_posture_document() -> Dict[str, Any]:
    """What can actually sign here, and what merely has an adapter.

    Listing three signers without saying which ran would let a reader assume
    all three were exercised. The local rehearsal signer works and is tested in
    CI; Sigstore needs an ambient GitHub OIDC token; KMS needs a live AWS
    account and a new ECDSA key, because the existing Terraform key is RSA-3072.
    """
    report = signer_capability_report()
    return {
        **report,
        "canonicalisation": {
            "signing": JCS_VERSION,
            "reproducibility": "wallet_twin_v2.canonical",
            "note": (
                "Separate on purpose. canonical.py rounds floats to the "
                "published precision and emits indented JSON, both of which are "
                "correct for byte-reproducible artifacts and disqualifying for a "
                "signature: signing a rounded payload signs a different number "
                "than the one published."
            ),
        },
        "envelope": {"format": DSSE_VERSION, "payload_type": PAYLOAD_TYPE},
        "trust_registry_version": TRUST_REGISTRY_VERSION,
        "enforcement": [
            "A rehearsal key cannot sign REAL_BANK or BANK_ATTESTED evidence.",
            "A key with real-bank authority cannot sit in the rehearsal trust domain.",
            "A bank trust root is refused in a FIXTURE environment.",
            "Expired, not-yet-valid and revoked keys all fail closed.",
            "An unknown key is not verified by absence.",
        ],
        "bank_signing_status": (
            "NO_REAL_BANK_SIGNING_CAPABILITY_ON_THIS_BUILD"
            if not report["real_bank_signing_available"]
            else "REAL_BANK_SIGNING_AVAILABLE"
        ),
    }


def main() -> int:
    for name, model in MODELS.items():
        write_canonical_json(
            SCHEMAS / f"{name}.schema.json", model.model_json_schema()
        )

    write_canonical_json(CONTRACTS / "promotion-gate-catalogue.json", gate_catalogue_document())
    write_canonical_json(OUTPUTS / "v32_promotion_policy.json", promotion_policy_document())
    write_canonical_json(OUTPUTS / "v32_signing_posture.json", signing_posture_document())

    # Canonical-tier laboratory results. Deterministic by construction: fixed
    # seeds, CPU-only, and a fixed artifact timestamp, so the byte-reproducibility
    # gate covers them like any other committed artifact.
    laboratories = run_all(as_of=ARTIFACT_AS_OF, replications=200, seed=20260630)
    write_canonical_json(OUTPUTS / "v32_simulation_laboratories.json", laboratories)

    print(
        f"exported {len(MODELS)} V3.2 schemas, "
        f"{len(GATE_CATALOGUE)} gates across {len(TRANSITION_IDS)} transitions, "
        f"{len(laboratories['laboratory_versions'])} laboratories"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
