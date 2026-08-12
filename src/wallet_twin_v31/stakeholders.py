"""Stakeholder-role resolution.

Resolution uses a governed responsibility matrix, not a learned person-ranking
model.  There is no labelled dataset of "who actually owned this decision", so
a ranking model would be unfalsifiable; a matrix is at least reviewable by the
coverage team that has to live with it.

The resolver returns role personas.  Named individuals are unavailable in the
demonstration by design.  In a bank environment CRM resolution happens only
after an entitlement check and is never inferred by the LLM.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

from .contracts import StakeholderResolution
from .taxonomy import (
    BankingSolution,
    BusinessProblem,
    RESPONSIBILITY_MATRIX,
    RESPONSIBILITY_MATRIX_VERSION,
    SOLUTION_PERMITTED_ROLES,
    StakeholderRole,
    primary_solutions,
    supporting_solutions,
)

WEIGHT_SEMANTICS = (
    "GOVERNED_SCENARIO_WEIGHT — the share of comparable corporates where this role owns "
    "the decision, per the approved responsibility matrix. It is not a calibrated "
    "probability about this client and it must be confirmed by the RM."
)
NAMED_CONTACT_STATUS = "NAMED_CONTACT_UNAVAILABLE_IN_DEMONSTRATION"


class StakeholderResolver:
    version = RESPONSIBILITY_MATRIX_VERSION

    def resolve(
        self,
        entity_id: str,
        problem: BusinessProblem,
        *,
        bundle: Sequence[BankingSolution] = (),
        attestation_status: str = "NOT_ATTESTED",
    ) -> StakeholderResolution:
        rule = RESPONSIBILITY_MATRIX[problem]
        primary = rule.primary
        secondary: List[StakeholderRole] = list(rule.secondary)
        rationale = rule.rationale
        weight = rule.primary_weight

        if bundle:
            # A role that may not be approached about every solution in the
            # bundle cannot own the conversation.  Intersecting here is what
            # stops a DCM discussion being routed to procurement.
            permitted = set(SOLUTION_PERMITTED_ROLES[bundle[0]])
            for solution in bundle[1:]:
                permitted &= set(SOLUTION_PERMITTED_ROLES[solution])
            if primary not in permitted:
                fallback = next(
                    (role for role in secondary if role in permitted), None
                )
                if fallback is not None:
                    secondary = [primary] + [
                        role for role in secondary if role is not fallback
                    ]
                    primary = fallback
                    weight = max(0.30, rule.primary_weight - 0.20)
                    rationale = (
                        f"{rule.rationale} The matrix owner is not a permitted counterpart "
                        "for every solution in this bundle, so ownership moves to the "
                        "highest-ranked permitted secondary role."
                    )
                else:
                    weight = max(0.25, rule.primary_weight - 0.30)
                    rationale = (
                        f"{rule.rationale} No permitted role covers every solution in this "
                        "bundle, so the bundle requires RM confirmation before any approach."
                    )
            secondary = [role for role in secondary if role in permitted or role is primary]

        return StakeholderResolution(
            resolution_id=f"stakeholder:{entity_id}:{problem.value.lower()}",
            entity_id=entity_id,
            problem=problem,
            primary_role=primary,
            secondary_roles=[role for role in secondary if role is not primary][:2],
            responsibility_weight=weight,
            weight_semantics=WEIGHT_SEMANTICS,
            ownership_rationale=rationale,
            supporting_solutions=list(primary_solutions(problem))
            + list(supporting_solutions(problem)),
            requires_rm_confirmation=rule.requires_rm_confirmation,
            attestation_status=attestation_status,
            named_contact_status=NAMED_CONTACT_STATUS,
            matrix_version=RESPONSIBILITY_MATRIX_VERSION,
        )

    def resolve_all(self, entity_id: str) -> Dict[BusinessProblem, StakeholderResolution]:
        return {
            problem: self.resolve(entity_id, problem) for problem in BusinessProblem
        }
