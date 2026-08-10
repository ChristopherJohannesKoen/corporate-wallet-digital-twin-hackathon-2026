from __future__ import annotations

import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import norm


PREREGISTRATION = {
    "version": "rm-encouragement-preregistration-1.0.0",
    "unit_of_randomization": "RM team",
    "treatment": "encouragement to use an eligible wallet recommendation",
    "primary_outcome": "qualified RM action within 30 days of eligibility",
    "primary_estimand": "intention-to-treat risk difference",
    "secondary_estimand": "Wald treatment-on-treated only with first-stage >= 0.10",
    "horizons_days": [30, 60, 90],
    "exclusions": ["ineligible at assignment", "test accounts", "withdrawn client consent"],
    "censoring": "inverse-probability weighting when outcome ascertainment is incomplete",
    "analysis": "cluster-robust ITT, randomization inference, covariate balance, first-stage diagnostic",
    "causal_label_gate": "independent validation plus adequate overlap/effective sample size",
}


def preregistration_manifest() -> dict:
    canonical = json.dumps(PREREGISTRATION, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {**PREREGISTRATION, "sha256": hashlib.sha256(canonical).hexdigest(), "locked": True}


class ExperimentAnalyzer:
    """Pre-registered cluster-randomized encouragement analysis.

    The implementation is production-shaped but remains claim-ineligible until
    populated with real, reconciled eligibility and outcome events.
    """

    @staticmethod
    def _cluster_robust_itt(frame: pd.DataFrame) -> dict:
        observed = frame[frame["observed"].astype(bool)].copy()
        x = np.column_stack([np.ones(len(observed)), observed.assignment.to_numpy(dtype=float)])
        y = observed.outcome.to_numpy(dtype=float)
        beta = np.linalg.pinv(x.T @ x) @ x.T @ y
        residual = y - x @ beta
        bread = np.linalg.pinv(x.T @ x)
        meat = np.zeros((2, 2))
        clusters = observed.cluster.unique()
        for cluster in clusters:
            mask = observed.cluster.eq(cluster).to_numpy()
            score = x[mask].T @ residual[mask]
            meat += np.outer(score, score)
        cluster_count = len(clusters)
        correction = cluster_count / max(cluster_count - 1, 1) * (len(observed) - 1) / max(len(observed) - 2, 1)
        variance = correction * bread @ meat @ bread
        standard_error = float(math.sqrt(max(variance[1, 1], 0.0)))
        effect = float(beta[1])
        z = effect / standard_error if standard_error > 0 else 0.0
        return {
            "estimate": effect,
            "cluster_robust_se": standard_error,
            "ci95": [effect - 1.96 * standard_error, effect + 1.96 * standard_error],
            "two_sided_p_value": float(2 * norm.sf(abs(z))),
            "clusters": cluster_count,
            "observations": len(observed),
        }

    @staticmethod
    def _randomization_inference(frame: pd.DataFrame, draws: int, seed: int) -> dict:
        rng = np.random.default_rng(seed)
        observed = frame[frame.observed.astype(bool)]
        cluster_assignment = observed.groupby("cluster").assignment.first()
        clusters = cluster_assignment.index.to_numpy()
        treated_count = int(cluster_assignment.sum())
        actual = float(observed.groupby("assignment").outcome.mean().diff().iloc[-1])
        permuted = []
        for _ in range(draws):
            treated = set(rng.choice(clusters, treated_count, replace=False))
            assignment = observed.cluster.isin(treated).astype(int)
            rates = observed.assign(_assignment=assignment).groupby("_assignment").outcome.mean()
            permuted.append(float(rates.get(1, 0.0) - rates.get(0, 0.0)))
        p_value = (1 + sum(abs(value) >= abs(actual) for value in permuted)) / (draws + 1)
        return {"draws": draws, "two_sided_p_value": float(p_value), "seed": seed}

    @staticmethod
    def _balance(frame: pd.DataFrame, covariates: Iterable[str]) -> dict:
        results = {}
        for covariate in covariates:
            treated = frame.loc[frame.assignment.eq(1), covariate].astype(float)
            control = frame.loc[frame.assignment.eq(0), covariate].astype(float)
            pooled = math.sqrt((treated.var(ddof=1) + control.var(ddof=1)) / 2) if len(treated) > 1 and len(control) > 1 else 0.0
            smd = float((treated.mean() - control.mean()) / pooled) if pooled > 0 else 0.0
            results[covariate] = {"standardized_mean_difference": smd, "passes_0_10": abs(smd) <= 0.10}
        return results

    def analyze(
        self,
        frame: pd.DataFrame,
        *,
        covariates: Iterable[str] = (),
        permutation_draws: int = 2_000,
        seed: int = 20260809,
        data_classification: str = "REAL_RECONCILED_EVENTS",
    ) -> dict:
        required = {"cluster", "assignment", "exposure", "outcome", "observed"}
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError("missing experiment fields: " + ", ".join(missing))
        if frame.cluster.nunique() < 4 or frame.assignment.nunique() != 2:
            raise ValueError("analysis requires at least four clusters and both assignment arms")
        itt = self._cluster_robust_itt(frame)
        observed = frame[frame.observed.astype(bool)]
        exposure = observed.groupby("assignment").exposure.mean()
        first_stage = float(exposure.get(1, 0.0) - exposure.get(0, 0.0))
        wald = itt["estimate"] / first_stage if abs(first_stage) >= 0.10 else None
        effective_sample_size = float(len(observed) ** 2 / max(np.sum(np.ones(len(observed)) ** 2), 1))
        real_data = data_classification == "REAL_RECONCILED_EVENTS"
        return {
            "analysis_version": "cluster-encouragement-analysis-1.0.0",
            "preregistration": preregistration_manifest(),
            "data_classification": data_classification,
            "itt": itt,
            "first_stage": first_stage,
            "weak_instrument": abs(first_stage) < 0.10,
            "wald_treatment_on_treated": wald,
            "randomization_inference": self._randomization_inference(frame, permutation_draws, seed),
            "covariate_balance": self._balance(frame, covariates),
            "censoring_rate": float(1 - frame.observed.astype(float).mean()),
            "effective_sample_size": effective_sample_size,
            "causal_claim_allowed": bool(real_data and abs(first_stage) >= 0.10 and itt["clusters"] >= 24),
            "label": "CAUSAL" if real_data and abs(first_stage) >= 0.10 and itt["clusters"] >= 24 else "REHEARSAL_ONLY",
        }


def run_trial_rehearsal(seed: int = 20260809) -> dict:
    rng = np.random.default_rng(seed)
    records = []
    cluster_count, opportunities_per_cluster = 48, 24
    assignments = np.repeat(rng.permutation([0, 1] * (cluster_count // 2)), opportunities_per_cluster)
    for index, assignment in enumerate(assignments):
        cluster = index // opportunities_per_cluster
        baseline_score = rng.normal()
        exposure = int(rng.random() < (0.64 if assignment else 0.11))
        outcome_probability = float(expit(-1.52 + 0.32 * exposure + 0.08 * baseline_score))
        records.append({
            "cluster": f"TEAM-{cluster:03d}", "assignment": int(assignment), "exposure": exposure,
            "outcome": int(rng.random() < outcome_probability), "observed": int(rng.random() >= 0.10),
            "baseline_score": baseline_score,
        })
    frame = pd.DataFrame(records)
    analysis = ExperimentAnalyzer().analyze(
        frame, covariates=("baseline_score",), permutation_draws=1_000, seed=seed,
        data_classification="SYNTHETIC_OPERATIONAL_REHEARSAL",
    )

    # A/A diagnostic: assignment must not create a mechanical effect when the
    # outcome generator is independent of assignment and exposure.
    aa = frame.copy()
    aa["outcome"] = (rng.random(len(aa)) < 0.18).astype(int)
    aa_analysis = ExperimentAnalyzer().analyze(
        aa, covariates=("baseline_score",), permutation_draws=500, seed=seed + 1,
        data_classification="SYNTHETIC_AA_REHEARSAL",
    )
    return {
        "status": "PRODUCTION_ANALYSIS_REHEARSED_WITH_SYNTHETIC_EVENTS",
        "production_claim_allowed": False,
        "event_records": len(frame),
        "analysis": analysis,
        "aa_diagnostic": {
            "itt_estimate": aa_analysis["itt"]["estimate"],
            "randomization_p_value": aa_analysis["randomization_inference"]["two_sided_p_value"],
            "passes_no_mechanical_effect": abs(aa_analysis["itt"]["estimate"]) < 0.05,
        },
        "remaining_gate": "powered live cluster-randomized trial with reconciled RM actions and outcomes",
    }


@dataclass
class PilotStore:
    sessions: Dict[str, dict] = field(default_factory=dict)
    feedback: List[dict] = field(default_factory=list)

    def start(
        self, rm_id: str, team_id: str, task_ids: List[str], started_at: datetime,
        *, consent_reference: str, real_participant: bool,
    ) -> dict:
        session_id = f"PILOT-{uuid.uuid4()}"
        state = {
            "session_id": session_id, "rm_id": rm_id, "team_id": team_id,
            "task_ids": task_ids, "started_at": started_at.astimezone(timezone.utc).isoformat(),
            "consent_reference_hash": hashlib.sha256(consent_reference.encode("utf-8")).hexdigest(),
            "status": "IN_PROGRESS", "real_participant": real_participant,
        }
        self.sessions[session_id] = state
        return state

    def record_feedback(self, session_id: str, payload: dict) -> dict:
        if session_id not in self.sessions:
            raise KeyError(session_id)
        record = {"session_id": session_id, "recorded_at": datetime.now(timezone.utc).isoformat(), **payload}
        self.feedback.append(record)
        expected = set(self.sessions[session_id]["task_ids"])
        completed = {item["task_id"] for item in self.feedback if item["session_id"] == session_id and item.get("completed")}
        if expected and expected.issubset(completed):
            self.sessions[session_id]["status"] = "COMPLETED"
        return record

    def readiness(self) -> dict:
        completed_sessions = [
            item for item in self.sessions.values()
            if item["status"] == "COMPLETED" and item["real_participant"]
        ]
        real_session_ids = {item["session_id"] for item in self.sessions.values() if item["real_participant"]}
        ratings = [item for item in self.feedback if item.get("completed") and item["session_id"] in real_session_ids]
        return {
            "pilot_sessions": len(self.sessions),
            "real_participant_sessions": len(real_session_ids),
            "completed_sessions": len(completed_sessions),
            "feedback_records": len(self.feedback),
            "median_verification_seconds": float(np.median([item["verification_seconds"] for item in ratings])) if ratings else None,
            "mean_actionability": float(np.mean([item["actionability"] for item in ratings])) if ratings else None,
            "mean_comprehension": float(np.mean([item["comprehension"] for item in ratings])) if ratings else None,
            "omissions": sum(bool(item.get("omission_found")) for item in ratings),
            "overrides": sum(bool(item.get("override")) for item in ratings),
            "adoption_claim_allowed": len(completed_sessions) >= 5,
            "release_gate": "OPEN" if len(completed_sessions) >= 5 else "BLOCKED_MINIMUM_FIVE_COMPLETED_RM_SESSIONS",
        }
