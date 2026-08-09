# Methodology

> **Archived V1 methodology.** Its three-client evidence counts, browser/runtime architecture, confidence score and prototype calculations are frozen regression benchmarks. The implemented V2 method and current 20-client/82-fact state are documented in [`v2_model_validation.md`](v2_model_validation.md) and [`v2_implementation_status.md`](v2_implementation_status.md).

## 1. Decision objective

The Corporate Wallet Digital Twin is a relationship-banker decision system, not a single prediction. It ranks client-product conversations by answering:

- **Who:** which client has the largest uncertainty-adjusted economic gap?
- **What:** which product need is plausible and underpenetrated?
- **When:** when do seasonality or scheduled events create a practical window?
- **Why:** which observations, derivations and assumptions support the call?

The modelling chain is:

`bank data x -> latent state z_t -> need N -> economic exposure E -> utilisation u -> total wallet T -> bank share q -> observed A -> economics W -> contestable gap G -> timing h -> priority`

## 2. Unit of analysis and point-in-time contract

The analytical unit is `client × product × as_of_date`. The supplied data ends on 30 June 2026, which becomes the model's point-in-time date. Features use only rows dated on or before that date. Future public enrichment must use `available_date`, not report period alone, to prevent look-ahead.

Products are Collections, Payments, Liquidity, Cross-border FX, and Trade finance. Thirty-one audited public facts for BHP, Glencore and Shoprite are eligible because their `available_date` is on or before 30 June 2026. Current borrowings and short-term facilities activate dated debt-maturity/refinancing anchors for those showcases; the remaining 17 relationships remain prior-led.

## 3. Ingestion and data quality

All three CSVs are streamed directly from `Data.zip` using CP1252 decoding. The pipeline:

1. normalises categorical text and currency case;
2. excludes repeated business IDs within each source;
3. flags missing countries and noncanonical currency values;
4. flags the semantic inconsistency `export_collections + import direction` rather than silently rewriting it;
5. preserves source-specific observations—cross-border and transactional SWIFT rows are not forced into a synthetic match.

The model-quality score is `1 − duplicate_ID_rate − 0.30 × missing_country_rate`. It measures processing fitness, not truth of wallet assumptions.

## 4. Interpretable dynamic state

Each client is represented by seven 0–100 features:

| State | Operational definition | Provenance |
|---|---|---|
| Operating scale | percentile of LTM supplied activity | derived |
| Working-capital intensity | collections + payments as share of supplied activity | derived |
| Liquidity volatility | standard deviation of monthly net flow / mean monthly gross flow | derived |
| International exposure | cross-border + trade activity / supplied activity | derived |
| Financing need | weighted trade intensity and liquidity volatility proxy | model-estimated |
| Event intensity | near-term trade maturity count and value | derived |
| Relationship complexity | product breadth and country breadth | derived |

These are refreshed whenever the pipeline advances its as-of date. They are intentionally explainable; no deep architecture is necessary for twenty relationships and 36 monthly observations.

## 5. Product exposure and utilisation

- Collections: observed inbound collection legs.
- Payments: supplier, payroll and tax-related transactional legs not classified as collections.
- Cross-border FX: observed cross-border payment value. This is exposure, not proven executed FX revenue.
- Trade finance: observed instrument value across supplied trade-finance types.
- Liquidity: `min(inbound, outbound) + 0.5 × |inbound − outbound|` per month. This is a **flow opportunity proxy**, not a deposit balance or liquidity wallet.

The public-fact table actively applies accounting triangulation for the three showcase clients:

`collections exposure ≈ revenue + opening receivables − closing receivables`

`supplier payments ≈ cost base + closing inventory − opening inventory + opening payables − closing payables`

FX uses the audited point exposure or hedge notional with an explicit 1× / 2× / 4× annual-turnover range. Liquidity uses 0.75× / 1.0× / 1.5× current debt and facilities. Trade finance uses the audited payments base with a declared sector-utilisation range. If all required audited facts are not present and point-in-time valid, the pipeline does not activate that anchor.

## 6. Partial identification

The key identity is:

`A = qT`

where `A` is observed Standard Bank activity, `q` is the bank share, and `T` is the total addressable wallet. One equation cannot identify two unknowns. The workbench therefore reports three different objects where audited anchors are available:

