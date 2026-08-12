"""Freeze the V3.0 analytical surface as an immutable V3.1 regression boundary.

V3.1.0 extends V3.0; it does not replace it.  This script captures a stable,
content-addressed digest of every V3.0 projection so that any later change to
the V3.1 decision layer that silently perturbs a V3.0 output is caught by
``tests/regression/v3_0/test_v3_0_frozen_surface.py``.

The frozen asset deliberately stores digests plus a small number of invariant
scalars rather than the full fixture: the full fixture is already reproducible
from the committed source, and storing digests keeps the regression boundary
readable in review.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v3.repository import repository as v3_repository  # noqa: E402

FROZEN = ROOT / "tests" / "regression" / "v3_0" / "v3_0_frozen_surface.json"


def _canonical(value: Any) -> Any:
    """Canonicalise the public V3.0 surface at its declared output precision.

    The committed V3 fixture serialises monetary and probability values to two
    decimals.  Hashing host-level binary floats more precisely would make the
    boundary fail after harmless NumPy/BLAS changes that are invisible on the
    published API.  Structural changes, labels, ranks and any displayed value
    change remain digest-breaking.
    """
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    if isinstance(value, float):
        return round(value, 2)
    return value


def digest(payload: Any) -> str:
    canonical = json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_frozen_surface() -> dict[str, Any]:
    opportunities = [item.model_dump(mode="json") for item in v3_repository.opportunities]
    shadows = {
        key: value.model_dump(mode="json")
        for key, value in v3_repository.shadow_reconstructions.items()
    }
    portfolio = v3_repository.action_portfolio.model_dump(mode="json")
    evidence_plan = v3_repository.evidence_acquisition.model_dump(mode="json")
    return {
        "frozen_version": "3.0.0",
        "boundary_policy": (
            "V3.1.0 is additive. Any change to these digests is a breaking change to the "
            "frozen V3.0 regression boundary and must be justified in review."
        ),
        "as_of": v3_repository.metadata["as_of"],
        "counts": {
            "opportunities": len(opportunities),
            "shadow_reconstructions": len(shadows),
            "treasury_graphs": len(v3_repository.treasury_graphs),
            "selected_actions": len(portfolio["selected_actions"]),
            "evidence_selected": len(evidence_plan["selected"]),
        },
        "invariants": {
            "capacity": portfolio["capacity"],
            "causal_status": portfolio["causal_status"],
            "commercial_status": portfolio["commercial_status"],
            "measured_competitor_share_claims": v3_repository.validation[
                "measured_competitor_share_claims"
            ],
            "causal_value_claims": v3_repository.validation["causal_value_claims"],
            "bank_production_status": v3_repository.release["bank_production_status"],
        },
        "digests": {
            "opportunities": digest(opportunities),
            "shadow_reconstructions": digest(shadows),
            "treasury_graphs": digest(v3_repository.treasury_graphs),
            "action_portfolio": digest(portfolio),
            "evidence_acquisition": digest(evidence_plan),
            "validation": digest(v3_repository.validation),
        },
        "ranked_opportunity_ids": [item["opportunity_id"] for item in opportunities],
        "selected_action_ids": sorted(
            item["action_id"] for item in portfolio["selected_actions"]
        ),
    }


def main() -> int:
    surface = build_frozen_surface()
    FROZEN.parent.mkdir(parents=True, exist_ok=True)
    FROZEN.write_text(json.dumps(surface, indent=2) + "\n", encoding="utf-8")
    print(f"frozen V3.0 regression surface written to {FROZEN.relative_to(ROOT)}")
    print(json.dumps(surface["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
