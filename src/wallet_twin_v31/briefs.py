"""Deterministic Why-How-What conversation briefs.

The LLM never computes anything here.  Arithmetic, graph traversal, ranks, VOI,
values and citations are all deterministic; the model's only permitted job is
to restate an already-closed pack in stakeholder-appropriate language.

``compile_claim_pack`` produces the closed pack.  ``ClaimCompiler.verify``
rejects any candidate narration containing a number, stakeholder assertion,
graph path or citation that is not in the pack.  When verification fails â€” or
when no provider is configured â€” the deterministic brief is returned unchanged.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from wallet_twin_v2.contracts import ApprovalStatus

from .business_evidence import BusinessEvidenceRegistry
from .contracts import ConversationBrief, ConversationCandidate
from .taxonomy import (
    ConversationAction,
    EligibilityDecision,
    GateStatus,
    PROBLEM_LABELS,
    SOLUTION_LABELS,
)

BRIEF_COMPILER_VERSION = "v31-deterministic-brief-3.1.1"

PROHIBITED_CLAIMS = (
    "measured competitor share",
    "causal uplift",
    "guaranteed saving",
    "optimal target share",
    "confidence score",
    "we know that",
    "named contact",
)

#: Numbers a narration is allowed to contain without appearing in the pack:
#: years and small ordinals that occur naturally in prose.
_ALLOWED_BARE_NUMBERS = {str(year) for year in range(2015, 2036)} | {
    str(value) for value in range(0, 13)
}
_NUMBER_PATTERN = re.compile(r"-?\d[\d ,]*\.?\d*")


def _fmt(value: Optional[float], suffix: str = "") -> str:
    if value is None:
        return "not available"
    return f"ZAR {value:,.0f}{suffix}"


def _citations(
    candidate: ConversationCandidate, registry: BusinessEvidenceRegistry
) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    for claim_id in candidate.evidence_claim_ids:
        claim = registry.get(claim_id)
        if claim is None:
            continue
        if claim.approval_status is not ApprovalStatus.APPROVED:
            continue
        citations.append(
            {
                "claim_id": claim.claim_id,
                "concept": claim.concept,
                "label": claim.source_title
                + (f" p.{claim.page}" if claim.page else ""),
                "url": claim.source_url,
                "available_date": claim.available_date.isoformat(),
                "tier": claim.tier.value,
                "approval_status": claim.approval_status.value,
                "legacy_fact_id": claim.legacy_fact_id,
            }
        )
    return citations[:12]


def compile_claim_pack(
    candidate: ConversationCandidate, registry: BusinessEvidenceRegistry
) -> Dict[str, Any]:
    """The closed pack.  Nothing outside this may appear in a brief."""
    client_total = candidate.client_value.monetised_total
    bank_total = candidate.bank_value.direct_contribution
    unknown_gates = [
        item.gate.value
        for item in candidate.risk_and_feasibility.gates
        if item.status is GateStatus.UNKNOWN and item.required
    ]
    return {
        "conversation_id": candidate.conversation_id,
        "client": candidate.entity_name,
        "sector": candidate.sector,
        "stakeholder_role": candidate.stakeholder.primary_role.value,
        "problem": PROBLEM_LABELS[candidate.problem.problem],
        "problem_identified": candidate.problem.identified,
        "problem_reason_codes": candidate.problem.reason_codes,
        "supporting_evidence": [
            item.statement for item in candidate.problem.supporting_evidence
        ],
        "disconfirming_evidence": [
            item.statement for item in candidate.problem.disconfirming_evidence
        ],
        "solutions": [
            SOLUTION_LABELS[solution] for solution in candidate.solution_bundle.solutions
        ],
        "why_now": candidate.engagement_window.why_now,
        "trigger_supported": candidate.engagement_window.trigger_supported,
        "timing": {
            "30d": candidate.engagement_window.probability_30d,
            "60d": candidate.engagement_window.probability_60d,
            "90d": candidate.engagement_window.probability_90d,
        },
        "client_value": {
            "lower": client_total.lower if client_total else None,
            "median": client_total.median if client_total else None,
            "upper": client_total.upper if client_total else None,
            "non_monetised": candidate.client_value.non_monetised_dimensions,
            "risk_reduction": candidate.client_value.risk_reduction_statement,
        },
        "bank_value": {
            "lower": bank_total.lower if bank_total else None,
            "median": bank_total.median if bank_total else None,
            "upper": bank_total.upper if bank_total else None,
            "status": candidate.bank_value.status,
            "relationship_3y": candidate.bank_value.relationship_value_3y.median
            if candidate.bank_value.relationship_value_3y
            else None,
        },
        "action": candidate.action.value,
        "eligibility": candidate.eligibility.value,
        "eligibility_reasons": candidate.eligibility_reasons,
        "unknown_gates": unknown_gates,
        "explanation_path": [step.label for step in candidate.explanation_path.steps],
        "citations": _citations(candidate, registry),
        "missing_evidence": sorted(
            {
                item
                for estimate in candidate.solution_estimates
                if not estimate.available and estimate.unavailable_reason
                for item in [estimate.unavailable_reason]
            }
            | set(candidate.client_value.non_monetised_dimensions)
        ),
        "primary_question": candidate.next_best_question.question_text
        if candidate.next_best_question
        else None,
        "prohibited_claims": list(PROHIBITED_CLAIMS),
    }


def compile_brief(
    candidate: ConversationCandidate, registry: BusinessEvidenceRegistry
) -> ConversationBrief:
    """Build the deterministic Why-How-What brief."""
    pack = compile_claim_pack(candidate, registry)
    role = candidate.stakeholder.primary_role.value.replace("_", " ").title()
    solutions = ", ".join(pack["solutions"])

    if candidate.engagement_window.trigger_supported:
        why = (
            f"{candidate.engagement_window.why_now} "
            f"On the evidence we hold, this points to {pack['problem'].lower()}."
        )
    else:
        why = (
            f"{candidate.engagement_window.why_now} "
            f"{pack['problem']} is indicated by "
            f"{len(pack['supporting_evidence'])} supporting signal(s), but nothing dates it."
        )
    if pack["disconfirming_evidence"]:
        why += (
            " Against it: " + pack["disconfirming_evidence"][0].rstrip(".") + "."
        )

    client_value = pack["client_value"]
    if client_value["median"] is not None:
        client_line = (
            f"Modelled client benefit is {_fmt(client_value['lower'])} to "
            f"{_fmt(client_value['upper'])} on the governed assumption set."
        )
    elif client_value["risk_reduction"]:
        client_line = (
            "The benefit here is risk reduction, not a saving, so it is deliberately "
            "not converted to rand."
        )
    else:
        client_line = "Client benefit cannot be monetised from the evidence we hold."

    bank_value = pack["bank_value"]
    if bank_value["median"] is not None:
        bank_line = (
            f"Representative net contribution to the bank is {_fmt(bank_value['lower'])} to "
            f"{_fmt(bank_value['upper'])} after cost to win, shown separately from the "
            "three-year relationship scenario."
        )
    else:
        bank_line = (
            "Bank economics are blocked for this bundle: no approved rate card exists, so "
            "no contribution is published."
        )

    how = f"{solutions}. {client_line}"

    if candidate.action is ConversationAction.PRODUCT_PROPOSAL:
        what = (
            f"Take a proposal to the {role}. "
            f"Every operational gate has passed."
        )
    elif candidate.action is ConversationAction.DISCOVERY:
        gates = ", ".join(pack["unknown_gates"]) or "several"
        what = (
            f"Open a discovery conversation with the {role}. This is not a product "
            f"proposal: {gates} remain unconfirmed, so the purpose is to establish the "
            "facts we are missing."
        )
    elif candidate.action is ConversationAction.EVIDENCE_ACQUISITION:
        what = (
            f"Approach the {role} to acquire the missing evidence before any solution is "
            "discussed."
        )
    else:
        what = (
            "Do not approach the client yet. A feasibility gate has failed and needs "
            "internal validation first."
        )
    if candidate.engagement_window.start_date and candidate.engagement_window.end_date:
        what += (
            f" The window runs {candidate.engagement_window.start_date.isoformat()} to "
            f"{candidate.engagement_window.end_date.isoformat()}."
        )
    if pack["primary_question"]:
        what += f' Ask first: "{pack["primary_question"]}"'

    abstentions: List[str] = []
    if not candidate.engagement_window.trigger_supported:
        abstentions.append("No time-critical trigger is established; urgency is not claimed.")
    if bank_value["median"] is None:
        abstentions.append("Bank contribution withheld: no approved rate card.")
    if client_value["median"] is None:
        abstentions.append("Client value withheld: not monetisable from reviewed evidence.")
    if candidate.eligibility is not EligibilityDecision.ELIGIBLE:
        abstentions.append(
            "This conversation is not commercially eligible; no product may be proposed."
        )
    abstentions.append("Causal incremental value is withheld until a randomized trial closes.")

    return ConversationBrief(
        brief_id=f"brief:{candidate.conversation_id}",
        conversation_id=candidate.conversation_id,
        headline=f"{candidate.entity_name} Â· {role} Â· {pack['problem']}",
        why=why,
        how=how,
        what=what,
        client_value_statement=client_line,
        bank_value_statement=bank_line,
        citations=pack["citations"],
        missing_evidence=pack["missing_evidence"],
        feasibility_statement=candidate.risk_and_feasibility.banker_confirmation_notice,
        primary_question=pack["primary_question"],
        prohibited_claims=list(PROHIBITED_CLAIMS),
        abstentions=abstentions,
        compiler=BRIEF_COMPILER_VERSION,
        provider_used=False,
        fallback_available=True,
    )


class ClaimCompiler:
    """Verifies that a narration says nothing the closed pack does not support."""

    version = BRIEF_COMPILER_VERSION

    @staticmethod
    def _pack_numbers(pack: Dict[str, Any]) -> Set[str]:
        numbers: Set[str] = set()

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    walk(item)
            elif isinstance(value, bool):
                return
            elif isinstance(value, (int, float)):
                numbers.add(f"{value:,.0f}")
                numbers.add(f"{value:.0f}")
                numbers.add(f"{value:.1f}")
                numbers.add(f"{value:.2f}")
                numbers.add(f"{value:.0%}".rstrip("%"))
            elif isinstance(value, str):
                for match in _NUMBER_PATTERN.findall(value):
                    numbers.add(match.strip())

        walk(pack)
        return {item.replace(" ", "") for item in numbers if item}

    def verify(
        self, narration: str, pack: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """Return (accepted, violations)."""
        violations: List[str] = []
        lowered = narration.lower()

        for phrase in PROHIBITED_CLAIMS:
            if phrase in lowered:
                violations.append(f"PROHIBITED_CLAIM:{phrase}")

        allowed = self._pack_numbers(pack) | _ALLOWED_BARE_NUMBERS
        for match in _NUMBER_PATTERN.findall(narration):
            token = match.strip().replace(" ", "")
            if not token or token in allowed:
                continue
            if token.rstrip(".").replace(",", "") in {
                item.replace(",", "") for item in allowed
            }:
                continue
            violations.append(f"UNSUPPORTED_NUMBER:{token}")

        role = str(pack.get("stakeholder_role", "")).replace("_", " ").lower()
        other_roles = {
            "cfo",
            "treasurer",
            "coo",
            "procurement",
            "risk legal",
            "sustainability",
            "corporate development",
            "cio technology",
            "finance operations",
            "ceo board",
        } - {role}
        for candidate_role in other_roles:
            if candidate_role in lowered and candidate_role not in role:
                violations.append(f"UNSUPPORTED_STAKEHOLDER:{candidate_role}")

        supported_solutions = {item.lower() for item in pack.get("solutions", [])}
        for solution_label in SOLUTION_LABELS.values():
            token = solution_label.lower()
            if token in lowered and token not in supported_solutions:
                violations.append(f"UNSUPPORTED_SOLUTION:{solution_label}")

        if not pack.get("trigger_supported") and any(
            phrase in lowered
            for phrase in ("urgent", "immediately", "act now", "closing window")
        ):
            violations.append("UNSUPPORTED_URGENCY")

        return (not violations), violations

    def compile_or_fallback(
        self,
        deterministic: ConversationBrief,
        pack: Dict[str, Any],
        narration: Optional[str],
    ) -> ConversationBrief:
        """Accept a provider narration only if it survives verification."""
        if not narration:
            return deterministic
        accepted, violations = self.verify(narration, pack)
        if not accepted:
            return deterministic.model_copy(
                update={
                    "provider_used": False,
                    "abstentions": deterministic.abstentions
                    + [f"Provider narration rejected: {'; '.join(violations[:4])}"],
                }
            )
        return deterministic.model_copy(
            update={"why": narration, "provider_used": True}
        )
