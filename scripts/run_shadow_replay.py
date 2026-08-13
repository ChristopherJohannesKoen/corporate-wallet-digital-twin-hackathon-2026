from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.contracts import DeploymentEnvironment, EntitlementContext, EventEnvelope, EventType
from wallet_twin_v2.events import ClusterRandomizedEncouragement, EventStore, new_event_id
from wallet_twin_v2.fixtures import build_fixture
from wallet_twin_v2.canonical import (
    EVENT_STREAM_VOLATILE_FIELDS,
    artifact_timestamp,
    content_digest,
)


def main() -> None:
    fixture = build_fixture()
    store = EventStore()
    assigner = ClusterRandomizedEncouragement()
    context = EntitlementContext(
        user_id="shadow-engine", roles=["WORKLOAD"], team="shadow-team-01", regions=["ZA"],
        client_ids=list(fixture["clients"]), products=["Collections", "Payments", "Liquidity", "Cross-border FX", "Trade finance"],
        environment=DeploymentEnvironment.SHADOW,
    )
    for opportunity in fixture["opportunities"]:
        store.append(EventEnvelope(
            event_id=new_event_id(), event_type=EventType.ELIGIBILITY_RECORDED,
            entity_id=opportunity.entity_id, product=opportunity.product,
            recommendation_id=opportunity.opportunity_id, as_of=opportunity.as_of,
            evidence_tier=opportunity.evidence_tier, rank=opportunity.rank,
            reason_codes=opportunity.eligibility.reason_codes, artifacts=opportunity.artifacts,
            entitlement_context=context, payload={"state": opportunity.eligibility.state.value, "rm_visible": False},
        ))
        store.append(assigner.assign(
            cluster_id=f"team-{int(opportunity.entity_id[1:]) % 8:02d}", recommendation_id=opportunity.opportunity_id,
            entity_id=opportunity.entity_id, product=opportunity.product, as_of=opportunity.as_of,
            artifacts=opportunity.artifacts, entitlement_context=context,
        ))
    serialized = [event.model_dump(mode="json") for event in store.list()]
    summary = {
        "replay_version": "local-shadow-replay-1.0.0",
        "generated_at": artifact_timestamp(),
        "watermark": "SYNTHETIC SHADOW REPLAY — NO RM EXPOSURE",
        "recommendations_visible_to_rm": False,
        "events": len(serialized),
        "event_types": dict(Counter(event["event_type"] for event in serialized)),
        # Content digest over the business payload only. Event envelopes carry a
        # real emission instant and a freshly minted UUID, so hashing those would
        # change every run and the digest could never detect the content drift it
        # exists to catch.
        "event_stream_sha256": content_digest(serialized, EVENT_STREAM_VOLATILE_FIELDS),
        "event_stream_digest_scope": (
            "business payload; emission timestamps and per-run identifiers excluded"
        ),
        "production_release_allowed": False,
    }
    output = ROOT / "outputs" / "v2_validation" / "shadow_replay_summary.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
