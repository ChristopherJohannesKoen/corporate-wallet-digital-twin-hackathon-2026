"""Documentation must not outrun the artifacts.

Prose is the easiest place for an overclaim to survive: nothing recomputes it,
and a number written once stays written after the code that produced it changes.
These tests bind the V3.2 documents to the fixtures they describe, so a doc that
still claims a superseded figure fails rather than being read.

Only load-bearing claims are checked — the numbers and statuses a reviewer would
act on. Wording is not asserted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
V32_DOC = DOCS / "Corporate_Wallet_Digital_Twin_V3_2_Promotion_Twin.md"

#: Documents that make V3.2 claims and must therefore stay consistent with it.
V32_DOCUMENTS = (
    V32_DOC,
    DOCS / "model_card.md",
    DOCS / "data_dictionary.md",
    DOCS / "judging_map.md",
    DOCS / "runbook.md",
    ROOT / "README.md",
)


@pytest.fixture(scope="module")
def promotion() -> Dict:
    return json.loads(
        (ROOT / "dashboard" / "app" / "data" / "promotion-fixture.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture(scope="module")
def texts() -> Dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in V32_DOCUMENTS}


def _v32_texts(texts: Dict[Path, str]) -> List[str]:
    return [text for text in texts.values() if "V3.2" in text or "promotion" in text.lower()]


# --------------------------------------------------------------------------
# The numbers the docs quote must be the numbers the fixture holds
# --------------------------------------------------------------------------


def test_the_gate_count_in_the_docs_matches_the_catalogue(
    promotion: Dict, texts: Dict[Path, str]
) -> None:
    from wallet_twin_v32 import GATE_CATALOGUE

    count = len(GATE_CATALOGUE)
    assert count == 24
    assert f"{count} gates" in texts[V32_DOC]


def test_the_transition_count_matches(promotion: Dict, texts: Dict[Path, str]) -> None:
    assert len(promotion["transitions"]) == 4
    assert "4 transitions" in texts[V32_DOC]


def test_the_two_scores_are_quoted_correctly(
    promotion: Dict, texts: Dict[Path, str]
) -> None:
    """PMR 100% / BER 0% appears in several documents. If either moves, every
    document quoting it becomes wrong at once."""
    summary = promotion["summary"]
    assert summary["promotion_machinery_readiness"] == 1.0
    assert summary["bank_evidence_readiness"] == 0.0
    for text in _v32_texts(texts):
        if "PMR" in text:
            assert "100%" in text
            assert "0%" in text


def test_the_day_counts_are_quoted_correctly(
    promotion: Dict, texts: Dict[Path, str]
) -> None:
    clock = promotion["clock"]
    assert clock["consecutive_clean_rehearsal_days"] == 30
    assert clock["rehearsal_days_elapsed"] == 47
    assert clock["elapsed_bank_shadow_days"] == 0
    assert "47" in texts[V32_DOC] and "30" in texts[V32_DOC]


def test_the_incident_day_is_quoted_correctly(texts: Dict[Path, str]) -> None:
    from wallet_twin_v32.rehearsal import CANONICAL_INCIDENT_DAY

    assert CANONICAL_INCIDENT_DAY == 17
    assert "day 17" in texts[V32_DOC].lower()


def test_the_policy_agreement_matrix_size_is_quoted_correctly(
    texts: Dict[Path, str]
) -> None:
    """4,860 is stated in three documents. It is the product of the sweep's
    dimensions, so a change to the matrix must update the prose."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import check_policy_agreement as sweep

    combinations = (
        len(sweep.ROLE_SETS)
        * len(sweep.CLIENT_ENTITLEMENTS)
        * len(sweep.REGION_ENTITLEMENTS)
        * len(sweep.PRODUCT_ENTITLEMENTS)
        * len(sweep.REQUESTED_CLIENTS)
        * len(sweep.REQUESTED_REGIONS)
        * len(sweep.REQUESTED_PRODUCTS)
        * len(sweep.ACTIONS)
    )
    assert combinations == 4860
    assert "4,860" in texts[V32_DOC]


def test_the_signer_posture_is_quoted_correctly(
    promotion: Dict, texts: Dict[Path, str]
) -> None:
    assert promotion["signing"]["real_bank_signing_available"] is False
    for text in _v32_texts(texts):
        assert "REAL_BANK_SIGNING_AVAILABLE = TRUE" not in text


# --------------------------------------------------------------------------
# The docs must not overclaim
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", V32_DOCUMENTS, ids=lambda item: item.name)
def test_no_document_claims_bank_authorisation(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    for forbidden in (
        "bank_shadow_authorized = true",
        "bank_shadow_authorized: true",
        "production ready",
        "production-approved",
    ):
        assert forbidden not in text, f"{path.name} claims bank authorisation"


@pytest.mark.parametrize("path", V32_DOCUMENTS, ids=lambda item: item.name)
def test_no_document_publishes_a_composite_score(path: Path) -> None:
    """The prohibition holds in prose too. A document quoting a single blended
    figure would undo in the reader's head what the code refuses to compute."""
    text = path.read_text(encoding="utf-8").lower()
    for forbidden in ("promotability score", "overall readiness score", "composite score"):
        assert forbidden not in text, f"{path.name} publishes a composite score"


def test_the_v32_document_states_what_is_not_established() -> None:
    """A document listing only what works cannot be audited for what does not."""
    text = V32_DOC.read_text(encoding="utf-8").lower()
    assert "what v3.2 does not establish" in text
    for gap in ("e3", "economics", "live-provider", "shadow day", "rm session", "trial"):
        assert gap in text, f"the open {gap} gate is not recorded"


def test_every_document_mentioning_shadow_days_also_states_elapsed_bank_days(
    texts: Dict[Path, str]
) -> None:
    """The pairing rule applies to prose as much as to payloads."""
    for path, text in texts.items():
        if "shadow_rehearsal_days" in text:
            assert "elapsed_bank_shadow_days" in text, path.name


def test_bank_production_status_is_stated_as_not_promotable(
    texts: Dict[Path, str]
) -> None:
    assert "NOT_PROMOTABLE" in texts[V32_DOC]
    assert "NOT_PROMOTABLE" in texts[ROOT / "README.md"]
