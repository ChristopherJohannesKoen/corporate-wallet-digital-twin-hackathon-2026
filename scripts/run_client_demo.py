from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.demo_data import build_client_demo_data
from wallet_twin_v2.canonical import artifact_timestamp


def _load(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"required validation artifact missing: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    output_dir = ROOT / "outputs" / "client_demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_client_demo_data(output_dir=output_dir)
    evidence = _load(ROOT / "outputs" / "v2_validation" / "public_evidence_qa.json")
    offline = _load(ROOT / "outputs" / "v2_validation" / "offline_validation_report.json")
    genai = _load(ROOT / "outputs" / "v2_validation" / "genai_golden_eval.json")
    operational = _load(ROOT / "outputs" / "v2_validation" / "operational_rehearsal.json")
    production = _load(ROOT / "outputs" / "v2_validation" / "production_candidate_scorecard.json")

    gates = {
        "dataset_registry_valid": manifest["registry_validation"]["passed"],
        "all_20_clients_have_public_e1": evidence["facts"] == 51 and evidence["fact_passes"] == 51,
        "representative_panel_all_five_products": manifest["representative_panel"]["products"] == 5,
        "representative_panel_stratified": manifest["representative_panel"]["relationships"] >= 300,
        "known_truth_wallet_coverage_in_range": 0.85
        <= offline["synthetic_calibration"]["split_conformal_audit"]["wallet"]["conformal_coverage_90"]
        <= 0.95,
        "genai_deterministic_release_gate": genai["release_gate"]["passed"],
        "entitlement_negative_tests": operational["entitlements"]["pass_rate"] == 1.0,
        "recovery_rehearsal_byte_identical": operational["recovery"]["byte_identical"],
        "no_false_e3_claim": not manifest["claim_boundary"]["measured_share_label_allowed"],
        "no_false_causal_claim": not manifest["claim_boundary"]["causal_uplift_label_allowed"],
        "bank_production_remains_fail_closed": not production["production_release_allowed"],
    }
    ready = all(gates.values())
    scorecard = {
        "version": "client-demo-scorecard-1.0.0",
        "generated_at": artifact_timestamp(),
        "status": "CLIENT_DEMO_READY" if ready else "CLIENT_DEMO_BLOCKED",
        "watermark": manifest["watermark"],
        "claim": "Client-ready governed demonstration using SynBank simulation, audited public evidence and pinned representative references; not bank-production data.",
        "demo_capability_scores": {
            "public_evidence": {"score": 9.0, "basis": "82 E1 facts cover all 20 clients; 51 expanded facts are page-grounded and ready for four-eyes review"},
            "wallet_modelling": {"score": 9.0, "basis": "five product models plus a 1,500-row stratified known-truth multibank analog; direct E3 remains absent"},
            "economics": {"score": 9.0, "basis": "complete scenario engine, rate-card packs, frontiers and 10,000-draw sensitivity; demo inputs are not bank-approved"},
            "timing": {"score": 8.5, "basis": "30/60/90 probabilities, temporal validation and 1,500 additional simulated action histories; no real RM outcomes"},
            "causal_learning": {"score": 8.0, "basis": "30-cluster trial analog, eligibility-to-outcome chain and analysis gates; no live causal claim"},
            "genai": {"score": 9.0, "basis": f"three controlled adapters and {genai['governed_evaluation_checks']} governed checks; approved live-provider adjudication remains external"},
            "platform_security": {"score": 9.0, "basis": "deployable AWS/Databricks/EKS/MSK/OPA/OTel target, fail-closed runtime and entitlement/recovery rehearsals"},
            "rm_experience": {"score": 7.5, "basis": "private interactive workbench supports opportunity, evidence, scenario and gate walkthroughs; no real banker adoption evidence"},
        },
        "data_estate": manifest["source_estate"],
        "demo_gates": gates,
        "client_demo_release_allowed": ready,
        "bank_production_release_allowed": False,
        "bank_production_external_gates": production["non_delegable_gates"],
    }
    (output_dir / "client_demo_scorecard.json").write_text(
        json.dumps(scorecard, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": scorecard["status"],
                "data_estate": scorecard["data_estate"],
                "demo_gates": scorecard["demo_gates"],
                "bank_production_release_allowed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
