"""Governed measurement policy for the hierarchical wallet model.

The weight given to a public anchor is a policy choice, not a tuning constant.
It decides how far a published wallet estimate moves away from the prior when
audited evidence exists, so it belongs in a versioned, registered artifact that
a model-risk forum can approve — exactly like the V3.1 value, feasibility and
coverage policies.

Before V3.1.1 these weights were bare class-level dicts on
:class:`~wallet_twin_v2.wallet_model.HierarchicalWalletModel`. Nothing bound
them to a version string, so changing ``0.35`` changed no declared artifact, and
``docs/methodology.md`` drifted to a V1-era ``0.84`` without any test noticing.
:meth:`MeasurementPolicy.methodology_block` is now the single source of that
documentation wording; ``scripts/sync_methodology.py`` writes it and
``tests/test_v2_measurement_policy.py`` asserts the file still matches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping

from .contracts import EvidenceTier
from .public_evidence import ANCHOR_ACTIVATION_POLICY_VERSION

MEASUREMENT_POLICY_VERSION = "v2-wallet-measurement-policy-1.1.0"

#: Geometric pooling weight applied to an *activated* anchor, by evidence tier.
#: E0 carries no anchor at all. E1 is a public accounting proxy — informative
#: about scale, but not a wallet label — so it is deliberately held well below
#: one. Only E3/E4 multibank observation earns a weight that dominates the prior.
DEFAULT_ANCHOR_WEIGHTS: Mapping[EvidenceTier, float] = {
    EvidenceTier.E0: 0.00,
    EvidenceTier.E1: 0.35,
    EvidenceTier.E2: 0.60,
    EvidenceTier.E3: 0.90,
    EvidenceTier.E4: 0.94,
}

DEFAULT_WEIGHT_RATIONALE: Mapping[EvidenceTier, str] = {
    EvidenceTier.E0: "No anchor exists; the estimate is prior-led and is labelled PRIOR_LED.",
    EvidenceTier.E1: (
        "An audited public accounting figure constrains scale but is not a wallet "
        "measurement. It is pooled at 0.35 so it informs the estimate without "
        "being treated as a label."
    ),
    EvidenceTier.E2: "A client-confirmed quantity, reviewed but not independently observed.",
    EvidenceTier.E3: "Direct multibank observation — the only tier that can support a measured share.",
    EvidenceTier.E4: "Adjudicated multibank observation with an audited reconciliation.",
}

#: Governed floor on the share used to close the identification set when no
#: anchor is active. Wide by construction: an assumption-light bound on an
#: unanchored cell *should* be wide, and narrowing it would manufacture
#: precision that the evidence does not support.
DEFAULT_SHARE_FLOOR = 0.03

#: Retired. V1 pooled anchors at 0.84. It survives only in
#: ``legacy/v1/config/assumptions.json`` and the frozen V1 regression fixtures,
#: and is not used by any V2/V3/V3.1 code path.
RETIRED_V1_ANCHOR_WEIGHT = 0.84


@dataclass(frozen=True)
class MeasurementPolicy:
    version: str = MEASUREMENT_POLICY_VERSION
    anchor_weights: Mapping[EvidenceTier, float] = field(
        default_factory=lambda: dict(DEFAULT_ANCHOR_WEIGHTS)
    )
    weight_rationale: Mapping[EvidenceTier, str] = field(
        default_factory=lambda: dict(DEFAULT_WEIGHT_RATIONALE)
    )
    activation_policy_version: str = ANCHOR_ACTIVATION_POLICY_VERSION
    declared_share_floor: float = DEFAULT_SHARE_FLOOR

    def weight(self, tier: EvidenceTier) -> float:
        return float(self.anchor_weights[tier])

    def with_e1_weight(self, weight: float) -> "MeasurementPolicy":
        """Return a sensitivity arm. The version records the override."""
        if not 0.0 <= weight <= 1.0:
            raise ValueError("an anchor weight must lie in [0, 1]")
        weights = dict(self.anchor_weights)
        weights[EvidenceTier.E1] = float(weight)
        return MeasurementPolicy(
            version=f"{self.version}+e1w{weight:.2f}",
            anchor_weights=weights,
            weight_rationale=dict(self.weight_rationale),
            activation_policy_version=self.activation_policy_version,
            declared_share_floor=self.declared_share_floor,
        )

    def as_dict(self) -> Dict[str, object]:
        return {
            "policy_version": self.version,
            "activation_policy_version": self.activation_policy_version,
            "anchor_weights": {
                tier.value: self.weight(tier) for tier in EvidenceTier
                if tier in self.anchor_weights
            },
            "weight_rationale": {
                tier.value: reason for tier, reason in self.weight_rationale.items()
            },
            "declared_share_floor": self.declared_share_floor,
            "retired_v1_anchor_weight": RETIRED_V1_ANCHOR_WEIGHT,
        }

    def methodology_block(self) -> str:
        """Generated methodology wording. The docs render this verbatim."""
        rows = "\n".join(
            f"| `{tier.value}` | {self.weight(tier):.2f} | {self.weight_rationale[tier]} |"
            for tier in EvidenceTier
            if tier in self.anchor_weights
        )
        return (
            f"Measurement policy `{self.version}`, activation policy "
            f"`{self.activation_policy_version}`.\n"
            "\n"
            "An *activated* public anchor is pooled geometrically with the share-prior\n"
            "wallet at the weight declared for its evidence tier. Activation is a separate\n"
            "gate: an anchor may inform an estimate only when every fact behind it is\n"
            "finance-SME approved. A single pending fact withholds the whole anchor and the\n"
            "cell falls back to the prior-led path.\n"
            "\n"
            "| Evidence tier | Anchor weight | Basis |\n"
            "|---|---|---|\n"
            f"{rows}\n"
            "\n"
            f"Where no anchor is active the identification set is closed with a governed\n"
            f"share floor of {self.declared_share_floor:.2f}. That produces a deliberately\n"
            "wide, assumption-light bound; it is not narrowed to look more precise than the\n"
            "evidence supports.\n"
            "\n"
            f"The V1 anchor weight of {RETIRED_V1_ANCHOR_WEIGHT} is **retired**. It is retained in\n"
            "`legacy/v1/config/assumptions.json` and the frozen V1 regression fixtures for\n"
            "historical reproducibility only, and is not used by the V2 measurement model."
        )


DEFAULT_MEASUREMENT_POLICY = MeasurementPolicy()
