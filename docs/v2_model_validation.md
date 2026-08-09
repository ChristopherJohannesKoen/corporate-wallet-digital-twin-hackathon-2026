# Analytical validation protocol and current offline evidence

The deterministic bounds engine remains independent of the statistical model. The share model now estimates a posterior-predictive beta distribution: calibration observations update the population mean and between-relationship dispersion instead of collapsing unseen-client intervals around a pooled mean. E1 anchors remain noisy wallet measurements; only E3/E4 evidence can support measured-share labels.

Run the reproducible lab with:

```powershell
python scripts/run_offline_validation.py --output outputs/v2_validation
```

The report covers:

- synthetic known-truth generation, selection-biased E3 panels, inverse-inclusion weights, disjoint client holdouts, interval coverage, bias, CRPS and within-client product-rank recovery;
- E1 anchor ablation to test whether interval narrowing preserves coverage;
- rolling-origin seasonal-naive evaluation over the 36-month supplied synthetic history;
- leave-one-client-out sector/product benchmarking and monthly top-10 stability;
- explicit transaction-derived activation, uplift and dormancy surrogate events;
- E0 economics packs and scenario frontiers; and
- cluster-trial power and non-compliance simulation.

Current known-truth results show 88.7% wallet coverage after anchors and 44.4% median interval narrowing. The selection-weighted panel improves share CRPS by 2.9% versus the frozen prior, below the 10% promotion target. These are synthetic mechanics results and cannot satisfy empirical calibration.

The transaction-derived seasonal interval covers 80.4% at a nominal 90%, which records a validation failure rather than hiding it. The 3,440 eligible surrogate intervals and 361 volume events would be numerically sufficient for an eight-degree-of-freedom Cox fit, but they are not qualified RM-action outcomes. The actual promotion gate therefore records zero valid outcomes and retains the seasonal baseline.

Global sensitivity uses 10,000 reproducible Latin-hypercube draws. Trade Finance is reported under three different definitions—first rank, top-10 share and majority dominance—and no test encodes a winner. Bank promotion still requires approved distributions, empirical E3 holdouts, 85–95% overall coverage, no material segment under-coverage, at least 10% CRPS improvement and independent reproduction.
