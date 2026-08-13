from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.evidence_qa import write_review_pack
from wallet_twin_v2.experiment_analysis import run_trial_rehearsal
from wallet_twin_v2.genai_eval import evaluate_golden_set
from wallet_twin_v2.offline_lab import run_offline_lab
from wallet_twin_v2.operational_validation import run_operational_rehearsal
from wallet_twin_v2.runtime_config import RuntimeConfig
from wallet_twin_v2.production_target import write_production_target_report
from wallet_twin_v2.canonical import artifact_timestamp


def main() -> None:
    output_dir = ROOT / "outputs" / "v2_validation"
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence = write_review_pack(output_dir)
    offline = run_offline_lab(include_history=True)
    genai = evaluate_golden_set()
    trial = run_trial_rehearsal()
    operational = run_operational_rehearsal()
    fixture_config = RuntimeConfig.from_env({"WALLET_DEPLOYMENT_MODE": "FIXTURE"}).validate()
    controlled_fail_closed = RuntimeConfig.from_env({"WALLET_DEPLOYMENT_MODE": "PRODUCTION"}).validate()
    production_target = write_production_target_report(output_dir / "production_target_validation.json")

    reports = {
        "offline_validation_report.json": offline,
        "genai_golden_eval.json": genai,
        "trial_rehearsal.json": trial,
        "operational_rehearsal.json": operational,
    }
    for filename, payload in reports.items():
        (output_dir / filename).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    scorecard = {
        "version": "production-candidate-scorecard-1.0.0",
        "generated_at": artifact_timestamp(),
        "status": "BANK_PRODUCTION_CANDIDATE_NOT_PROMOTABLE",
        "claim": "Maximum offline production-candidate maturity; bank-dependent release gates remain explicit.",
        "scores": {
            "public_evidence": {"score": 8.5, "basis": "82 E1 facts across 20 clients; 51/51 expanded facts page-grounded; four-eyes SME approval pending"},
            "wallet_modelling": {"score": 8.0, "basis": "product models, selection weighting, known-truth holdout, split-conformal and stress audits; no representative real E3 panel"},
            "economics": {"score": 7.5, "basis": "fail-closed engine, three E0 packs, waterfalls, frontiers, break-even, concentration and reconciliation; no bank-approved rates"},
            "timing": {"score": 7.0, "basis": "30/60/90 baseline plus temporally held-out discrete-time surrogate hazard challenger; no qualified RM outcomes"},
            "causal_learning": {"score": 6.5, "basis": "locked preregistration, cluster-robust ITT, randomization inference, IV gate, A/A rehearsal and event contracts; no live randomized trial"},
            "genai": {"score": 8.5, "basis": f"three fail-closed adapters, circuit breaker, payload guard, claim compiler and {genai['governed_evaluation_checks']} governed checks; no approved live-provider run"},
            "platform_security": {"score": 8.0, "basis": "AWS/Databricks IaC, runtime fail-closed config, production adapters, ABAC, hardened Helm, load/negative/recovery rehearsals; no bank infrastructure validation"},
            "rm_adoption": {"score": 4.0, "basis": "consented pilot sessions, task feedback and adoption gate implemented; zero real completed banker sessions"},
        },
        "machine_gates": {
            "evidence_documents": f"{evidence['document_passes']}/{evidence['documents']}",
            "evidence_facts": f"{evidence['fact_passes']}/{evidence['facts']}",
            "wallet_conformal_coverage_90": offline["synthetic_calibration"]["split_conformal_audit"]["wallet"]["conformal_coverage_90"],
            "timing_challenger_brier_improvement": offline["historical_validation"]["timing_surrogate"]["discrete_time_challenger"]["brier_improvement"],
            "genai_governed_checks": genai["governed_evaluation_checks"],
            "genai_deterministic_gate": genai["release_gate"]["passed"],
            "entitlement_negative_pass_rate": operational["entitlements"]["pass_rate"],
            "local_p95_latency_ms": operational["load"]["latency_ms"]["p95"],
            "event_recovery_byte_identical": operational["recovery"]["byte_identical"],
            "production_runtime_fails_closed_without_bank_config": controlled_fail_closed["fail_closed"],
            "production_target_control_definitions": f"{production_target['controls_passed']}/{production_target['controls_total']}",
        },
        "fixture_runtime": fixture_config,
        "controlled_runtime_without_bank_config": controlled_fail_closed,
        "non_delegable_gates": [
            "finance-SME and independent approval of pending E1 facts",
            "representative, consented E3 multibank calibration panel",
            "approved Treasury/Product Finance/FTP/risk/capital/cost/hurdle inputs",
            "bank SSO, Unity Catalog, SIEM, network and infrastructure validation",
            "bank-approved live-provider evaluation on sealed independently adjudicated documents",
            "at least five supervised RM pilot sessions and a powered live randomized trial",
            "30 elapsed clean production shadow days",
        ],
        "production_release_allowed": False,
    }
    (output_dir / "production_candidate_scorecard.json").write_text(
        json.dumps(scorecard, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"status": scorecard["status"], "scores": scorecard["scores"], "machine_gates": scorecard["machine_gates"]}, indent=2))


if __name__ == "__main__":
    main()
