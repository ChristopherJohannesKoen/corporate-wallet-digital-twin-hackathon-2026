# Governed V2 data registers

- `public_sources.json` records the official point-in-time audited source, URL, reporting date, availability date and locally verified SHA-256 for each of the 17 newly curated relationships.
- `public_facts_expanded.csv` contains 51 page-cited E1 facts—three per relationship—held as `PENDING_REVIEW` until four-eyes finance-SME approval.
- `public_evidence_coverage.csv` is the control register. All 20 relationships now have E1 coverage; it does not imply E2/E3 wallet measurement.
- `benchmark_rate_cards.json` contains explicit conservative/reference/upside E0 scenarios. It is non-production and never represents Standard Bank pricing.
- `golden_set/cases.jsonl` is the 36-case synthetic extraction/evaluation dataset. Its sealed split is a release benchmark, not a replacement for real scanned documents.
- `representative_trade_finance_summary.json` is a pinned aggregate of the 10,000-row public synthetic trade-finance reference. It keeps the demonstration reproducible without redistributing the downloaded dataset and remains ineligible for E3 or measured-share claims.

Every new public fact retains source hash, page, period, source/availability dates, unit, currency and review state. Accounting facts become noisy anchors through transparent rules; they are never exact wallet labels. Sector FX and trade ratios remain E0 governed assumptions even when combined with an E1 audited fact.