1. **Prior-only envelope:** `A / q95` to `A / q05`, using the declared product share prior.
2. **Audited-anchor envelope where available:** low/high bounds derived from the relevant accounting, FX, debt or trade-utilisation transformation.
3. **Model-based posterior:** Monte Carlo P10, median and P90. For anchored opportunities, the share-prior wallet and audited-anchor distribution are precision-pooled geometrically at the declared 0.84 anchor weight.

The posterior is not relabelled as observed truth. Product priors live in `config/assumptions.json`; no prior is hidden in code.

Share is sampled as:

`q ~ Beta(μκ, (1−μ)κ)`

where the mean `μ` begins with the declared product prior and is bounded after transparent relationship adjustments. `κ` increases with recurrence and data quality. Total wallet follows by `T = A/q`.

## 7. Contestable economics

The solution never targets 100% share. A target share is sampled from a triangular 30% / 40% / 50% scenario. Product economic rates are also triangular assumptions in basis points.

`G = T × rate × max(q* − q, 0)`

This gives an annualised **scenario revenue gap**, not booked revenue. P10 may be zero because in some draws current share already exceeds target share. Rates are placeholders until treasury, product and finance teams supply approved pricing and margin economics.

## 8. Confidence and evidence coverage

Evidence provenance follows the plan:

| Evidence | Weight |
|---|---:|
| Synthetic bank observation | 1.00 |
| Audited public statement | 0.95 |
| Direct public note | 0.90 |
| Accounting identity | 0.80 |
| Sector benchmark | 0.60 |
| Model extrapolation | 0.50 |
| Generic prior | 0.30 |

Opportunity confidence combines evidence coverage, source-data quality, recurrence and trend stability. An active audited anchor adds product-specific public coverage and an explicit evidence lift. Across the 15 anchored opportunities, median confidence increases by 26 percentage points and high-confidence opportunities increase from 0 before the public evidence to 15 after it. This is an evidence-strength score, not a win probability.

## 9. Timing

For each client-product series the baseline forecast is the same month one year earlier, multiplied by a capped six-month trend factor (0.75–1.25). This honours the strong November–December and January–February seasonality visible in the portfolio while remaining auditable.

Trade instruments create scheduled events using `date + tenor_days`. Events ending within 90 days of the as-of date lift the trade-finance timing score. Timing is kept separate from economic gap so a large wallet does not masquerade as urgency.

## 10. Ranking and uncertainty

`priority = median(G) × confidence × sector_fit × timing`

This is an economic prioritisation score, not a propensity or causal conversion probability. Monte Carlo draws are ranked repeatedly to calculate `P(top 10)`, showing whether a recommendation remains stable under uncertainty.

When action/outcome history becomes available in `data/interventions.csv`, uplift can be estimated separately using treatment-aware methods. Until then the system does not claim incremental causal effect.

## 11. Validation

- Accounting invariants: observed activity ≤ modelled wallet, share ∈ [0,1], nonnegative gaps.
- Temporal backtest: seasonal-naive WAPE, MAE and RMSE across all 100 client-product series.
- Synthetic latent recovery: simulate `T`, `q`, and `A=qT`; test P10–P90 coverage and rank recovery under the declared data-generating prior.
- Public-anchor impact: relative P10–P90 interval width is compared before and after anchoring. The median reduction is 72.8%; BHP 70.1%, Glencore 72.8%, and Shoprite 80.5%.
- Sensitivity: nine explicit low/base/high economic-rate × low/base/high share-prior cases are rerun. Trade Finance remains the single #1 opportunity in 9/9 cases, but occupies only 2/10 top slots in every case and is majority-dominant in 0/9 under the declared definition.
- GenAI: prompts forbid new calculations and unsupported facts; briefs retain citations and abstention language.

## 12. Scope limits

No competitor flows, real pricing, fees, margins, Global Markets trades, investment-banking pipeline, or labelled recommendation outcomes are present. Audited public evidence covers only three showcases. USD facts for BHP and Glencore are translated at the declared ZAR17.86/USD point rate for comparability; this is not an audited ZAR restatement. The prototype is decision-ready as a transparent scenario system; production calibration requires broader feeds, an approved FX translation policy, entitlements, model-risk review and outcome capture.
