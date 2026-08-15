"""OPA in the request path.

Two groups. The first runs everywhere and uses a stub OPA, testing the
*arrangement*: agreement, disagreement, unavailability, and the disabled
pass-through. The second is marked ``bank_lab`` and talks to a real OPA
container, testing that the Rego policy and the Python policy actually agree on
the same inputs.

The stub tests are not a substitute for the second group and are not presented
as one. A stub proves the gateway handles what OPA says; only the real policy
proves what OPA says is right.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest

from wallet_twin_v2.contracts import DeploymentEnvironment, EntitlementContext
from wallet_twin_v2.opa_gateway import (
    DualEntitlementGateway,
    OPAClient,
    OPADecision,
    OPAUnavailableError,
    build_opa_input,
    gateway_report,
)

OPA_URL = "http://127.0.0.1:8181"


def context(**overrides) -> EntitlementContext:
    payload = {
        "user_id": "shadow-operator-1",
        "roles": ["SHADOW_OPERATOR"],
        "team": "model-risk",
        "regions": ["ZA"],
        "client_ids": ["E01"],
        "products": ["*"],
        "environment": DeploymentEnvironment.SHADOW,
    }
    payload.update(overrides)
    return EntitlementContext(**payload)


class StubOPA:
    """An OPA that says exactly what a test tells it to."""

    def __init__(self, allow: bool, reasons: List[str] | None = None) -> None:
        self.allow = allow
        self.reasons = reasons or []
        self.calls: List[Dict[str, Any]] = []

    def evaluate(self, payload: Dict[str, Any]) -> OPADecision:
        self.calls.append(payload)
        return OPADecision(allow=self.allow, deny_reasons=sorted(self.reasons))


class UnavailableOPA:
    def evaluate(self, payload: Dict[str, Any]) -> OPADecision:
        raise OPAUnavailableError("connection refused")


# --------------------------------------------------------------------------
# The arrangement
# --------------------------------------------------------------------------


def test_the_gateway_is_a_pass_through_when_no_opa_is_configured() -> None:
    """Fixture deployments and the existing suite must be unaffected."""
    gateway = DualEntitlementGateway()
    assert gateway.enabled is False
    decision = gateway.authorize(
        context=context(),
        action="v32:promotion-state:read",
        resource_type="promotion-decision",
        resource_id="2026-06-30",
        client_id="E01",
    )
    assert decision.allowed is True
    assert gateway.divergences() == []


def test_agreement_on_allow_is_reported_as_agreement() -> None:
    gateway = DualEntitlementGateway(client=StubOPA(allow=True))
    decision = gateway.authorize(
        context=context(),
        action="v32:promotion-state:read",
        resource_type="promotion-decision",
        resource_id="2026-06-30",
        client_id="E01",
    )
    assert decision.allowed is True
    assert "OPA_AND_LOCAL_AGREE" in decision.reason_codes
    assert gateway.divergences() == []


def test_agreement_on_deny_merges_both_sets_of_reasons() -> None:
    """A reviewer should see why each policy refused, not just that one did."""
    gateway = DualEntitlementGateway(
        client=StubOPA(allow=False, reasons=["CLIENT_NOT_ENTITLED"])
    )
    decision = gateway.authorize(
        context=context(client_ids=["E01"]),
        action="v32:promotion-state:read",
        resource_type="promotion-decision",
        resource_id="E02",
        client_id="E02",
    )
    assert decision.allowed is False
    assert "CLIENT_NOT_ENTITLED" in decision.reason_codes
    assert gateway.divergences() == []


def test_disagreement_denies_and_is_recorded() -> None:
    """The failure this arrangement is most likely to produce is the two
    policies drifting apart silently. Denying makes the drift loud."""
    gateway = DualEntitlementGateway(client=StubOPA(allow=False, reasons=["REGION_NOT_ENTITLED"]))
    decision = gateway.authorize(
        context=context(),
        action="v32:promotion-state:read",
        resource_type="promotion-decision",
        resource_id="2026-06-30",
        client_id="E01",
    )
    assert decision.allowed is False
    assert "POLICY_DIVERGENCE_DENIED" in decision.reason_codes
    divergences = gateway.divergences()
    assert len(divergences) == 1
    assert divergences[0]["opa_allowed"] is False
    assert divergences[0]["local_allowed"] is True


def test_disagreement_denies_even_when_opa_would_allow() -> None:
    """Fail closed in both directions. An OPA that allows what the local policy
    refuses is just as much a drift, and just as unsafe to act on."""
    gateway = DualEntitlementGateway(client=StubOPA(allow=True))
    decision = gateway.authorize(
        context=context(roles=["PRODUCT_FINANCE"]),
        action="v32:promotion-state:read",
        resource_type="promotion-decision",
        resource_id="2026-06-30",
        client_id="E01",
    )
    assert decision.allowed is False
    assert "POLICY_DIVERGENCE_DENIED" in decision.reason_codes
    assert gateway.divergences()[0]["opa_allowed"] is True
    assert gateway.divergences()[0]["local_allowed"] is False


def test_an_unreachable_opa_raises_rather_than_allowing() -> None:
    """An authorisation service that fails open is worse than none, because it
    looks like one."""
    gateway = DualEntitlementGateway(client=UnavailableOPA())
    with pytest.raises(OPAUnavailableError):
        gateway.authorize(
            context=context(),
            action="v32:promotion-state:read",
            resource_type="promotion-decision",
            resource_id="2026-06-30",
            client_id="E01",
        )


def test_actions_outside_the_rego_vocabulary_are_not_adjudicated() -> None:
    """Comparing against a rule that does not exist would manufacture a
    divergence on every write."""
    stub = StubOPA(allow=False)
    gateway = DualEntitlementGateway(client=stub)
    decision = gateway.authorize(
        context=context(roles=["MODEL_VALIDATOR"]),
        action="v32:promotion-evaluation:write",
        resource_type="promotion-evaluation",
        resource_id="supply-chain-clean",
    )
    assert decision.allowed is True
    assert stub.calls == []
    assert gateway.divergences() == []


def test_evidence_approval_maps_onto_the_rego_action() -> None:
    stub = StubOPA(allow=True)
    gateway = DualEntitlementGateway(client=stub)
    gateway.authorize(
        context=context(roles=["EVIDENCE_REVIEWER", "SHADOW_OPERATOR"]),
        action="evidence:approve",
        resource_type="evidence-fact",
        resource_id="F001",
        client_id="E01",
    )
    assert stub.calls[0]["action"] == "approve_evidence"


def test_sensitive_economics_maps_onto_its_own_rego_action() -> None:
    stub = StubOPA(allow=True)
    gateway = DualEntitlementGateway(client=stub)
    gateway.authorize(
        context=context(roles=["PRODUCT_FINANCE", "SHADOW_OPERATOR"]),
        action="v1:economics:read",
        resource_type="rate-card",
        resource_id="RC-1",
        client_id="E01",
        sensitive_economics=True,
    )
    assert stub.calls[0]["action"] == "read_sensitive_economics"


# --------------------------------------------------------------------------
# The input document
# --------------------------------------------------------------------------


def test_the_input_document_uses_the_policys_field_names() -> None:
    """A Rego rename should break in one place, not produce silent denials
    scattered across the request path."""
    payload = build_opa_input(
        context(), action="read", client_id="E01", product="Trade finance", client_region="ZA"
    )
    assert set(payload) == {
        "user_id",
        "roles",
        "environment",
        "mfa_authenticated",
        "workload_identity_age_seconds",
        "action",
        "client_id",
        "client_region",
        "product",
        "allowed_client_ids",
        "allowed_regions",
        "allowed_products",
    }


def test_every_field_the_rego_policy_reads_is_supplied() -> None:
    """Parsed from the policy itself, so adding an `input.x` rule without
    supplying x fails here rather than denying every request in production."""
    import re
    from pathlib import Path

    policy = (
        Path(__file__).resolve().parents[1] / "infra" / "policy" / "client_entitlements.rego"
    ).read_text(encoding="utf-8")
    referenced = set(re.findall(r"input\.([a-z_]+)", policy))
    supplied = set(build_opa_input(context(), action="read"))
    assert referenced <= supplied, f"policy reads fields the gateway never sends: {referenced - supplied}"


def test_the_environment_is_sent_as_its_string_value() -> None:
    payload = build_opa_input(context(), action="read")
    assert payload["environment"] == "SHADOW"


# --------------------------------------------------------------------------
# The client
# --------------------------------------------------------------------------


def test_a_missing_decision_key_is_an_error_not_a_denial() -> None:
    """An OPA response without `allow` means the policy package is missing or
    renamed. Reporting that as a routine denial would mask a deployment error."""
    client = OPAClient(OPA_URL)

    class _Response:
        def read(self) -> bytes:
            return json.dumps({"result": {}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    import urllib.request

    original = urllib.request.urlopen
    urllib.request.urlopen = lambda *args, **kwargs: _Response()  # type: ignore[assignment]
    try:
        with pytest.raises(OPAUnavailableError, match="missing or misnamed"):
            client.evaluate({"action": "read"})
    finally:
        urllib.request.urlopen = original


def test_a_transport_failure_raises_opa_unavailable() -> None:
    client = OPAClient(OPA_URL)
    # Explicit: `urllib.error` resolves only because `urllib.request` imports it,
    # which is an implementation detail rather than something to rely on.
    import urllib.error
    import urllib.request

    original = urllib.request.urlopen

    def _fail(*args, **kwargs):
        raise urllib.error.URLError("connection refused")

    urllib.request.urlopen = _fail  # type: ignore[assignment]
    try:
        with pytest.raises(OPAUnavailableError, match="evaluation failed"):
            client.evaluate({"action": "read"})
    finally:
        urllib.request.urlopen = original


def test_an_empty_opa_url_is_refused() -> None:
    with pytest.raises(ValueError, match="OPA URL is required"):
        OPAClient("")


def test_the_report_states_whether_opa_is_actually_in_the_path() -> None:
    disabled = gateway_report(DualEntitlementGateway())
    assert disabled["opa_in_request_path"] is False
    enabled = gateway_report(DualEntitlementGateway(client=StubOPA(allow=True)))
    assert enabled["opa_in_request_path"] is True


# --------------------------------------------------------------------------
# Against a real OPA container
# --------------------------------------------------------------------------


def _opa_running() -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"{OPA_URL}/health", timeout=1.0) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001
        return False


bank_lab = pytest.mark.skipif(
    not _opa_running(), reason="bank-shaped lab is not running (docker compose up -d)"
)


@pytest.mark.bank_lab
@bank_lab
def test_the_real_policy_allows_an_entitled_read() -> None:
    client = OPAClient(OPA_URL)
    decision = client.evaluate(
        build_opa_input(
            context(), action="read", client_id="E01", product="Trade finance", client_region="ZA"
        )
    )
    assert decision.allow is True


@pytest.mark.bank_lab
@bank_lab
@pytest.mark.parametrize(
    ("field", "value", "expected_reason"),
    [
        ("client_id", "E02", "CLIENT_NOT_ENTITLED"),
        ("client_region", "UK", "REGION_NOT_ENTITLED"),
        ("product", "Structured trade", "PRODUCT_NOT_ENTITLED"),
    ],
)
def test_the_real_policy_denies_each_dimension_independently(
    field: str, value: str, expected_reason: str
) -> None:
    """Client, region and product are enforced separately. A test that only
    varied client could not show that region is checked at all."""
    payload = build_opa_input(
        context(products=["Trade finance"]),
        action="read",
        client_id="E01",
        product="Trade finance",
        client_region="ZA",
    )
    payload[field] = value
    decision = OPAClient(OPA_URL).evaluate(payload)
    assert decision.allow is False
    assert expected_reason in decision.deny_reasons


@pytest.mark.bank_lab
@bank_lab
def test_the_real_policy_refuses_a_stale_workload_identity() -> None:
    payload = build_opa_input(
        context(), action="read", client_id="E01", product="Trade finance", client_region="ZA"
    )
    payload["workload_identity_age_seconds"] = 7200
    decision = OPAClient(OPA_URL).evaluate(payload)
    assert decision.allow is False
    assert "IDENTITY_INVALID" in decision.deny_reasons


@pytest.mark.bank_lab
@bank_lab
def test_the_real_policy_refuses_an_unauthenticated_identity() -> None:
    payload = build_opa_input(
        context(), action="read", client_id="E01", product="Trade finance", client_region="ZA"
    )
    payload["mfa_authenticated"] = False
    decision = OPAClient(OPA_URL).evaluate(payload)
    assert decision.allow is False
    assert "IDENTITY_INVALID" in decision.deny_reasons


@pytest.mark.bank_lab
@bank_lab
def test_the_real_policy_refuses_a_fixture_environment() -> None:
    payload = build_opa_input(
        context(environment=DeploymentEnvironment.FIXTURE),
        action="read",
        client_id="E01",
        product="Trade finance",
        client_region="ZA",
    )
    decision = OPAClient(OPA_URL).evaluate(payload)
    assert decision.allow is False
    assert "ENVIRONMENT_INVALID" in decision.deny_reasons


@pytest.mark.bank_lab
@bank_lab
def test_the_two_policies_do_not_diverge_on_the_governed_cases() -> None:
    """The test the whole arrangement exists for: OPA and the in-process ABAC
    must agree, and CI asserts the divergence log is empty."""
    gateway = DualEntitlementGateway(client=OPAClient(OPA_URL))
    cases = [
        (context(products=["Trade finance"]), "E01", "Trade finance", "ZA"),
        (context(products=["Trade finance"]), "E02", "Trade finance", "ZA"),
        (context(products=["Trade finance"]), "E01", "Structured trade", "ZA"),
    ]
    for principal, client_id, product, region in cases:
        gateway.authorize(
            context=principal,
            action="v1:opportunities:read",
            resource_type="opportunity",
            resource_id=f"{client_id}:{product}",
            client_id=client_id,
            product=product,
            client_region=region,
        )
    assert gateway.divergences() == [], (
        "the Rego policy and the in-process policy disagree; one of them has "
        "drifted and the system is deciding things nobody decided"
    )
