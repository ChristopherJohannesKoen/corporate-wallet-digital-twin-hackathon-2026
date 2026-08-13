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
    print(f"wrote {OUT} ({len(projection.cells)} cells)")


if __name__ == "__main__":
    main()
