"""Risk and operational feasibility gates.

Six gates are assessed for every solution bundle.  The rules are deliberately
blunt:

* any ``FAIL`` blocks the bundle;
* any material ``UNKNOWN`` converts the action into discovery or validation â€”
  it never silently becomes a ``PASS``;
* only an all-required-``PASS`` bundle can support a product proposal, and only
  in pilot or production.

Risk and implementation friction are kept as separate dimensions rather than
folded into the commercial score.  A high-friction, low-risk conversation and a
low-friction, high-risk one are different problems for a banker, and averaging
them into one number hides that.

In the demonstration boundary the bank's own credit, compliance and operational
systems are not connected, so those gates are ``UNKNOWN`` by construction.  That
is the honest answer, and it is why the demo produces discovery conversations
rather than product proposals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Mapping, Optional, Sequence

from .contracts import FeasibilityAssessment, GateResult, SolutionBundle, SolutionEstimate
from .taxonomy import (
    BankingSolution as S,
    ConversationAction,
    FeasibilityGate as G,
    GateStatus,
    SOLUTION_FAMILY,
    SolutionFamily,
)

FEASIBILITY_POLICY_VERSION = "v31-feasibility-policy-3.1.1"

BANKER_CONFIRMATION_NOTICE = (
    "Credit, compliance and operational feasibility are not connected in this "
    "demonstration. Every gate shown as UNKNOWN requires banker confirmation before any "
    "product is proposed to a client."
)

#: Solutions the bank is assumed to be able to deliver in the demonstration.
#: The five V3 products are already live in the simulation; the rest are
#: capability assumptions that a product forum would have to confirm.
DEMONSTRATED_CAPABILITY = frozenset(
    {
        S.COLLECTIONS,
        S.PAYMENTS,
        S.LIQUIDITY_CASH_MANAGEMENT,
        S.CROSS_BORDER_FX,
        S.TRADE_FINANCE,
    }
)

#: Families that always require a credit or contingent limit.
CREDIT_REQUIRED_FAMILIES = frozenset(
    {
        SolutionFamily.LENDING,
        SolutionFamily.TRADE_AND_WORKING_CAPITAL,
        SolutionFamily.CAPITAL_MARKETS,
    }
)
#: Families that always require derivative documentation.
ISDA_REQUIRED = frozenset(
    {S.INTEREST_RATE_RISK_MANAGEMENT, S.COMMODITY_RISK_MANAGEMENT}
)
#: Families with heavy client-side systems integration.
INTEGRATION_HEAVY = frozenset(
    {S.PAYMENTS, S.COLLECTIONS, S.LIQUIDITY_CASH_MANAGEMENT, S.SUPPLY_CHAIN_FINANCE}
)

#: Relative implementation friction per family, 0-1.  Governed policy.
FAMILY_FRICTION: Mapping[SolutionFamily, float] = {
    SolutionFamily.TRANSACTION_BANKING: 0.55,
    SolutionFamily.RISK_MANAGEMENT: 0.25,
    SolutionFamily.TRADE_AND_WORKING_CAPITAL: 0.70,
    SolutionFamily.LENDING: 0.45,
    SolutionFamily.CAPITAL_MARKETS: 0.65,
    SolutionFamily.ADVISORY_AND_AGENCY: 0.50,
}
#: Relative delivery risk per family, 0-1.  Governed policy, separate from friction.
FAMILY_RISK: Mapping[SolutionFamily, float] = {
    SolutionFamily.TRANSACTION_BANKING: 0.20,
    SolutionFamily.RISK_MANAGEMENT: 0.45,
    SolutionFamily.TRADE_AND_WORKING_CAPITAL: 0.50,
    SolutionFamily.LENDING: 0.60,
    SolutionFamily.CAPITAL_MARKETS: 0.55,
    SolutionFamily.ADVISORY_AND_AGENCY: 0.40,
}

#: Jurisdictions in the fixture that would require additional legal review.
HIGH_REVIEW_JURISDICTIONS = frozenset({"DRC", "Zimbabwe", "Sudan", "Myanmar"})


class FeasibilityEngine:
    version = FEASIBILITY_POLICY_VERSION

    def assess(
        self,
        entity_id: str,
        bundle: SolutionBundle,
        estimates: Sequence[SolutionEstimate],
        *,
        corridors: Sequence[str] = (),
        attestations: Optional[Mapping[str, GateResult]] = None,
    ) -> FeasibilityAssessment:
        solutions = bundle.solutions
        families = {SOLUTION_FAMILY[solution] for solution in solutions}
        attestations = dict(attestations or {})
        gates: List[GateResult] = []

        # 1 product capability
        unsupported = [
            solution for solution in solutions if solution not in DEMONSTRATED_CAPABILITY
        ]
        if not unsupported:
            gates.append(
                GateResult(
                    gate=G.PRODUCT_CAPABILITY,
                    status=GateStatus.PASS,
                    required=True,
                    reason="Every solution in this bundle is already delivered to this client base.",
                )
            )
        else:
            gates.append(
                GateResult(
                    gate=G.PRODUCT_CAPABILITY,
                    status=GateStatus.UNKNOWN,
                    required=True,
                    reason=(
                        "Product capability is not confirmed for "
                        + ", ".join(item.value for item in unsupported)
                        + " in this demonstration boundary."
                    ),
                    required_confirmation="product forum capability confirmation",
                )
            )

        # 2 credit and risk
        needs_credit = bool(families & CREDIT_REQUIRED_FAMILIES)
        gates.append(
            GateResult(
                gate=G.CREDIT_AND_RISK,
                status=GateStatus.UNKNOWN if needs_credit else GateStatus.NOT_REQUIRED,
                required=needs_credit,
                reason=(
                    "A credit or contingent limit is required and no bank credit system is "
                    "connected in this demonstration."
                    if needs_credit
                    else "This bundle creates no funded or contingent credit exposure."
                ),
                required_confirmation="approved credit or contingent limit"
                if needs_credit
                else None,
            )
        )

        # 3 compliance and conduct
        gates.append(
            GateResult(
                gate=G.COMPLIANCE_AND_CONDUCT,
                status=GateStatus.UNKNOWN,
                required=True,
                reason=(
                    "Client due diligence, sanctions screening and conduct suitability are "
                    "not connected in this demonstration."
                ),
                required_confirmation="compliance and conduct sign-off",
            )
        )

        # 4 legal and jurisdiction
        flagged = sorted(set(corridors) & HIGH_REVIEW_JURISDICTIONS)
        needs_isda = bool(set(solutions) & ISDA_REQUIRED)
        if flagged or needs_isda:
            reason_parts = []
            if flagged:
                reason_parts.append(
                    "Observed corridors include " + ", ".join(flagged) + ", which require "
                    "additional jurisdictional review."
                )
            if needs_isda:
                reason_parts.append(
                    "Derivative solutions require executed ISDA/CSA documentation, which is "
                    "not confirmed."
                )
            gates.append(
                GateResult(
                    gate=G.LEGAL_AND_JURISDICTION,
                    status=GateStatus.UNKNOWN,
                    required=True,
                    reason=" ".join(reason_parts),
                    required_confirmation="legal and jurisdictional review",
                )
            )
        else:
            gates.append(
                GateResult(
                    gate=G.LEGAL_AND_JURISDICTION,
                    status=GateStatus.PASS,
                    required=True,
                    reason=(
                        "No flagged jurisdiction and no derivative documentation requirement "
                        "applies to this bundle."
                    ),
                )
            )

        # 5 operations and onboarding
        gates.append(
            GateResult(
                gate=G.OPERATIONS_AND_ONBOARDING,
                status=GateStatus.UNKNOWN,
                required=True,
                reason=(
                    "Account opening, mandate and onboarding capacity are not connected in "
                    "this demonstration."
                ),
                required_confirmation="operations and onboarding capacity confirmation",
            )
        )

        # 6 technology and integration
        integration_heavy = bool(set(solutions) & INTEGRATION_HEAVY)
        gates.append(
            GateResult(
                gate=G.TECHNOLOGY_AND_INTEGRATION,
                status=GateStatus.UNKNOWN
                if integration_heavy
                else GateStatus.NOT_REQUIRED,
                required=integration_heavy,
                reason=(
                    "Client ERP, host-to-host and file-format constraints are unknown."
                    if integration_heavy
                    else "This bundle requires no client-side systems integration."
                ),
                required_confirmation="client ERP and connectivity assessment"
                if integration_heavy
                else None,
            )
        )

        gates = [attestations.get(result.gate.value, result) for result in gates]

        failed = [item for item in gates if item.status is GateStatus.FAIL]
        material_unknowns = [
            item.gate
            for item in gates
            if item.status is GateStatus.UNKNOWN and item.required
        ]
        blocked = bool(failed)

        if blocked:
            action = ConversationAction.VALIDATION
        elif material_unknowns:
            action = ConversationAction.DISCOVERY
        else:
            action = ConversationAction.PRODUCT_PROPOSAL

        friction = max(FAMILY_FRICTION[family] for family in families)
        risk = max(FAMILY_RISK[family] for family in families)
        prerequisites = sorted(
            {
                prerequisite
                for solution in solutions
                for prerequisite in bundle.prerequisites
            }
            | {
                item.required_confirmation
                for item in gates
                if item.required_confirmation
            }
        )
        passed_required = sum(
            1
            for item in gates
            if item.required and item.status is GateStatus.PASS
        )
        required_total = sum(1 for item in gates if item.required) or 1
        multiplier = 0.0 if blocked else max(0.15, passed_required / required_total)

        return FeasibilityAssessment(
            assessment_id=f"feasibility:{entity_id}:{bundle.bundle_id}",
            entity_id=entity_id,
            bundle_id=bundle.bundle_id,
            gates=gates,
            blocked=blocked,
            material_unknowns=material_unknowns,
            permitted_action=action,
            friction_score=friction,
            risk_score=risk,
            feasibility_multiplier=multiplier,
            required_confirmations=prerequisites,
            banker_confirmation_notice=BANKER_CONFIRMATION_NOTICE,
            policy_version=FEASIBILITY_POLICY_VERSION,
        )


def record_attestation(
    gate: G,
    status: GateStatus,
    *,
    role: str,
    reason: str,
    at: Optional[datetime] = None,
) -> GateResult:
    """Record an entitled banker's validation of one operational gate."""
    if status is GateStatus.UNKNOWN:
        raise ValueError("an attestation must resolve the gate, not restate the unknown")
    return GateResult(
        gate=gate,
        status=status,
        required=True,
        reason=reason,
        attested_by_role=role,
        attested_at=at or datetime.now(timezone.utc),
    )
