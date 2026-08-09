# Validation report

The generated, machine-readable results are in `outputs/validation.json`.

## Current validation stack

1. **Structural:** all 20 entities and 5 products are present; all quantiles are monotone.
2. **Accounting:** modelled total wallet never falls below observed activity; current share is in `[0,1]`; revenue gaps are nonnegative.
3. **Temporal:** 12-month seasonal-naive backtests run on every client-product monthly series. WAPE is the primary scale-free error because values differ materially by product.
4. **Synthetic recovery:** a known `T` and `q` generate `A=qT`; the model checks P10–P90 coverage and rank correlation under its declared prior.
5. **Uncertainty:** Monte Carlo sampling propagates share, target-share and rate uncertainty. `P(top 10)` quantifies rank stability.
6. **Public evidence:** 31/31 facts are audited, page-cited and point-in-time dated; 15/15 derived product anchors tie to the pipeline.
7. **Evidence impact:** median relative interval width falls 72.8% and median confidence rises 26 percentage points across anchored opportunities.
8. **Sensitivity:** all nine rate/prior cases are materialised. Trade Finance is #1 in 9/9, but majority-dominant in 0/9 and occupies 2/10 top slots in every case.
9. **Narrative:** deterministic briefs require standard sections and page-linked public-anchor citations when evidence is available.

## Production validation additions

- rolling-origin comparisons against ETS, SARIMA and gradient boosting;
- leave-one-client-out validation for any learned peer model;
- interval coverage against independently anchored wallet estimates;
- rank stability across share-prior, price and target-share grids;
- calibration of event hazards using realised events;
- causal uplift validation only after recommendation/action/outcome capture;
- red-team and golden-set evaluation of generated briefs.

## Acceptance gates

The solution must fail closed when the portfolio JSON is missing, reject incoherent quantiles, surface missing evidence, preserve the as-of date and pass Python tests, workbook checks, spreadsheet error scans, PDF visual QA, and the dashboard build/test before release.
