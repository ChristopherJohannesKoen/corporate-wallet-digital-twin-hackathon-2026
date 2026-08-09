from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import List

import numpy as np
from fastapi.testclient import TestClient

from .api import app
from .contracts import EventEnvelope, EventType
from .events import EventStore, new_event_id


def _canonical(events: List[EventEnvelope]) -> bytes:
    return json.dumps(
        [event.model_dump(mode="json") for event in events],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def api_load_rehearsal(requests: int = 300, workers: int = 16) -> dict:
    client = TestClient(app)

    def request(_: int) -> tuple[int, float]:
        started = time.perf_counter()
        response = client.get("/v1/opportunities?as_of=2026-06-30&limit=25")
        return response.status_code, (time.perf_counter() - started) * 1_000

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(request, range(requests)))
    elapsed = time.perf_counter() - started
    latencies = np.asarray([latency for _, latency in results])
    successes = sum(status == 200 for status, _ in results)
    return {
        "status": "LOCAL_IN_PROCESS_REHEARSAL_ONLY",
        "production_slo_claim_allowed": False,
        "requests": requests,
        "workers": workers,
        "successes": successes,
        "availability": successes / requests,
        "throughput_requests_per_second": requests / max(elapsed, 1e-9),
        "latency_ms": {
            "p50": float(np.quantile(latencies, 0.50)),
            "p95": float(np.quantile(latencies, 0.95)),
            "p99": float(np.quantile(latencies, 0.99)),
            "maximum": float(latencies.max()),
        },
        "local_target_pass": successes == requests and float(np.quantile(latencies, 0.95)) < 750,
    }


def entitlement_negative_rehearsal() -> dict:
    client = TestClient(app)
    cases = [
        client.get(
            "/v1/opportunities?as_of=2026-06-30",
            headers={"x-user-id": "negative-no-role", "x-user-clients": "*"},
        ),
        client.get(
            "/v1/clients/E01/twin?as_of=2026-06-30",
            headers={"x-user-id": "negative-client", "x-user-roles": "PILOT_RM", "x-user-clients": "E02"},
        ),
        client.post(
            "/v1/scenarios/evaluate",
            headers={
                "x-user-id": "negative-economics", "x-user-roles": "SHADOW_OPERATOR",
                "x-user-clients": "*", "x-user-products": "*", "content-type": "application/json",
            },
            json={"opportunity_id": "E02-trade-finance", "as_of": "2026-06-30", "target_share": 0.40},
        ),
    ]
    statuses = [response.status_code for response in cases]
    return {
        "cases": len(cases),
        "expected_denials": 3,
        "actual_denials": sum(status == 403 for status in statuses),
        "statuses": statuses,
        "pass_rate": sum(status == 403 for status in statuses) / len(cases),
    }


def event_recovery_rehearsal(event_count: int = 500) -> dict:
    store = EventStore()
    for index in range(event_count):
        store.append(EventEnvelope(
            event_id=new_event_id(),
            event_type=EventType.ELIGIBILITY_RECORDED,
            entity_id=f"E{index % 20 + 1:02d}",
            product="Collections",
            occurred_at=datetime.now(timezone.utc),
            payload={"sequence": index, "synthetic_recovery_rehearsal": True},
        ))
    original = _canonical(store.list())
    restored = [EventEnvelope.model_validate(item) for item in json.loads(original)]
    restored_bytes = _canonical(restored)
    return {
        "status": "LOCAL_SERIALIZATION_RECOVERY_REHEARSAL",
        "events": event_count,
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "restored_sha256": hashlib.sha256(restored_bytes).hexdigest(),
        "byte_identical": original == restored_bytes,
        "production_rpo_rto_claim_allowed": False,
        "remaining_gate": "bank backup restore and regional failover exercise",
    }


def thirty_day_shadow_rehearsal() -> dict:
    days = []
    for day in range(1, 31):
        days.append({
            "day": day,
            "pipeline_completed": True,
            "reconciliation_passed": True,
            "unsupported_critical_claims": 0,
            "entitlement_breaches": 0,
            "sev1_sev2": 0,
        })
    return {
        "status": "SYNTHETIC_30_DAY_CONTROL_REHEARSAL",
        "days": len(days),
        "clean_days": sum(all((item["pipeline_completed"], item["reconciliation_passed"], item["unsupported_critical_claims"] == 0, item["entitlement_breaches"] == 0, item["sev1_sev2"] == 0)) for item in days),
        "production_consecutive_shadow_days": 0,
        "production_gate_passed": False,
        "reason": "Simulated calendar days cannot satisfy an elapsed production operating-period gate.",
    }


def run_operational_rehearsal() -> dict:
    return {
        "version": "local-operational-rehearsal-1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "load": api_load_rehearsal(),
        "entitlements": entitlement_negative_rehearsal(),
        "recovery": event_recovery_rehearsal(),
        "shadow_period": thirty_day_shadow_rehearsal(),
    }
