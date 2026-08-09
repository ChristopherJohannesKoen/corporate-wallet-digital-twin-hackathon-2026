from __future__ import annotations

import hashlib
from typing import Optional

from .contracts import AccessDecision, DeploymentEnvironment, EntitlementContext


SHADOW_ROLES = {"SHADOW_OPERATOR", "MODEL_VALIDATOR", "EVIDENCE_REVIEWER", "PILOT_RM", "PLATFORM_ADMIN"}
SENSITIVE_ECONOMICS_ROLES = {"PRODUCT_FINANCE", "TREASURY", "RISK", "PLATFORM_ADMIN"}


class EntitlementService:
    """Deny-by-default ABAC reference policy.

    Production deployment also evaluates the equivalent OPA policy at the
    gateway and enforces Unity Catalog row filters in the analytical plane.
    """

    version = "abac-2.0.0"

    def authorize(
        self,
        *,
        context: Optional[EntitlementContext],
        action: str,
        resource_type: str,
        resource_id: str,
        client_id: Optional[str] = None,
        product: Optional[str] = None,
        sensitive_economics: bool = False,
        shadow_only: bool = True,
    ) -> AccessDecision:
        reasons = []
        if context is None:
            reasons.append("IDENTITY_MISSING")
        else:
            roles = set(context.roles)
            if shadow_only and not roles.intersection(SHADOW_ROLES):
                reasons.append("SHADOW_ROLE_REQUIRED")
            if client_id and "*" not in context.client_ids and client_id not in context.client_ids:
                reasons.append("CLIENT_NOT_ENTITLED")
            if product and context.products and "*" not in context.products and product not in context.products:
                reasons.append("PRODUCT_NOT_ENTITLED")
            if sensitive_economics and not roles.intersection(SENSITIVE_ECONOMICS_ROLES):
                reasons.append("SENSITIVE_ECONOMICS_ROLE_REQUIRED")
            if action.startswith("evidence:approve") and "EVIDENCE_REVIEWER" not in roles and "PLATFORM_ADMIN" not in roles:
                reasons.append("EVIDENCE_REVIEWER_ROLE_REQUIRED")
            if context.environment == DeploymentEnvironment.PRODUCTION and context.user_id.startswith("demo-"):
                reasons.append("DEMO_IDENTITY_FORBIDDEN_IN_PRODUCTION")

        return AccessDecision(
            allowed=not reasons,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            reason_codes=reasons or ["POLICY_ALLOWED"],
        )

    @staticmethod
    def privacy_safe_identifier(user_id: str) -> str:
        return hashlib.sha256(user_id.encode("utf-8")).hexdigest()
