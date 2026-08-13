from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from wallet_twin_v2.api import app
from wallet_twin_v3.repository import repository
from wallet_twin_v2.canonical import write_canonical_json


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "v3_validation" / "v3_validation_report.json"


def main() -> None:
    client = TestClient(app)
    endpoint_status = {}
    for path in (
        "/v3/opportunities?as_of=2026-06-30&limit=1",
        "/v3/action-portfolio?as_of=2026-06-30",
        "/v3/evidence-acquisition?as_of=2026-06-30",
        "/v3/models/validation",
    ):
        response = client.get(path)
        endpoint_status[path] = response.status_code
        response.raise_for_status()
    report = {
        "metadata": repository.metadata,
        "validation": repository.validation,
        "endpoint_status": endpoint_status,
        "action_portfolio": repository.action_portfolio.model_dump(mode="json"),
        "evidence_acquisition": repository.evidence_acquisition.model_dump(mode="json"),
        "release": repository.release,
    }
    write_canonical_json(OUTPUT, report)
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(OUTPUT),
                "validation": repository.validation,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
