"""Assert the Rego policy and the in-process policy agree.

Two policies that drift apart silently is the failure the dual gateway exists to
catch. This sweeps a matrix of principals and requests through both and fails on
any disagreement, so the drift is caught in CI rather than in a request.

The matrix is deliberately built from *combinations* rather than a handwritten
list of interesting cases. The two divergences V3.2 actually found — the ``"*"``
wildcard and unenforced region — were both in combinations nobody had thought to
write down, which is the argument against handwriting them.

    python scripts/check_policy_agreement.py
"""

from __future__ import annotations

import itertools
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.contracts import DeploymentEnvironment, EntitlementContext  # noqa: E402
from wallet_twin_v2.opa_gateway import (  # noqa: E402
    DualEntitlementGateway,
    OPAClient,
    OPAUnavailableError,
)

OPA_URL = "http://127.0.0.1:8181"

ROLE_SETS = (
    ["SHADOW_OPERATOR"],
    ["MODEL_VALIDATOR"],
    ["EVIDENCE_REVIEWER", "SHADOW_OPERATOR"],
    ["PILOT_RM"],
    ["PRODUCT_FINANCE", "SHADOW_OPERATOR"],
)
CLIENT_ENTITLEMENTS = (["E01"], ["E01", "E02"], ["*"])
REGION_ENTITLEMENTS = (["ZA"], ["ZA", "UK"], ["*"])
PRODUCT_ENTITLEMENTS = (["Trade finance"], ["*"], [])
REQUESTED_CLIENTS = ("E01", "E02", "E99")
REQUESTED_REGIONS = ("ZA", "UK")
REQUESTED_PRODUCTS = ("Trade finance", "Structured trade")
ACTIONS = (
    ("v1:opportunities:read", False),
    ("evidence:approve", False),
    ("v1:economics:read", True),
)


def opa_available() -> bool:
    try:
        with urllib.request.urlopen(f"{OPA_URL}/health", timeout=2.0) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    if not opa_available():
        print(
            f"OPA is not reachable at {OPA_URL}. Start the lab first:\n"
            "  docker compose -f infra/local/docker-compose.yml up -d opa",
            file=sys.stderr,
        )
        return 2

    gateway = DualEntitlementGateway(client=OPAClient(OPA_URL))
    checked = 0

    for roles, clients, regions, products in itertools.product(
        ROLE_SETS, CLIENT_ENTITLEMENTS, REGION_ENTITLEMENTS, PRODUCT_ENTITLEMENTS
    ):
        context = EntitlementContext(
            user_id="policy-agreement-probe",
            roles=list(roles),
            team="ci",
            regions=list(regions),
            client_ids=list(clients),
            products=list(products),
            environment=DeploymentEnvironment.SHADOW,
        )
        for client_id, region, product in itertools.product(
            REQUESTED_CLIENTS, REQUESTED_REGIONS, REQUESTED_PRODUCTS
        ):
            for action, sensitive in ACTIONS:
                try:
                    gateway.authorize(
                        context=context,
                        action=action,
                        resource_type="probe",
                        resource_id=f"{client_id}:{product}:{region}",
                        client_id=client_id,
                        product=product,
                        client_region=region,
                        sensitive_economics=sensitive,
                    )
                except OPAUnavailableError as error:
                    print(f"OPA became unavailable mid-sweep: {error}", file=sys.stderr)
                    return 2
                checked += 1

    divergences: List[Dict[str, Any]] = gateway.divergences()
    if divergences:
        print(
            json.dumps(
                {
                    "status": "POLICY_DIVERGENCE",
                    "checked": checked,
                    "divergences": len(divergences),
                    "sample": divergences[:10],
                },
                indent=2,
            ),
            file=sys.stderr,
        )
        print(
            "\nThe Rego policy and the in-process policy disagree. One of them "
            "has drifted, and the system is refusing or allowing requests "
            "nobody decided to refuse or allow.",
            file=sys.stderr,
        )
        return 1

    print(
        json.dumps(
            {
                "status": "POLICIES_AGREE",
                "combinations_checked": checked,
                "opa_in_request_path": gateway.enabled,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
