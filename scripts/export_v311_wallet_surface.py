from __future__ import annotations

import json
from pathlib import Path

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
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(projection.cells)} cells)")


if __name__ == "__main__":
    main()
