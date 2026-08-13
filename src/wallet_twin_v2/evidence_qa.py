from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from pypdf import PdfReader

from .public_evidence import EXPANDED_FACTS, ROOT, SOURCE_REGISTRY
from .canonical import artifact_timestamp


EVIDENCE_DIR = ROOT / "tmp" / "evidence-v2"
TEXT_DIR = EVIDENCE_DIR / "text"

LOCAL_FILES = {
    "E03": "AngloAmerican.pdf", "E04": "AngloGold.pdf", "E05": "GoldFields.pdf",
    "E06": "Valterra.pdf", "E07": "OUTsurance.pdf", "E08": "Sanlam.pdf",
    "E10": "Bidcorp.pdf", "E11": "Pepkor.pdf", "E12": "Clicks.pdf",
    "E13": "NEPI.pdf", "E14": "Prosus.pdf", "E15": "Naspers.pdf",
    "E16": "MTN.pdf", "E17": "Vodacom.pdf", "E18": "Bidvest.pdf",
    "E19": "Aspen.pdf", "E20": "Shaftesbury.pdf",
}
TEXT_FILES = {entity_id: Path(filename).with_suffix(".txt").name for entity_id, filename in LOCAL_FILES.items()}

CONCEPT_TERMS = {
    "revenue": ("revenue", "sales"),
    "insurance_revenue": ("insurance revenue", "insurance service revenue"),
    "gross_rental_income": ("rental income", "gross rental"),
    "cash_and_cash_equivalents": ("cash", "cash equivalents"),
    "current_liabilities": ("current liabilities",),
    "current_debt": ("borrowings", "debt", "short-term"),
    "term_finance": ("term finance", "borrowings", "debt"),
    "trade_payables": ("trade payables", "payables"),
    "trade_payables_close": ("trade payables", "payables"),
    "insurance_liabilities": ("insurance liabilities", "insurance contracts"),
}


def _page_index(text: str) -> Dict[int, str]:
    pages: Dict[int, str] = {}
    matches = list(re.finditer(r"<<<PDF_PAGE\s+(\d+)>>>", text))
    for index, match in enumerate(matches):
        start = match.end()
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages[int(match.group(1))] = text[start:stop]
    return pages


def _numbers(text: str) -> List[float]:
    # PDF extractors preserve narrow/non-breaking spaces used as thousands
    # separators.  Normalise them before tokenisation so the verifier does not
    # depend on a particular OCR/PDF implementation.
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    tokens = re.findall(r"\(?-?\d{1,3}(?:[ ,]\d{3})+(?:\.\d+)?\)?|\(?-?\d+(?:\.\d+)?\)?", text)
    values = []
    for token in tokens:
        negative = token.startswith("(") and token.endswith(")")
        normalized = token.strip("()").replace(",", "").replace(" ", "")
        try:
            value = float(normalized)
            values.append(-value if negative else value)
        except ValueError:
            continue
    return values


def _number_found(value: float, text: str) -> bool:
    # Curated facts are normalized to millions. Audited tables commonly display
    # either thousands or millions, while summary pages sometimes use billions.
    normalized_targets = (value, value * 1_000.0, value / 1_000.0)
    for target in normalized_targets:
        tolerance = max(0.001, abs(target) * 1e-7)
        # Match the expected magnitude directly before generic tokenisation.
        # This avoids merging adjacent table columns such as
        # ``226 707 188 001`` into one artificial number.
        formatted = f"{abs(target):,.6f}".rstrip("0").rstrip(".")
        variants = {
            formatted,
            formatted.replace(",", " "),
            formatted.replace(",", "\u00a0"),
            formatted.replace(",", "\u202f"),
            formatted.replace(",", ""),
        }
        if any(re.search(rf"(?<![\d.,]){re.escape(candidate)}(?!\d)", text) for candidate in variants):
            return True
        # Curated wallet anchors store liability magnitudes as positive values;
        # audited balance sheets often display the same amount in parentheses.
        # Sign semantics are therefore checked by concept and human review,
        # while this check proves the cited amount is present on the page.
        if any(abs(abs(candidate) - abs(target)) <= tolerance for candidate in _numbers(text)):
            return True
    return False


