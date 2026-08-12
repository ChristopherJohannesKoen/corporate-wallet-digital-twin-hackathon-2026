"""The measurement policy is governed, versioned and documented from one source."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from wallet_twin_v2.contracts import EvidenceTier
from wallet_twin_v2.measurement_policy import (
    DEFAULT_MEASUREMENT_POLICY,
    MEASUREMENT_POLICY_VERSION,
    RETIRED_V1_ANCHOR_WEIGHT,
    MeasurementPolicy,
)
from wallet_twin_v2.public_evidence import ANCHOR_ACTIVATION_POLICY_VERSION
from wallet_twin_v2.wallet_model import HierarchicalWalletModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sync_methodology import BLOCKS, extract, rendered_body  # noqa: E402


def test_shipped_anchor_weights_are_the_governed_values():
    policy = DEFAULT_MEASUREMENT_POLICY
    assert policy.version == MEASUREMENT_POLICY_VERSION
    assert policy.activation_policy_version == ANCHOR_ACTIVATION_POLICY_VERSION
    assert policy.weight(EvidenceTier.E0) == 0.00
    assert policy.weight(EvidenceTier.E1) == 0.35
    assert policy.weight(EvidenceTier.E2) == 0.60
    assert policy.weight(EvidenceTier.E3) == 0.90
    assert policy.weight(EvidenceTier.E4) == 0.94


def test_wallet_model_reads_its_weights_from_the_policy():
    """Changing the policy must change the model, or the version means nothing."""
    default = HierarchicalWalletModel()
    assert default.policy is DEFAULT_MEASUREMENT_POLICY
    assert default._anchor_weight[EvidenceTier.E1] == 0.35

    arm = HierarchicalWalletModel(policy=DEFAULT_MEASUREMENT_POLICY.with_e1_weight(0.20))
    assert arm._anchor_weight[EvidenceTier.E1] == 0.20
    assert arm.policy.version.endswith("+e1w0.20")
    # A sensitivity arm must not silently disturb the other tiers.
    assert arm._anchor_weight[EvidenceTier.E3] == 0.90


def test_sensitivity_arm_rejects_an_out_of_range_weight():
    with pytest.raises(ValueError):
        DEFAULT_MEASUREMENT_POLICY.with_e1_weight(1.4)


def test_retired_v1_weight_is_not_used_by_the_v2_model():
    """0.84 is V1 history. It must never reappear as a live V2 weight."""
    assert RETIRED_V1_ANCHOR_WEIGHT == 0.84
    assert RETIRED_V1_ANCHOR_WEIGHT not in set(
        DEFAULT_MEASUREMENT_POLICY.anchor_weights.values()
    )


def test_policy_serialises_for_artifacts():
    payload = DEFAULT_MEASUREMENT_POLICY.as_dict()
    assert payload["policy_version"] == MEASUREMENT_POLICY_VERSION
    assert payload["anchor_weights"]["E1"] == 0.35
    assert payload["declared_share_floor"] == 0.03
    assert set(payload["weight_rationale"]) == {"E0", "E1", "E2", "E3", "E4"}


@pytest.mark.parametrize("block", BLOCKS, ids=lambda item: item.marker)
def test_generated_documentation_blocks_match_their_source(block):
    """docs/methodology.md carried a stale 0.84 for two releases. Never again.

    If this fails, run ``python scripts/sync_methodology.py``.
    """
    text = block.path.read_text(encoding="utf-8")
    assert extract(text, block.marker) == rendered_body(block), (
        f"generated block '{block.marker}' in {block.path.name} is stale; "
        "run python scripts/sync_methodology.py"
    )


def test_methodology_block_states_the_live_weight_and_retires_the_old_one():
    block = DEFAULT_MEASUREMENT_POLICY.methodology_block()
    assert "0.35" in block
    assert "retired" in block.lower()
    assert MEASUREMENT_POLICY_VERSION in block
    assert ANCHOR_ACTIVATION_POLICY_VERSION in block


def test_policy_is_immutable():
    with pytest.raises(Exception):
        DEFAULT_MEASUREMENT_POLICY.declared_share_floor = 0.10  # type: ignore[misc]
    assert isinstance(DEFAULT_MEASUREMENT_POLICY, MeasurementPolicy)
