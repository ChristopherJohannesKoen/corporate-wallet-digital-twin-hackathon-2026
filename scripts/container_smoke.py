"""Container smoke test: readiness, then negative-then-positive authorization.

Run inside the published image:

    docker exec -i wallet-twin-smoke python - < scripts/container_smoke.py

Two properties this is designed to prove, which a single 200-check cannot:

* the image is **not** running in fixture mode — an unauthenticated read is
  refused, so the deployed artifact is the entitled one;
* the ABAC layer is **live** rather than merely present — a caller who
  authenticates but holds the wrong role is refused too. Without that phase a
  passing smoke test is consistent with "any header at all is accepted".

Readiness polling is separated from assertions. Retrying an assertion failure
twenty times and then printing nothing is how a 401 regression previously looked
identical to a slow boot.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8080"
DECISION = f"{BASE}/v3/decision-twin?as_of=2026-06-30&week_start=2026-07-06"
WALLET = f"{BASE}/v3/wallet-portfolio?as_of=2026-06-30"
VERSION = "3.2.0"
FROZEN_DECISION_VERSION = "3.1.1"
PROMOTION = f"{BASE}/v3/promotion/readiness?as_of=2026-06-30&target_state=SHADOW_READY"

ENTITLED = {
    "x-user-id": "ci-smoke",
    "x-user-roles": "SHADOW_OPERATOR,MODEL_VALIDATOR",
    "x-user-team": "model-risk",
    "x-user-clients": "*",
    "x-user-products": "*",
}
#: Authenticates, and is a real role — but it is in SENSITIVE_ECONOMICS_ROLES,
#: not SHADOW_ROLES, so authorization must still refuse it.
WRONG_ROLE = dict(ENTITLED, **{"x-user-id": "ci-smoke-wrong-role", "x-user-roles": "PRODUCT_FINANCE"})


def get(url: str, headers: dict[str, str] | None = None, timeout: float = 10.0) -> dict:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def expect_status(url: str, headers: dict[str, str] | None, code: int, label: str) -> None:
    try:
        get(url, headers)
    except urllib.error.HTTPError as exc:
        if exc.code != code:
            raise AssertionError(f"{label}: expected {code}, got {exc.code}") from exc
        print(f"PASS {label}: {code}")
        return
    raise AssertionError(f"{label}: expected {code}, but the request succeeded")


def wait_for_ready(attempts: int = 30, delay: float = 2.0) -> None:
    """Poll /health only. Readiness must never be inferred from an assertion."""
    last: Exception | None = None
    for _ in range(attempts):
        try:
            health = get(f"{BASE}/health", timeout=2.0)
        except Exception as exc:  # noqa: BLE001 - any transport error means not up yet
            last = exc
            time.sleep(delay)
            continue
        if health.get("version") == VERSION:
            print(f"PASS ready: /health reports {VERSION}")
            return
        raise AssertionError(f"/health reports {health.get('version')!r}, expected {VERSION!r}")
    raise AssertionError(f"container never became ready: {last!r}")


def main() -> int:
    wait_for_ready()

    expect_status(DECISION, None, 401, "unauthenticated read is refused")
    expect_status(DECISION, WRONG_ROLE, 403, "authenticated wrong-role read is refused")

    payload = get(DECISION, ENTITLED)
    # The Decision Twin body is the frozen V3.1.1 compatibility contract; the
    # ASGI service and additive Promotion surface carry the V3.2 release.
    assert payload["metadata"]["version"] == FROZEN_DECISION_VERSION, payload["metadata"]["version"]
    entries = len(payload["coverage_plan"]["entries"])
    assert entries == 8, f"coverage plan has {entries} entries, expected 8"
    print(
        f"PASS entitled read: frozen decision contract {FROZEN_DECISION_VERSION}, "
        f"{entries} coverage-plan entries"
    )

    promotion = get(PROMOTION, ENTITLED)
    assert promotion["repository_version"] == "v32-promotion-repository-1.0.0"
    assert len(promotion["gate_breakdown"]) == 30
    assert promotion["decision"]["score"]["promotion_machinery_readiness"] == 1.0
    assert promotion["decision"]["score"]["bank_evidence_readiness"] == 0.0
    assert promotion["decision"]["bank_shadow_authorized"] is False
    print("PASS promotion surface: V3.2, 30 gates, PMR 100%, BER 0%, bank shadow false")

    wallet = get(WALLET, ENTITLED)
    assert len(wallet["cells"]) == 100, len(wallet["cells"])
    assert wallet["approved_anchor_cells"] == 15, wallet["approved_anchor_cells"]
    assert wallet["prior_led_cells"] == 85, wallet["prior_led_cells"]
    print("PASS wallet portfolio: 100 cells, 15 approved-anchor, 85 prior-led")

    print("container smoke passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
