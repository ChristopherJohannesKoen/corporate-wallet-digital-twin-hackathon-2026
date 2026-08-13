"""Point-in-time "what changed?" digest.

The digest answers a narrow question honestly: between ``since`` and ``as_of``,
what new evidence became *available* and what dated events fall inside the
window?  Availability date â€” not period end and not ingestion date â€” is the
only admissible clock, so a document published after ``since`` counts as a
change even when it reports an older period, and a document that existed
before ``since`` never does.

When nothing changed the digest says so explicitly rather than rendering an
empty panel.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Mapping, Sequence

from wallet_twin_v2.contracts import ApprovalStatus

from .business_evidence import BusinessEvidenceRegistry
from .business_twin import DOMAIN_MATERIALITY
from .contracts import BusinessEvent, ChangeDigest, ChangeDigestItem
from .taxonomy import DOMAIN_LABELS

DIGEST_VERSION = "v31-change-digest-3.1.1"


class ChangeDigestBuilder:
    version = DIGEST_VERSION

    def __init__(
        self,
        registry: BusinessEvidenceRegistry,
        events: Mapping[str, Sequence[BusinessEvent]],
        as_of: date,
    ) -> None:
        self.registry = registry
        self.events = events
        self.as_of = as_of

    def build(self, entity_id: str, since: date) -> ChangeDigest:
        if since > self.as_of:
            raise ValueError("since must not exceed as_of")
        items: List[ChangeDigestItem] = []

        new_claims = [
            claim
            for claim in self.registry.claims_for(entity_id)
            if since < claim.available_date <= self.as_of
        ]
        by_domain: Dict[str, List[str]] = {}
        for claim in new_claims:
            for domain in claim.domains:
                by_domain.setdefault(domain.value, []).append(claim.claim_id)
        for domain_value, claim_ids in sorted(by_domain.items()):
            domain = next(item for item in DOMAIN_LABELS if item.value == domain_value)
            approved = [
                claim_id
                for claim_id in claim_ids
                if (claim := self.registry.get(claim_id)) is not None
                and claim.approval_status is ApprovalStatus.APPROVED
            ]
            items.append(
                ChangeDigestItem(
                    change_type="NEW_EVIDENCE",
                    subject=DOMAIN_LABELS[domain],
                    before=None,
                    after=(
                        f"{len(claim_ids)} claim(s) became available "
                        f"({len(approved)} approved, {len(claim_ids) - len(approved)} awaiting review)"
                    ),
                    materiality=DOMAIN_MATERIALITY[domain],
                    evidence_claim_ids=sorted(claim_ids)[:12],
                    decision_impact=(
                        "May change problem intensity, indicator status and eligibility"
                        if approved
                        else "Cannot change eligibility until finance-SME review completes"
                    ),
                )
            )

        for event in self.events.get(entity_id, ()):
            if not since < event.available_date <= self.as_of:
                continue
            items.append(
                ChangeDigestItem(
                    change_type="NEW_EVENT",
                    subject=event.event_type,
                    before=None,
                    after=event.label,
                    materiality=max(
                        (DOMAIN_MATERIALITY[domain] for domain in event.affected_domains),
                        default=0.5,
                    ),
                    evidence_claim_ids=list(event.evidence_claim_ids),
                    decision_impact=(
                        "Implies "
                        + ", ".join(item.value for item in event.implied_problems)
                        if event.implied_problems
                        else "No problem hypothesis implied"
                    ),
                )
            )

        items.sort(key=lambda item: (-item.materiality, item.change_type, item.subject))
        return ChangeDigest(
            digest_id=f"digest:{entity_id}:{since.isoformat()}:{self.as_of.isoformat()}",
            entity_id=entity_id,
            since=since,
            as_of=self.as_of,
            items=items,
            no_change_statement=None
            if items
            else (
                "No new evidence became available and no dated event falls inside this "
                "window. Nothing about this client has changed for decision purposes."
            ),
        )

    def build_all(self, since: date) -> Dict[str, ChangeDigest]:
        return {
            entity_id: self.build(entity_id, since)
            for entity_id in sorted(
                {claim.entity_id for claim in self.registry.claims}
            )
        }
