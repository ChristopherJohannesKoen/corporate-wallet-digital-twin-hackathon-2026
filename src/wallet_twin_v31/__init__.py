"""Corporate Wallet Digital Twin V3.1 — Corporate Banking Decision Twin.

V3.1 extends V3 rather than replacing it.  V2 remains the governed evidence and
economics substrate, V3 remains the latent-structure and change-detection
layer, and V3.1 adds the decision object a corporate banker actually acts on:

    (client, stakeholder, business problem, solution bundle, engagement window)

Every interpretation boundary established in V2 and V3 is preserved: observed,
identified, posterior, scenario and causal values remain distinct, unknown
inputs remain unknown, and bank production remains ``NOT_PROMOTABLE``.
"""

from .taxonomy import (
    BankingSolution,
    BusinessProblem,
    BusinessTwinDomain,
    StakeholderRole,
)

__all__ = [
    "BankingSolution",
    "BusinessProblem",
    "BusinessTwinDomain",
    "StakeholderRole",
    "build_v31_fixture",
]

__version__ = "3.1.1"


def __getattr__(name: str):  # pragma: no cover - lazy import keeps import cheap
    if name == "build_v31_fixture":
        from .fixtures import build_v31_fixture

        return build_v31_fixture
    raise AttributeError(name)
