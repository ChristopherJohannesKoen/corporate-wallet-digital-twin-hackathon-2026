"""Export the wallet-first V3.1.1 read model.

This exporter owns the wallet data. It deliberately does **not** own the
submission verdict: it runs before the live-provider comparison exists, so it
emits a pending placeholder that ``scripts/build_submission.py`` replaces once
that input resolves. A status already stamped by the canonical build is carried
forward rather than reset, which keeps repeated exports a fixed point and lets
CI's reproducibility gate cover this artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

from wallet_twin_v2.canonical import write_canonical_json
from wallet_twin_v31.repository import repository
from wallet_twin_v31.wallet_portfolio import HACKATHON_STATUS_PENDING


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "app" / "data" / "wallet-v311-fixture.json"


def previously_stamped_status(path: Path) -> str | None:
    """The verdict a prior canonical build wrote, if there was one."""
    if not path.exists():
        return None
    try:
        status = json.loads(path.read_text(encoding="utf-8"))["projection"]["release"][
            "hackathon_status"
        ]
    except (ValueError, KeyError, TypeError):
        return None
    return None if status == HACKATHON_STATUS_PENDING else status


def main() -> None:
    carried = previously_stamped_status(OUT)
    projection = repository.wallet_portfolio(repository.as_of)
    details = {
        cell.opportunity_id: repository.wallet_opportunity(
            cell.opportunity_id, repository.as_of
        ).model_dump(mode="json")
        for cell in projection.cells
    }
    payload = {
        "projection": projection.model_dump(mode="json"),
        "details": details,
    }
    if carried:
        payload["projection"]["release"]["hackathon_status"] = carried
    write_canonical_json(OUT, payload)
    stamped = payload["projection"]["release"]["hackathon_status"]
    print(
        f"wrote {OUT.relative_to(ROOT)} ({len(projection.cells)} cells, "
        f"hackathon_status={stamped})"
    )


if __name__ == "__main__":
    main()