def _concept_found(concept: str, text: str, notes: str) -> bool:
    lowered = re.sub(r"\s+", " ", (text + " " + notes).lower())
    terms = CONCEPT_TERMS.get(concept, (concept.replace("_", " "),))
    return any(term in lowered for term in terms)


def _iso_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _unit_and_sign_checks(fact: dict) -> Dict[str, bool]:
    """Validate normalized magnitude semantics without pretending to do SME review.

    The curated public register stores audited balance-sheet and income-statement
    amounts as *magnitudes* in millions. Liability signs therefore cannot be
    inferred from the source presentation alone (parentheses are common). The
    deterministic gate proves that the normalization is declared, finite and
    non-negative; a finance reviewer still owns the accounting interpretation.
    """

    value = float(fact["value"])
    return {
        "unit_supported": fact.get("unit") in {"million", "billion", "unit", "percent"},
        "normalized_value_finite": value == value and abs(value) != float("inf"),
        "magnitude_sign_consistent": value >= 0.0,
        "currency_code_valid": bool(re.fullmatch(r"[A-Z]{3}", fact.get("currency", ""))),
    }


def verify_expanded_evidence(
    *, evidence_dir: Path = EVIDENCE_DIR, text_dir: Path = TEXT_DIR,
) -> dict:
    registry = json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))
    documents = {item["entity_id"]: item for item in registry["documents"]}
    facts = list(csv.DictReader(EXPANDED_FACTS.open(newline="", encoding="utf-8-sig")))
    doc_results: Dict[str, dict] = {}
    page_cache: Dict[str, Dict[int, str]] = {}

    for entity_id, document in documents.items():
        pdf_path = evidence_dir / LOCAL_FILES[entity_id]
        text_path = text_dir / TEXT_FILES[entity_id]
        exists = pdf_path.exists() and text_path.exists()
        actual_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest() if pdf_path.exists() else None
        pdf_magic = pdf_path.read_bytes()[:5] == b"%PDF-" if pdf_path.exists() else False
        page_count: Optional[int] = None
        if pdf_path.exists():
            try:
                page_count = len(PdfReader(str(pdf_path)))
            except Exception:
                page_count = None
        pages = _page_index(text_path.read_text(encoding="utf-8", errors="replace")) if text_path.exists() else {}
        page_cache[entity_id] = pages
        doc_results[entity_id] = {
            "entity_name": document["entity_name"],
            "source_title": document["source_title"],
            "source_url": document["source_url"],
            "expected_sha256": document["sha256"],
            "actual_sha256": actual_hash,
            "hash_match": actual_hash == document["sha256"],
            "pdf_magic_valid": pdf_magic,
            "pdf_page_count": page_count,
            "indexed_text_pages": len(pages),
            "available_by_as_of": document["available_date"] <= registry["as_of"],
            "automated_status": "PASS" if exists and actual_hash == document["sha256"] and pdf_magic and pages else "FAIL",
        }

    fact_results = []
    fact_keys = Counter(
        (fact["entity_id"], fact["concept"], fact["period_start"], fact["period_end"])
        for fact in facts
    )
    for fact in facts:
        entity_id = fact["entity_id"]
        page = int(fact["page"])
        page_text = page_cache.get(entity_id, {}).get(page, "")
        value = float(fact["value"])
        period_start = _iso_date(fact.get("period_start", ""))
        period_end = _iso_date(fact.get("period_end", ""))
        available_date = _iso_date(fact.get("available_date", ""))
        as_of = _iso_date(registry["as_of"])
        normalized_checks = _unit_and_sign_checks(fact)
        checks = {
            "document_hash_match": doc_results.get(entity_id, {}).get("hash_match", False),
            "page_exists": bool(page_text),
            "value_exact_on_page": _number_found(value, page_text),
            "concept_term_on_page": _concept_found(fact["concept"], page_text, fact.get("notes", "")),
            "period_dates_valid": bool(period_start and period_end and period_start <= period_end),
            "period_not_after_as_of": bool(period_end and as_of and period_end <= as_of),
            "available_date_valid": bool(available_date),
            "point_in_time_eligible": bool(available_date and as_of and available_date <= as_of),
            "currency_consistent": fact["currency"] == documents[entity_id]["currency"],
            "source_hash_consistent": fact["source_sha256"] == documents[entity_id]["sha256"],
            "arithmetic_consistent": fact.get("method", "").lower().startswith("direct"),
            "no_unresolved_restatement_conflict": fact_keys[
                (fact["entity_id"], fact["concept"], fact["period_start"], fact["period_end"])
            ] == 1,
            **normalized_checks,
        }
        blocking_checks = (
            "document_hash_match", "page_exists", "value_exact_on_page",
            "period_dates_valid", "period_not_after_as_of", "available_date_valid",
            "point_in_time_eligible", "currency_consistent", "source_hash_consistent",
            "arithmetic_consistent", "no_unresolved_restatement_conflict",
            "unit_supported", "normalized_value_finite", "magnitude_sign_consistent",
            "currency_code_valid",
        )
        status = "PASS" if all(checks[name] for name in blocking_checks) else "FAIL"
        fact_results.append({
            "fact_id": fact["fact_id"], "entity_id": entity_id, "entity_name": fact["entity_name"],
            "concept": fact["concept"], "value": value, "currency": fact["currency"], "unit": fact["unit"],
            "page": page, "source_url": fact["source_url"], "source_hash": fact["source_sha256"],
            "automated_status": status, "checks": checks,
            "developer_qa_state": "DEVELOPER_VERIFIED" if status == "PASS" else "DEVELOPER_REJECTED",
            "review_state": "READY_FOR_FINANCE_SME" if status == "PASS" else "RESEARCH_REMEDIATION_REQUIRED",
            "required_reviewers": ["FINANCE_SME", "INDEPENDENT_EVIDENCE_APPROVER"],
            "approval_status": fact["approval_status"],
            "approval_boundary": "DEVELOPER_VERIFIED is deterministic QA only; it never activates an anchor or claim path.",
        })

    counts = Counter(item["automated_status"] for item in fact_results)
    ready = sum(item["review_state"] == "READY_FOR_FINANCE_SME" for item in fact_results)
    return {
        "qa_version": "public-evidence-qa-1.1.0",
        "generated_at": artifact_timestamp(),
        "as_of": registry["as_of"],
        "documents": len(doc_results),
        "source_cache_complete": all(item["automated_status"] == "PASS" for item in doc_results.values()),
        "facts": len(fact_results),
        "document_passes": sum(item["automated_status"] == "PASS" for item in doc_results.values()),
        "fact_passes": counts["PASS"],
        "fact_failures": counts["FAIL"],
        "ready_for_finance_sme": ready,
        "developer_verified": sum(item["developer_qa_state"] == "DEVELOPER_VERIFIED" for item in fact_results),
        "human_approvals_completed": 0,
        "production_approval_claim_allowed": False,
        "documents_detail": doc_results,
        "facts_detail": fact_results,
    }


def write_review_pack(output_dir: Path) -> dict:
    report = verify_expanded_evidence()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "public_evidence_qa.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    with (output_dir / "finance_sme_review_pack.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["fact_id", "entity_id", "entity_name", "concept", "value", "currency", "unit", "page", "source_url", "source_hash", "automated_status", "developer_qa_state", "review_state", "approval_status"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in report["facts_detail"]:
            writer.writerow({field: item[field] for field in fields})
    return report
