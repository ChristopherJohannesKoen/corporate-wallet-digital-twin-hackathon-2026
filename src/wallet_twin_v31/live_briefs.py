"""Public-safe accepted provider brief projection for the V3.1 API.

The full comparative report is a judging artifact, not a runtime dependency.
This module reads the compact submission-truth projection copied into the
container.  It contains accepted narratives and audit metadata only: no secret,
request payload or confidential row-level data.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TRUTH_PATH = ROOT / "data/v2/submission_truth_v3.2.0.json"


@lru_cache(maxsize=1)
def submission_truth() -> dict[str, Any]:
    if not TRUTH_PATH.exists():
        return {
            "genai": {
                "accepted_runs": 0,
                "target_runs": 0,
                "showcase_briefs": {},
                "bank_authorized_live_genai": False,
            }
        }
    return json.loads(TRUTH_PATH.read_text(encoding="utf-8"))


def provider_brief_for_client(client_id: str) -> dict[str, Any] | None:
    return submission_truth()["genai"]["showcase_briefs"].get(client_id)


def live_evaluation_summary() -> dict[str, Any]:
    genai = submission_truth()["genai"]
    return {
        "evaluation_scope": genai["evaluation_scope"],
        "target_runs": genai["target_runs"],
        "runs": genai["runs"],
        "accepted_runs": genai["accepted_runs"],
        "blocked_runs": genai["blocked_runs"],
        "submission_gate_passed": genai["submission_gate_passed"],
        "accepted_providers": genai["accepted_providers"],
        "accepted_clients": genai["accepted_clients"],
        "bank_authorized_live_genai": genai["bank_authorized_live_genai"],
        "claim_boundary": genai["claim_boundary"],
    }

