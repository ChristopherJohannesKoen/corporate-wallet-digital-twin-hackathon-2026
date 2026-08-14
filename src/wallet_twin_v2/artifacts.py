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
    "dashboard/app/data/promotion-fixture.json",
    "outputs/v3",
    "outputs/v31",
    "outputs/v32",
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

#: Deliverables that are rebuilt by the canonical build and are **not** expected
#: to be byte-identical: document formats stamp their own creation time, and an
#: executed notebook records per-cell execution metadata. They are outside the
#: reproducibility gate for that reason.
#:
#: This distinction is what ``clean_worktree`` means. A dirty tree matters when
#: *source* or a *gated artifact* differs from the commit the manifest names —
#: that would mean the manifest describes something other than what was built.
#: A re-encoded PDF timestamp means nothing of the kind, and treating it as a
#: reproducibility failure would make the strongest honest verdict unreachable
#: on every build.
NON_REPRODUCIBLE_DELIVERABLES: dict[str, str] = {
    "notebooks/01_wallet_twin_demo.ipynb": "records per-cell execution metadata",
    "output/notebook/01_wallet_twin_demo.html": "rendered from the executed notebook",
    "output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf": "PDF stamps a creation date",
    "output/presentation/Corporate-Wallet-Digital-Twin.pptx": "OOXML stamps a creation date",
    "outputs/audit/Public-Facts-Anchor-Register-V3.1.1.xlsx": "OOXML stamps a creation date",
    "outputs/audit/Public-Facts-Anchor-Register-V3.1.1.xlsx.inspect.ndjson": "derived from the workbook",
    "outputs/audit/Public-Facts-Anchor-Register.inspect.json": "derived from the workbook",
    # The manifest records a real build time, so it necessarily differs from the
    # committed copy. It also cannot be an input to its own verdict.
    "outputs/judging_manifest_v3.1.1.json": "records the actual build time; self-referential",
}


def reproducibility_relevant(paths: List[str]) -> List[str]:
    """Filter changed paths down to those that undermine the commit claim.

    Paths whose non-determinism is declared and understood are dropped; anything
    else — source, config, or a gated artifact — is returned, because it means
    the tree no longer matches the commit the manifest names.
    """
    exempt = set(NON_REPRODUCIBLE_DELIVERABLES) | set(UNSTABLE_BY_DESIGN)
    return [path for path in paths if path not in exempt]


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
