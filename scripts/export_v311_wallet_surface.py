"""Export the wallet-first V3.1.1 read model.

This exporter owns the wallet data. It deliberately does **not** own the
submission verdict: it runs before the live-provider comparison is evaluated,
so it always emits the pending placeholder that ``scripts/build_submission.py``
replaces once all verdict inputs resolve. Carrying a previous final status here
would make a BLOCKED -> READY transition impossible for the canonical builder.
"""

from __future__ import annotations

from pathlib import Path

from wallet_twin_v2.canonical import write_canonical_json
from wallet_twin_v31.repository import repository
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard" / "app" / "data" / "wallet-v311-fixture.json"


def main() -> None:
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
    write_canonical_json(OUT, payload)
    stamped = payload["projection"]["release"]["hackathon_status"]
    print(
        f"wrote {OUT.relative_to(ROOT)} ({len(projection.cells)} cells, "
        f"hackathon_status={stamped})"
    )


if __name__ == "__main__":
    main()
