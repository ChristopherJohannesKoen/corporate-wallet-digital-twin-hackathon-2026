"""Committed artifacts must be reproducible.

Nothing guarded this before V3.1.1. The only mechanism was a
``git diff --exit-code`` step in CI, which fails on a machine you cannot inspect
and says nothing about *why*. These tests run in milliseconds, need no NumPy
execution, and name the offending JSON pointer.

They would have caught all of the following, each of which was live in the
committed tree: 8,645 sub-canonical floats in the V3.1 artifacts, six wall-clock
build timestamps in ``shadow-fixture.json``, UUID4 event ids inside a published
content digest, and two host latency measurements embedded in a
reproducibility-gated fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, List

import pytest

from wallet_twin_v2.artifacts import ROOT, UNSTABLE_BY_DESIGN, committed_artifacts
from wallet_twin_v2.canonical import (
    MACHINE_MEASUREMENT_FIELDS,
    canonical_json,
    canonical_value,
)

ARTIFACTS = committed_artifacts()

#: A build stamp is fine; a *wall-clock* build stamp is not. Committed artifacts
#: are stamped at the model as_of instant so a rebuild is byte-identical.
ALLOWED_TIMESTAMP_PREFIX = "2026-06-30T00:00:00"


def _ids(paths: List[Path]) -> List[str]:
    return [str(path.relative_to(ROOT)).replace("\\", "/") for path in paths]


def _walk(value: Any, pointer: str = "") -> Iterator[tuple[str, Any]]:
    yield pointer or "/", value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk(item, f"{pointer}/{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{pointer}/{index}")


def test_the_artifact_set_is_not_empty():
    assert ARTIFACTS, "no committed artifacts resolved; the gate would pass vacuously"


@pytest.mark.parametrize("path", ARTIFACTS, ids=_ids(ARTIFACTS))
def test_committed_artifact_is_at_published_precision(path: Path):
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if canonical_value(parsed) == parsed:
        return
    offenders = [
        f"{pointer} = {value!r}"
        for pointer, value in _walk(parsed)
        if not isinstance(value, (dict, list)) and canonical_value(value) != value
    ]
    pytest.fail(
        f"{path.relative_to(ROOT)} holds {len(offenders)} sub-canonical value(s); "
        "run the exporters through canonical.write_canonical_json.\n  "
        + "\n  ".join(offenders[:10])
    )


#: The pre-restatement boundary is immutable historical evidence. It predates the
#: canonical writer and must never be rewritten to satisfy a formatting rule.
BYTE_FORM_EXEMPT = {"tests/regression/v3_0/v3_0_frozen_surface.json"}


@pytest.mark.parametrize("path", ARTIFACTS, ids=_ids(ARTIFACTS))
def test_committed_artifact_byte_form_is_canonical(path: Path):
    relative = str(path.relative_to(ROOT)).replace("\\", "/")
    if relative in BYTE_FORM_EXEMPT:
        pytest.skip("immutable pre-restatement asset; never rewritten")
    text = path.read_text(encoding="utf-8")
    parsed = json.loads(text)
    assert text == canonical_json(parsed), (
        f"{relative} is not in canonical byte form "
        "(indent=2, sort_keys=True, trailing newline)"
    )


@pytest.mark.parametrize("path", ARTIFACTS, ids=_ids(ARTIFACTS))
def test_committed_artifact_carries_no_wall_clock_stamp(path: Path):
    parsed = json.loads(path.read_text(encoding="utf-8"))
    offenders = [
        f"{pointer} = {value!r}"
        for pointer, value in _walk(parsed)
        if pointer.rsplit("/", 1)[-1] in {"generated_at", "recorded_at", "received_at"}
        and isinstance(value, str)
        and not value.startswith(ALLOWED_TIMESTAMP_PREFIX)
    ]
    assert not offenders, (
        f"{path.relative_to(ROOT)} embeds a wall-clock build stamp, so it can never "
        "reproduce byte-identically. Use canonical.artifact_timestamp().\n  "
        + "\n  ".join(offenders[:10])
    )


@pytest.mark.parametrize("path", ARTIFACTS, ids=_ids(ARTIFACTS))
def test_committed_artifact_embeds_no_host_measurement(path: Path):
    parsed = json.loads(path.read_text(encoding="utf-8"))
    offenders = [
        f"{pointer} = {value!r}"
        for pointer, value in _walk(parsed)
        if pointer.rsplit("/", 1)[-1] in MACHINE_MEASUREMENT_FIELDS
        and not isinstance(value, str)
        and "/properties/" not in pointer
    ]
    assert not offenders, (
        f"{path.relative_to(ROOT)} embeds a measured host timing. Keep it in "
        "outputs/v2_validation/ and redact it here via "
        "canonical.redact_machine_measurements.\n  " + "\n  ".join(offenders[:10])
    )


def test_unstable_artifacts_are_declared_and_excluded_from_the_gate():
    """Artifacts that legitimately vary must be named, not quietly omitted."""
    gated = set(_ids(ARTIFACTS))
    for path, reason in UNSTABLE_BY_DESIGN.items():
        assert reason, f"{path} must state why it is not byte-stable"
        assert path not in gated, (
            f"{path} is declared unstable but is also in the reproducibility gate"
        )
