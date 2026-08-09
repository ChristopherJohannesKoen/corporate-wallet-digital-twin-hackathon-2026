# Data dictionary

## Supplied sources

### Transactional banking

Primary key: `transaction_id` after first-occurrence ID deduplication. Core fields: client, date, leg type, direction, ZAR amount, currency, channel, beneficiary and reference.

### Cross-border payments

Primary key: `transaction_id` after first-occurrence ID deduplication. Core fields: client, date, direction, currency pair, ZAR value, counterparty country and corridor type.

### Trade finance

Primary key: `instrument_id` after first-occurrence ID deduplication. Core fields: client, date, instrument type, direction, tenor, ZAR value, counterparty country, contract type and status.

## Generated portfolio fields

| Field | Meaning | Provenance |
|---|---|---|
| `observed_activity_zar` | LTM source activity, or the documented liquidity flow proxy | observed / accounting-derived |
| `current_share.p10/p50/p90` | prior-conditioned bank-share distribution | model-estimated |
| `total_wallet_zar.p10/p50/p90` | `observed/share` distribution | model-estimated |
| `partial_identification_zar` | explicit envelope under share prior quantiles | assumption-bounded |
| `revenue_gap_zar.p10/p50/p90` | contestable annualised scenario economics | model-estimated |
| `confidence` | evidence, quality, recurrence and stability score | model-estimated |
| `fit_score` | declared sector-product fit | assumption |
| `timing_score` | seasonality and event-window score | derived |
| `top10_probability` | Monte Carlo frequency of remaining top ten | model-estimated |
| `priority_score` | gap median × confidence × fit × timing | model-estimated |
| `public_anchor` | low/base/high product activity anchor, formula, assumptions and fact IDs | audited facts + declared transformation |
| `anchor_impact` | prior-only vs anchored intervals, width reduction and confidence lift | model-evaluated |
| `debt_maturity_anchor` | current borrowings and disclosed short-term facilities | audited public facts |
| `sensitivity.scenarios` | nine rate/prior reruns with top-10 composition | model-evaluated |

## Public fact schema

`data/public_facts.csv` contains 31 audited facts for BHP (`E01`), Glencore (`E02`) and Shoprite (`E09`). Required fields include source value, unit, currency, reporting period, entity, normalized concept, source title/URL/page, audit status, method, confidence, source date and `available_date`. Facts are eligible only if `available_date <= as_of`. `value_zar` is generated separately using the declared currency-conversion assumption and never overwrites the audited source value.

Normalized concepts are `revenue`, `operating_cost_base`, opening/closing trade receivables, inventories and trade payables, `fx_exposure`, `current_debt`, and `short_term_facilities`.

## Intervention schema

`data/interventions.csv` reserves client, product, recommendation, action, outcome date/value and notes. This is the minimum future dataset for separating propensity from uplift.
