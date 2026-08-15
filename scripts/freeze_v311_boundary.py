"""Freeze V3.1.1 as the regression boundary V3.2 builds on.

V3.2 adds a Promotion Readiness Twin *alongside* the Wallet and Decision Twins.
"Alongside" is only a meaningful claim if there is a recorded boundary to compare
against, so this captures what V3.1.1 actually produced — provenance, artifact
digests and the analytical surface — before any V3.2 code exists.

The record deliberately states what was **not** established as prominently as what
was. A boundary that only lists successes cannot be used to detect a later
regression in the things that were still open.

    python scripts/freeze_v311_boundary.py            # write the boundary
    python scripts/freeze_v311_boundary.py --check    # verify current state matches
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.artifacts import (  # noqa: E402
    NON_REPRODUCIBLE_DELIVERABLES,
    committed_artifacts,
)
from wallet_twin_v2.canonical import (  # noqa: E402
    CANONICALISATION_VERSION,
    DIGEST_PRECISION_VERSION,
    write_canonical_json,
)
from wallet_twin_v2.measurement_policy import MEASUREMENT_POLICY_VERSION  # noqa: E402
from wallet_twin_v2.public_evidence import ANCHOR_ACTIVATION_POLICY_VERSION  # noqa: E402

BOUNDARY = ROOT / "tests" / "regression" / "v3_1_1" / "v3_1_1_boundary.json"
BOUNDARY_VERSION = "v3.1.1-regression-boundary-1.2.0"

#: Composed API documents, checked **additively** rather than byte-exactly.
#:
#: These files are a composition of every registered router. Adding a new API
#: surface necessarily changes their bytes, so freezing them byte-exact would
#: make every additive change a boundary violation — the boundary would be
#: re-frozen on each release and would stop meaning anything.
#:
#: The invariant that actually matters is narrower and stronger: every path and
#: schema V3.1.1 published must still be present and **identical**. New ones are
#: permitted; changing or removing an existing one is not. That is precisely the
#: "additive" claim, tested directly instead of by proxy.
ADDITIVE_API_DOCUMENTS: tuple[str, ...] = (
    "contracts/openapi.json",
    "contracts/openapi-v31.json",
)

# V3.2 artifacts are deliberately excluded from the V3.1.1 byte boundary.
# The previous boundary accidentally captured early V3.2 files because it
# expanded the shared ``contracts`` and ``outputs`` directories after V3.2 had
# already been introduced.  That made an additive release impossible to
# evolve without appearing to mutate V3.1.1.
V32_ADDITIVE_ARTIFACT_PREFIXES: tuple[str, ...] = (
    "contracts/jsonschema/v32-",
    "contracts/promotion-gate-catalogue.json",
    "dashboard/app/data/promotion-fixture.json",
    "outputs/v32/",
)


def is_v32_additive_artifact(relative_path: str) -> bool:
    return any(relative_path.startswith(prefix) for prefix in V32_ADDITIVE_ARTIFACT_PREFIXES)


def git_value(*args: str, default: str = "UNKNOWN") -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    return completed.stdout.strip() if completed.returncode == 0 else default


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


#: The tag whose API surface the boundary describes.
BOUNDARY_TAG = "v3.1.1"


def _surface_of(document: Dict[str, Any]) -> Dict[str, Any]:
    """Paths and component schemas of a composed API document.

    Operation detail is included, so a changed request body or response schema
    on an existing path is caught. Only *additions* are invisible to this.
    """
    return {
        "paths": document.get("paths", {}),
        "schemas": document.get("components", {}).get("schemas", {}),
    }


def api_surface(relative_path: str) -> Dict[str, Any]:
    """The current API surface, from the working tree."""
    return _surface_of(
        json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    )


def api_surface_at_boundary_tag(relative_path: str) -> Dict[str, Any]:
    """The API surface as published at ``v3.1.1``.

    Read from the tag rather than from the working tree. Freezing the current
    tree would capture whatever surface exists at freeze time — including V3.2
    routes — and the record would stop describing V3.1.1, which is the one
    thing it is for. A missing tag fails loudly rather than silently falling
    back to the working tree.
    """
    completed = subprocess.run(
        ["git", "show", f"{BOUNDARY_TAG}:{relative_path}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise SystemExit(
            f"cannot read {relative_path} at tag {BOUNDARY_TAG}: "
            f"{completed.stderr.strip()}. The boundary describes the tagged "
            "release, so freezing from the working tree instead would silently "
            "record the wrong surface."
        )
    return _surface_of(json.loads(completed.stdout))


def additive_api_drift(frozen: Dict[str, Any]) -> Dict[str, list]:
    """Paths or schemas that V3.1.1 published and that have since changed.

    Returns removals and modifications only. A path present in the current
    document but not in the frozen one is an addition, which is what V3.2 is
    allowed to do.
    """
    drift: Dict[str, list] = {}
    for relative_path, recorded in frozen.items():
        current = api_surface(relative_path)
        removed = []
        changed = []
        for section in ("paths", "schemas"):
            for key, value in recorded.get(section, {}).items():
                if key not in current[section]:
                    removed.append(f"{section}:{key}")
                elif current[section][key] != value:
                    changed.append(f"{section}:{key}")
        if removed or changed:
            drift[relative_path] = sorted(removed + changed)
    return drift


def build_boundary() -> Dict[str, Any]:
    from wallet_twin_v2.fixtures import build_fixture

    fixture = build_fixture()
    opportunities = fixture["opportunities"]
    coverage = fixture["evidence_coverage"]

    providers_path = ROOT / "outputs" / "v2_validation" / "live_provider_comparison.json"
    providers = json.loads(providers_path.read_text(encoding="utf-8"))

    manifest_path = ROOT / "outputs" / "judging_manifest_v3.1.1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    gated = {
        path.relative_to(ROOT).as_posix(): sha256_of(path)
        for path in committed_artifacts()
        if path.relative_to(ROOT).as_posix() not in ADDITIVE_API_DOCUMENTS
        and not is_v32_additive_artifact(path.relative_to(ROOT).as_posix())
    }
    api_documents = {
        relative_path: api_surface_at_boundary_tag(relative_path)
        for relative_path in ADDITIVE_API_DOCUMENTS
    }

    return {
        "boundary_version": BOUNDARY_VERSION,
        "solution_version": "3.1.1",
        "purpose": (
            "The analytical and governance surface V3.2 must not perturb. V3.2 is "
            "additive: any change to these digests or counts is a breaking change to "
            "the V3.1.1 boundary and must be justified in review."
        ),
        "source": {
            # The commit whose surface was *measured*, which is necessarily the
            # parent of the commit that carries this file. `--check` deliberately
            # ignores it: the boundary is a claim about the analytical surface,
            # not about which commit recorded it, and the surface is expected to
            # survive commits that do not touch it.
            "measured_at_commit": git_value("rev-parse", "HEAD"),
            "branch": git_value("rev-parse", "--abbrev-ref", "HEAD"),
        },
        "policy_versions": {
            "anchor_activation": ANCHOR_ACTIVATION_POLICY_VERSION,
            "measurement": MEASUREMENT_POLICY_VERSION,
            "canonicalisation": CANONICALISATION_VERSION,
            "digest_precision": DIGEST_PRECISION_VERSION,
        },
        "evidence": {
            "total_source_facts": coverage["approved_e1_facts"] + coverage["pending_sme_facts"],
            "approved_source_facts": coverage["approved_e1_facts"],
            "pending_source_facts": coverage["pending_sme_facts"],
            "approved_anchor_clients": coverage["e1_clients"],
            "wallet_cells": len(opportunities),
            "approved_anchor_cells": sum(
                1 for item in opportunities if item.evidence_tier.value == "E1"
            ),
            "prior_led_cells": sum(
                1 for item in opportunities if item.evidence_tier.value == "E0"
            ),
        },
        "genai": {
            "live_provider_target_runs": providers["runs"],
            "live_provider_accepted_runs": providers["accepted_runs"],
            "live_provider_accepted_providers": providers["accepted_providers"],
            "submission_gate_passed": providers["submission_gate_passed"],
            "note": (
                "Zero accepted runs is the measured state, not a placeholder. A prior "
                "six-accepted evaluation was overwritten before it was committed and is "
                "unrecoverable; re-running requires fresh rotated credentials."
            ),
        },
        "release": {
            "submission_status": manifest["status"],
            "bank_production_status": manifest["bank_production_status"],
        },
        "gated_artifact_digests": gated,
        "additive_api_documents": api_documents,
        "non_reproducible_deliverables": dict(NON_REPRODUCIBLE_DELIVERABLES),
        "not_established_at_this_boundary": [
            "No E3 multibank observation; measured competitor share remains impossible.",
            "No finance-SME approval of the 51 pending public facts.",
            "No bank-approved economics beyond the five legacy rate cards.",
            "No accepted live-provider brief in the committed evidence.",
            "No real elapsed bank shadow day.",
            "No supervised RM pilot and no randomized trial; causal value stays null.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args()

    current = build_boundary()

    if args.check:
        if not BOUNDARY.exists():
            print(f"boundary missing: {BOUNDARY.relative_to(ROOT)}", file=sys.stderr)
            return 2
        frozen = json.loads(BOUNDARY.read_text(encoding="utf-8"))
        drifted = [
            key
            for key in ("evidence", "genai", "release", "policy_versions")
            if frozen.get(key) != current.get(key)
        ]
        digest_drift = sorted(
            path
            for path, digest in frozen.get("gated_artifact_digests", {}).items()
            if current["gated_artifact_digests"].get(path) != digest
        )
        api_drift = additive_api_drift(frozen.get("additive_api_documents", {}))
        if drifted or digest_drift or api_drift:
            print(
                json.dumps(
                    {
                        "status": "BOUNDARY_DRIFTED",
                        "sections": drifted,
                        "artifacts": digest_drift[:20],
                        "api_surface": api_drift,
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
            return 1
        print("V3.1.1 boundary intact")
        return 0

    write_canonical_json(BOUNDARY, current)
    print(f"froze V3.1.1 boundary to {BOUNDARY.relative_to(ROOT)}")
    print(
        json.dumps(
            {
                "measured_at_commit": current["source"]["measured_at_commit"][:12],
                "evidence": current["evidence"],
                "accepted_live_runs": current["genai"]["live_provider_accepted_runs"],
                "gated_artifacts": len(current["gated_artifact_digests"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
