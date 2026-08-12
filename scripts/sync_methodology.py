"""Regenerate the documentation blocks that are owned by governed policy objects.

Prose that restates a policy number drifts. ``docs/methodology.md`` carried a
V1-era anchor weight of 0.84 for the whole life of V2 and V3 while the shipped
V2 model pooled at 0.35, and nothing caught it because nothing tied the sentence
to the constant.

Each block below is delimited in the target document and written from a single
source of truth. ``tests/test_v2_measurement_policy.py`` asserts the committed
files still match, so drift fails the build instead of reaching a judge.

Usage::

    python scripts/sync_methodology.py            # rewrite the blocks
    python scripts/sync_methodology.py --check    # fail if a block is stale
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.genai_eval import governed_check_scopes  # noqa: E402
from wallet_twin_v2.measurement_policy import (  # noqa: E402
    DEFAULT_MEASUREMENT_POLICY,
)


class GeneratedBlock(NamedTuple):
    path: Path
    marker: str
    render: Callable[[], str]


def _measurement_policy_block() -> str:
    return DEFAULT_MEASUREMENT_POLICY.methodology_block()


def _governed_checks_block() -> str:
    scopes = governed_check_scopes()
    evidence_grounded = scopes["evidence_grounded_total"]
    stress = scopes["generated_stress_cases"]
    total = scopes["governed_checks_total"]
    share = 100.0 * stress / total if total else 0.0
    return (
        f"{evidence_grounded} evidence-grounded governed checks "
        f"({scopes['golden_cases']} sealed/dev/training golden cases, "
        f"{scopes['evidence_register_replays']} evidence-register replays and "
        f"{scopes['page_grounding_facts']} page-grounded fact replays), plus a "
        f"{stress}-case deterministic validator stress suite — {total} checks in "
        f"total, of which {share:.0f}% exercise validators and abstention mechanics "
        "with no model call. The two figures measure different things and are "
        "reported separately for that reason."
    )


BLOCKS: List[GeneratedBlock] = [
    GeneratedBlock(
        path=ROOT / "docs" / "methodology.md",
        marker="measurement-policy",
        render=_measurement_policy_block,
    ),
    GeneratedBlock(
        path=ROOT / "docs" / "v2_security_and_genai.md",
        marker="governed-checks",
        render=_governed_checks_block,
    ),
]


def _pattern(marker: str) -> re.Pattern[str]:
    return re.compile(
        rf"(<!-- BEGIN GENERATED: {re.escape(marker)} -->\n)(.*?)(<!-- END GENERATED: {re.escape(marker)} -->)",
        re.DOTALL,
    )


def extract(text: str, marker: str) -> str:
    match = _pattern(marker).search(text)
    if match is None:
        raise SystemExit(f"generated block '{marker}' is missing its delimiters")
    return match.group(2)


def apply(text: str, marker: str, body: str) -> str:
    pattern = _pattern(marker)
    if pattern.search(text) is None:
        raise SystemExit(f"generated block '{marker}' is missing its delimiters")
    return pattern.sub(lambda m: f"{m.group(1)}{body}{m.group(3)}", text)


def rendered_body(block: GeneratedBlock) -> str:
    """The block body, normalised so comparison is whitespace-stable."""
    return "\n" + block.render().strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if any generated block is stale, without writing",
    )
    args = parser.parse_args()

    stale: Dict[str, Path] = {}
    for block in BLOCKS:
        text = block.path.read_text(encoding="utf-8")
        body = rendered_body(block)
        if extract(text, block.marker) == body:
            continue
        stale[block.marker] = block.path
        if not args.check:
            block.path.write_text(apply(text, block.marker, body), encoding="utf-8")
            print(f"regenerated '{block.marker}' in {block.path.relative_to(ROOT)}")

    if args.check and stale:
        for marker, path in stale.items():
            print(
                f"stale generated block '{marker}' in {path.relative_to(ROOT)}; "
                "run python scripts/sync_methodology.py",
                file=sys.stderr,
            )
        return 1
    if not stale:
        print("all generated documentation blocks are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
