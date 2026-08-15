"""OPA in the request path, with the in-process policy as defence in depth.

Before this module, ``WALLET_OPA_URL`` was configured, validated, and never
called. The OPA container ran, the Rego policy was linted by
``production_target``, and every actual authorisation decision was computed
in-process by :class:`~wallet_twin_v2.entitlements.EntitlementService`. A policy
engine nothing consults is documentation, not a control — the same defect the
V3.2 gate catalogue fixed for ``mlflow_promotion_policy.json``.

**Two policies, and disagreement is a denial.**

In a bank deployment OPA at the gateway is authoritative and the in-process
ABAC is defence in depth. When they agree, the decision is the decision. When
they disagree, one of them is wrong and there is no way to tell which from
inside the request, so the request is denied and the divergence is recorded.

That is not paranoia. Two policies that drift apart silently is the failure
mode this arrangement is most likely to produce: the Rego is edited without the
Python, or the reverse, and the system starts allowing or refusing things
nobody decided. A denial on divergence turns a silent drift into a visible,
loud one — and :meth:`DualEntitlementGateway.divergences` gives CI something to
assert is empty.

The gateway is **inactive unless an OPA URL is configured**, so fixture and
test deployments keep the existing in-process behaviour unchanged.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .contracts import AccessDecision, DeploymentEnvironment, EntitlementContext
from .entitlements import EntitlementService

OPA_GATEWAY_VERSION = "v2-opa-request-path-1.0.0"

#: The decision document the Rego policy publishes.
DEFAULT_DECISION_PATH = "/v1/data/wallet/entitlements"


class OPAUnavailableError(RuntimeError):
    """OPA could not be reached or returned an unusable response.

    Deliberately not caught-and-allowed anywhere in this module. An
    authorisation service that fails open is worse than no authorisation
    service, because it looks like one.
    """


@dataclass(frozen=True)
class OPADecision:
    allow: bool
    deny_reasons: List[str]
    raw: Dict[str, Any] = field(default_factory=dict)


class OPAClient:
    """Minimal OPA data-API client.

    Uses ``urllib`` rather than adding an HTTP dependency: the call is one POST
    with a JSON body, and the runtime already refuses a non-HTTPS OPA URL
    outside fixture mode via ``RuntimeConfig.validate``.
    """

    def __init__(
        self,
        url: str,
        *,
        decision_path: str = DEFAULT_DECISION_PATH,
        timeout_seconds: float = 2.0,
    ) -> None:
        if not url:
            raise ValueError("OPA URL is required")
        self.url = url.rstrip("/")
        self.decision_path = decision_path
        self.timeout_seconds = timeout_seconds

    def evaluate(self, payload: Dict[str, Any]) -> OPADecision:
        request = urllib.request.Request(
            f"{self.url}{self.decision_path}",
            data=json.dumps({"input": payload}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            raise OPAUnavailableError(f"OPA evaluation failed: {error}") from error

        result = body.get("result")
        if not isinstance(result, dict) or "allow" not in result:
            # An OPA response without an `allow` key means the policy package
            # is missing or renamed. Treating that as "not allowed" would mask a
            # deployment error as a routine denial.
            raise OPAUnavailableError(
                f"OPA returned no decision at {self.decision_path}; "
                "the policy package is missing or misnamed"
            )
        return OPADecision(
            allow=bool(result["allow"]),
            deny_reasons=sorted(result.get("deny_reasons", []) or []),
            raw=result,
        )


def build_opa_input(
    context: EntitlementContext,
    *,
    action: str,
    client_id: Optional[str] = None,
    product: Optional[str] = None,
    client_region: Optional[str] = None,
    mfa_authenticated: bool = True,
    workload_identity_age_seconds: int = 0,
) -> Dict[str, Any]:
    """Shape a request into the input document the Rego policy expects.

    The field names are the policy's, not the codebase's. Keeping the mapping
    here in one function means a Rego rename breaks in a single place rather
    than producing silent denials scattered across the request path.
    """
    return {
        "user_id": context.user_id,
        "roles": list(context.roles),
        "environment": context.environment.value
        if isinstance(context.environment, DeploymentEnvironment)
        else str(context.environment),
        "mfa_authenticated": mfa_authenticated,
        "workload_identity_age_seconds": workload_identity_age_seconds,
        "action": action,
        "client_id": client_id or "",
        "client_region": client_region or "",
        "product": product or "",
        "allowed_client_ids": list(context.client_ids),
        "allowed_regions": list(context.regions),
        "allowed_products": list(context.products),
    }


@dataclass
class Divergence:
    """One request where OPA and the in-process policy disagreed."""

    action: str
    resource_id: str
    opa_allowed: bool
    local_allowed: bool
    opa_reasons: List[str]
    local_reasons: List[str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "resource_id": self.resource_id,
            "opa_allowed": self.opa_allowed,
            "local_allowed": self.local_allowed,
            "opa_reasons": self.opa_reasons,
            "local_reasons": self.local_reasons,
        }


class DualEntitlementGateway:
    """Evaluate both policies; deny and record when they disagree.

    ``enabled`` is false when no OPA URL is configured, in which case this is a
    transparent pass-through to the in-process service and behaviour is
    identical to before this module existed. That keeps fixture deployments and
    the entire existing test suite unaffected.
    """

    version = OPA_GATEWAY_VERSION

    def __init__(
        self,
        local: Optional[EntitlementService] = None,
        client: Optional[OPAClient] = None,
    ) -> None:
        self.local = local or EntitlementService()
        self.client = client
        self._divergences: List[Divergence] = []
        self._lock = threading.RLock()

    @classmethod
    def from_env(cls, local: Optional[EntitlementService] = None) -> "DualEntitlementGateway":
        from .runtime_config import RuntimeConfig

        url = RuntimeConfig.from_env().opa_url
        return cls(local=local, client=OPAClient(url) if url else None)

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def divergences(self) -> List[Dict[str, Any]]:
        """Requests where the two policies disagreed.

        CI asserts this is empty. A non-empty list means the Rego and the Python
        have drifted and the system is refusing requests nobody decided to
        refuse — or, worse, was about to allow one.
        """
        with self._lock:
            return [item.as_dict() for item in self._divergences]

    def authorize(
        self,
        *,
        context: Optional[EntitlementContext],
        action: str,
        resource_type: str,
        resource_id: str,
        client_id: Optional[str] = None,
        product: Optional[str] = None,
        client_region: Optional[str] = None,
        sensitive_economics: bool = False,
        shadow_only: bool = True,
    ) -> AccessDecision:
        local_decision = self.local.authorize(
            context=context,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            client_id=client_id,
            product=product,
            client_region=client_region,
            sensitive_economics=sensitive_economics,
            shadow_only=shadow_only,
        )
        if not self.enabled or context is None:
            return local_decision

        # OPA's policy covers read / approve_evidence / read_sensitive_economics.
        # Actions outside that vocabulary are not something the gateway can
        # adjudicate, so the in-process decision stands rather than being
        # compared against a rule that does not exist.
        opa_action = _opa_action_for(action, sensitive_economics=sensitive_economics)
        if opa_action is None:
            return local_decision

        opa_decision = self.client.evaluate(  # type: ignore[union-attr]
            build_opa_input(
                context,
                action=opa_action,
                client_id=client_id,
                product=product,
                client_region=client_region,
            )
        )

        if opa_decision.allow == local_decision.allowed:
            reasons = local_decision.reason_codes if not opa_decision.allow else ["POLICY_ALLOWED"]
            return AccessDecision(
                allowed=opa_decision.allow,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                reason_codes=sorted(set(reasons) | set(opa_decision.deny_reasons))
                if not opa_decision.allow
                else ["POLICY_ALLOWED", "OPA_AND_LOCAL_AGREE"],
            )

        with self._lock:
            self._divergences.append(
                Divergence(
                    action=action,
                    resource_id=resource_id,
                    opa_allowed=opa_decision.allow,
                    local_allowed=local_decision.allowed,
                    opa_reasons=opa_decision.deny_reasons,
                    local_reasons=list(local_decision.reason_codes),
                )
            )
        # Fail closed. One of the two policies is wrong and the request cannot
        # tell which, so the only safe outcome is a denial that is visible.
        return AccessDecision(
            allowed=False,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            reason_codes=[
                "POLICY_DIVERGENCE_DENIED",
                f"OPA_ALLOWED_{opa_decision.allow}",
                f"LOCAL_ALLOWED_{local_decision.allowed}",
                *opa_decision.deny_reasons,
                *local_decision.reason_codes,
            ],
        )


def _opa_action_for(action: str, *, sensitive_economics: bool) -> Optional[str]:
    """Map an internal action onto the Rego policy's action vocabulary."""
    if action.startswith("evidence:approve"):
        return "approve_evidence"
    if sensitive_economics:
        return "read_sensitive_economics"
    if action.endswith(":read") or ":read" in action:
        return "read"
    return None


def gateway_report(gateway: DualEntitlementGateway) -> Dict[str, Any]:
    """Publishable statement of whether OPA is actually in the request path."""
    return {
        "gateway_version": gateway.version,
        "opa_in_request_path": gateway.enabled,
        "local_policy_version": gateway.local.version,
        "divergences": gateway.divergences(),
        "divergence_policy": (
            "A disagreement between OPA and the in-process policy denies the "
            "request and is recorded. Two policies drifting apart silently is "
            "the failure this arrangement is most likely to produce; denying "
            "turns a silent drift into a loud one."
        ),
        "when_disabled": (
            "With no WALLET_OPA_URL configured the gateway is a transparent "
            "pass-through to the in-process policy, so fixture deployments "
            "behave exactly as they did before OPA was wired in."
        ),
        "fail_closed": (
            "OPA being unreachable raises rather than allowing. An "
            "authorisation service that fails open is worse than none, because "
            "it looks like one."
        ),
    }


__all__ = [
    "DEFAULT_DECISION_PATH",
    "OPA_GATEWAY_VERSION",
    "Divergence",
    "DualEntitlementGateway",
    "OPAClient",
    "OPADecision",
    "OPAUnavailableError",
    "build_opa_input",
    "gateway_report",
]
