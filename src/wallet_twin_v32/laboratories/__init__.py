"""Seven simulation laboratories.

Each answers a question the bank would ask before promoting the system, and
each states in its own report what it does **not** establish. That second part
matters more than the first: a laboratory that produces a number without saying
what the number cannot support is how a rehearsal gets mistaken for evidence.

======================================  ==========================================
Laboratory                              Question
======================================  ==========================================
``calibration``                         Are the intervals calibrated at 50/80/90%?
``sample_size``                         How many E3 clients would be needed?
``economics``                           Do the value components reconcile?
``timing``                              Does timing generalise to unseen clients?
``causal_operating_characteristics``    Does the trial design control Type I and
                                        have power?
``feasibility_sweep``                   Do the feasibility gates actually bite?
``rm_personas``                         Where does the workbench create friction?
======================================  ==========================================

All seven produce ``SYNTHETIC_REHEARSAL`` evidence. None can satisfy a
real-track gate — that is enforced by the mode algebra, not by convention.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

from wallet_twin_v2.genai_eval import promotion_genai_readiness_suite

from .calibration import (
    CALIBRATION_LAB_VERSION,
    audit_coverage,
    calibration_report,
)
from .causal_operating_characteristics import (
    CAUSAL_OC_LAB_VERSION,
    causal_report,
    operating_characteristics,
    trial_design_report,
    weak_instrument_behaviour,
)
from .compute import (
    CANONICAL_TIERS,
    COMPUTE_VERSION,
    NIGHTLY_TIERS,
    compute_report,
    gpu_available,
    map_replications,
    worker_count,
)
from .e3_panel import E3_PANEL_LAB_VERSION, panel_report
from .economics import ECONOMICS_LAB_VERSION, portfolio_economics_report, reconcile
from .feasibility_sweep import (
    FEASIBILITY_SWEEP_VERSION,
    sweep_feasibility_injections,
    sweep_report,
)
from .rm_personas import (
    PERSONAS,
    RM_PERSONA_LAB_VERSION,
    TASKS,
    persona_report,
    real_sessions,
    simulate_sessions,
)
from .sample_size import (
    SAMPLE_SIZE_LAB_VERSION,
    plan_e3_readiness_sample_size,
    plan_e3_sample_size,
    plan_report,
    wilson_interval,
)
from .timing import TIMING_LAB_VERSION, evaluate_splits, hazard_recovery_report, timing_report

LABORATORIES_VERSION = "v32-simulation-laboratories-1.0.0"

LABORATORY_VERSIONS = {
    "calibration": CALIBRATION_LAB_VERSION,
    "sample_size": SAMPLE_SIZE_LAB_VERSION,
    "economics": ECONOMICS_LAB_VERSION,
    "timing": TIMING_LAB_VERSION,
    "causal_operating_characteristics": CAUSAL_OC_LAB_VERSION,
    "feasibility_sweep": FEASIBILITY_SWEEP_VERSION,
    "rm_personas": RM_PERSONA_LAB_VERSION,
    "synthetic_e3_panel": E3_PANEL_LAB_VERSION,
    "genai_readiness": "v32-genai-bank-readiness-1.0.0",
}


def run_all(
    *,
    as_of: date,
    replications: int = 200,
    seed: int = 20260630,
) -> Dict[str, Any]:
    """Run every canonical-tier laboratory and return one report.

    Tier sizes are the canonical ones: small enough that the build stays fast
    and every artifact reproduces byte-identically on a CI runner without a GPU.
    """
    plan, points = plan_e3_sample_size(as_of=as_of, replications=500, seed=seed)
    coverage = audit_coverage(as_of=as_of, replications=240, seed=seed)
    causal_replications = 2_000
    characteristics = operating_characteristics(replications=causal_replications, seed=seed)
    sessions = simulate_sessions(as_of=as_of, seed=seed)

    return {
        "laboratories_version": LABORATORIES_VERSION,
        "as_of": as_of.isoformat(),
        "laboratory_versions": dict(LABORATORY_VERSIONS),
        "compute": compute_report(),
        "calibration": calibration_report(coverage),
        "synthetic_e3_panel": panel_report(as_of=as_of, seed=seed),
        "sample_size": plan_report(plan, points),
        "e3_sample_size_readiness": plan_e3_readiness_sample_size(
            as_of=as_of, replications=500, seed=seed
        ),
        "economics": portfolio_economics_report(samples=10_000, seed=seed),
        "timing": {
            **timing_report(evaluate_splits(seed=seed), as_of),
            "hazard_recovery": hazard_recovery_report(as_of=as_of, seed=seed),
        },
        "causal_operating_characteristics": causal_report(
            characteristics, weak_instrument_behaviour(seed=seed), causal_replications
        ),
        "causal_trial_design": trial_design_report(replications=2_000, seed=seed),
        "feasibility_sweep": sweep_report(sweep_feasibility_injections()),
        "rm_personas": persona_report(sessions),
        "genai_readiness": promotion_genai_readiness_suite(),
        "what_none_of_this_establishes": [
            "No E3 multibank observation exists; competitor share stays unmeasurable.",
            "No bank-approved economics; no money value may be attached.",
            "No real RM session; adoption remains zero.",
            "No trial was run; causal value stays null.",
            "Every laboratory produces SYNTHETIC_REHEARSAL evidence, which the "
            "mode algebra refuses on the real track.",
        ],
    }


__all__ = [
    "CANONICAL_TIERS",
    "COMPUTE_VERSION",
    "LABORATORIES_VERSION",
    "LABORATORY_VERSIONS",
    "NIGHTLY_TIERS",
    "PERSONAS",
    "TASKS",
    "audit_coverage",
    "calibration_report",
    "causal_report",
    "compute_report",
    "evaluate_splits",
    "gpu_available",
    "map_replications",
    "operating_characteristics",
    "panel_report",
    "persona_report",
    "plan_e3_sample_size",
    "plan_e3_readiness_sample_size",
    "plan_report",
    "real_sessions",
    "reconcile",
    "portfolio_economics_report",
    "run_all",
    "simulate_sessions",
    "sweep_feasibility_injections",
    "sweep_report",
    "timing_report",
    "hazard_recovery_report",
    "trial_design_report",
    "weak_instrument_behaviour",
    "wilson_interval",
    "worker_count",
]
