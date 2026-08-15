"""Export the wallet-first V3.1.1 read model.

This exporter owns the wallet data. It deliberately does **not** own the
submission verdict: it runs before the live-provider comparison is evaluated,
so it always emits the pending placeholder that ``scripts/build_submission.py``
replaces once all verdict inputs resolve. Carrying a previous final status here
would make a BLOCKED -> READY transition impossible for the canonical builder.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wallet_twin_v2.canonical import canonical_value, write_canonical_json
from wallet_twin_v31.repository import repository
from wallet_twin_v31.wallet_portfolio import HACKATHON_STATUS_PENDING

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "app" / "data" / "wallet-v311-fixture.json"
MANIFEST = ROOT / "outputs" / "judging_manifest_v3.2.0.json"


def build_payload() -> dict[str, Any]:
    projection = repository.wallet_portfolio(repository.as_of)
    details = {
        cell.opportunity_id: repository.wallet_opportunity(
            cell.opportunity_id, repository.as_of
        ).model_dump(mode="json")
        for cell in projection.cells
    }
    return {
        "projection": projection.model_dump(mode="json"),
        "details": details,
    }


def verify_published_fixture(payload: dict[str, Any]) -> None:
    """Validate the final fixture without returning its status to pending.

    The canonical builder owns the release verdict. CI therefore regenerates
    the analytical payload in memory, proves that the published verdict agrees
    with the judging manifest, normalises only that owned field, and compares
    everything else exactly at published precision.
    """
    if not OUT.exists():
        raise RuntimeError(f"wallet fixture missing: {OUT.relative_to(ROOT)}")
    if not MANIFEST.exists():
        raise RuntimeError(f"judging manifest missing: {MANIFEST.relative_to(ROOT)}")

    published = json.loads(OUT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    generated_release = payload["projection"]["release"]
    published_release = published["projection"]["release"]

    if generated_release.get("hackathon_status") != HACKATHON_STATUS_PENDING:
        raise RuntimeError("wallet exporter no longer emits the governed pending placeholder")
    if published_release.get("hackathon_status") != manifest.get("status"):
        raise RuntimeError(
            "published wallet status disagrees with the judging manifest: "
            f"{published_release.get('hackathon_status')!r} != {manifest.get('status')!r}"
        )

    expected = canonical_value(payload)
    expected["projection"]["release"]["hackathon_status"] = manifest["status"]
    if expected != published:
        raise RuntimeError(
            "wallet fixture drifted from the regenerated analytical projection; "
            "run scripts/build_submission.py from the canonical source boundary"
        )


def main(*, check: bool = False) -> None:
    payload = build_payload()
    if check:
        verify_published_fixture(payload)
        print(f"verified {OUT.relative_to(ROOT)} without modifying it")
        return

    write_canonical_json(OUT, payload)
    stamped = payload["projection"]["release"]["hackathon_status"]
    print(
        f"wrote {OUT.relative_to(ROOT)} ({len(payload['projection']['cells'])} cells, "
        f"hackathon_status={stamped})"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without writing")
    arguments = parser.parse_args()
    main(check=arguments.check)
