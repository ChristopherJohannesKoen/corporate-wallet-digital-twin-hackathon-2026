from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_twin_v2.evidence_qa import write_review_pack


if __name__ == "__main__":
    result = write_review_pack(ROOT / "outputs" / "v2_validation")
    print(json.dumps({
        "documents": result["documents"], "document_passes": result["document_passes"],
        "facts": result["facts"], "fact_passes": result["fact_passes"],
        "ready_for_finance_sme": result["ready_for_finance_sme"],
        "production_approval_claim_allowed": result["production_approval_claim_allowed"],
    }, indent=2))
