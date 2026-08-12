"""The set of committed artifacts that must reproduce byte-identically.

One list, three consumers: the CI reproducibility gate, the artifact-stability
test and the submission manifest. Keeping it here rather than inline in
``.github/workflows/ci.yml`` means a new generated artifact cannot be added to
the build while being silently omitted from the gate that protects it.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[2]

#: Paths relative to the repository root. Directories expand to every ``*.json``
#: beneath them.
COMMITTED_ARTIFACT_PATHS: tuple[str, ...] = (
    "contracts",
    "dashboard/app/data/shadow-fixture.json",
    "dashboard/app/data/v3-fixture.json",
    "dashboard/app/data/v31-fixture.json",
    "outputs/v3",
    "outputs/v31",
    "outputs/v3_validation/v3_validation_report.json",
    "tests/regression/v3_0/v3_0_frozen_surface.json",
    "tests/regression/v3_0/v3_0_frozen_surface.restated.json",
)

#: Artifacts that are regenerated but deliberately NOT byte-stable, with the
#: reason. They carry measured host behaviour, so they are reported rather than
#: gated. Nothing here may be embedded in a committed artifact — see
#: ``canonical.redact_machine_measurements``.
UNSTABLE_BY_DESIGN: dict[str, str] = {
    "outputs/v2_validation/operational_rehearsal.json": "measures host latency and throughput",
    "outputs/v2_validation/production_candidate_scorecard.json": "embeds a measured host p95 latency",
}


def committed_artifacts(root: Path = ROOT) -> List[Path]:
    """Every committed artifact the reproducibility gate covers."""
    resolved: List[Path] = []
    for entry in COMMITTED_ARTIFACT_PATHS:
        target = root / entry
        if target.is_dir():
            resolved.extend(sorted(target.rglob("*.json")))
        elif target.exists():
            resolved.append(target)
    return sorted(set(resolved))
