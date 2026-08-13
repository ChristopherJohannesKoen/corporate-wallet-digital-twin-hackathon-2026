"""V3.1.1 regression boundary — V3.2 must be additive.

The Promotion Readiness Twin is a claim about governance, not about wallet
estimation. If adding it moves a wallet number, an evidence count, or a release
status, the "additive" claim is false and these tests say so.

Regenerate deliberately with ``python scripts/freeze_v311_boundary.py`` only when
a V3.1.1 change is intended and reviewed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from freeze_v311_boundary import additive_api_drift, build_boundary  # noqa: E402

BOUNDARY = Path(__file__).with_name("v3_1_1_boundary.json")


@pytest.fixture(scope="module")
def frozen() -> dict:
    return json.loads(BOUNDARY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def current() -> dict:
    return build_boundary()


def test_boundary_declares_its_version(frozen: dict) -> None:
    assert frozen["boundary_version"] == "v3.1.1-regression-boundary-1.1.0"
    assert frozen["solution_version"] == "3.1.1"


def test_every_v311_api_path_and_schema_survives_unchanged(frozen: dict) -> None:
    """The composed OpenAPI documents are checked additively.

    Byte-freezing a document whose whole job is to compose new surfaces would
    make every additive API change a violation, and the boundary would be
    re-frozen every release until it meant nothing. What must hold is narrower
    and stronger: each path and schema V3.1.1 published is still present and
    identical. Additions are what V3.2 is permitted to do.
    """
    drift = additive_api_drift(frozen["additive_api_documents"])
    assert not drift, f"V3.1.1 API surface changed, not merely extended: {drift}"


def test_the_v311_api_surface_was_actually_captured(frozen: dict) -> None:
    """A guard against the additive check silently covering nothing.

    Exact counts, not a threshold: V3.1.1 published 48 paths and 25 component
    schemas. If a future refactor drops half of them out of the frozen record,
    the additive check would still pass over what remained and report nothing.
    """
    documents = frozen["additive_api_documents"]
    assert set(documents) == {"contracts/openapi.json", "contracts/openapi-v31.json"}
    for relative_path, surface in documents.items():
        assert len(surface["paths"]) == 48, relative_path
        assert len(surface["schemas"]) == 25, relative_path


def test_v32_extended_the_api_rather_than_replacing_it(current: dict) -> None:
    """The positive half: the promotion routes are present *in addition*."""
    from freeze_v311_boundary import api_surface

    live = api_surface("contracts/openapi.json")
    promotion = [path for path in live["paths"] if path.startswith("/v3/promotion")]
    assert len(promotion) == 12
    assert len(live["paths"]) == 48 + 12


def test_evidence_surface_is_unchanged(frozen: dict, current: dict) -> None:
    """The wallet grid and its evidence partition are what V3.2 must not touch."""
    assert current["evidence"] == frozen["evidence"]


def test_policy_versions_are_unchanged(frozen: dict, current: dict) -> None:
    assert current["policy_versions"] == frozen["policy_versions"]


def test_release_status_is_unchanged(frozen: dict, current: dict) -> None:
    assert current["release"] == frozen["release"]
    assert current["release"]["bank_production_status"] == "NOT_PROMOTABLE"


def test_live_provider_evidence_is_reported_honestly(frozen: dict, current: dict) -> None:
    """Accepted runs may rise when credentials arrive; they may never be invented.

    A rise is a real re-run and is expected to require regenerating this boundary.
    A fall would mean evidence was lost again, which is what the write guard in
    ``run_live_provider_eval.py`` exists to prevent.
    """
    frozen_accepted = frozen["genai"]["live_provider_accepted_runs"]
    current_accepted = current["genai"]["live_provider_accepted_runs"]
    assert current_accepted >= frozen_accepted, (
        f"accepted live-provider runs fell from {frozen_accepted} to {current_accepted}; "
        "evidence was overwritten"
    )
    assert current["genai"]["live_provider_target_runs"] == 9
    if current_accepted == 0:
        assert current["genai"]["submission_gate_passed"] is False


def test_gated_artifacts_have_not_drifted(frozen: dict, current: dict) -> None:
    drifted = sorted(
        path
        for path, digest in frozen["gated_artifact_digests"].items()
        if current["gated_artifact_digests"].get(path) != digest
    )
    assert not drifted, "V3.1.1 gated artifacts drifted:\n  " + "\n  ".join(drifted[:15])


def test_boundary_states_what_was_not_established(frozen: dict) -> None:
    """A boundary listing only successes cannot detect a later overclaim."""
    open_items = frozen["not_established_at_this_boundary"]
    assert len(open_items) >= 6
    joined = " ".join(open_items).lower()
    for term in ("e3", "finance-sme", "economics", "live-provider", "shadow", "causal"):
        assert term in joined, f"boundary does not record the open {term} gate"
