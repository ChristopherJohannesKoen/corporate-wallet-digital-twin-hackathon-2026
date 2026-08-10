# Validation report

The generated machine-readable results are written to `outputs/validation.json`, `outputs/v2_validation/`, `outputs/v3_validation/v3_validation_report.json` and `outputs/judging_validation_manifest.json`.

## Current validation stack

1. **Point-in-time evidence:** 82 E1 facts cover all 20 relationships. Page, period, source date, available date, currency, unit, source hash and approval status remain explicit; 51 expanded facts remain pending finance-SME approval.
2. **Identification:** the deterministic bounds engine is separate from posterior and scenario estimates. No reconstructed edge is labelled as a measured competitor transaction.
3. **Wallet calibration lab:** entity-disjoint calibration and evaluation, selection weighting, posterior-predictive draws, conformal coverage, CRPS and interval-width diagnostics remain reproducible on known representative truth.
4. **Shadow Wallet:** 100 client-product reconstructions produce 1,500 anonymous external edges. Observed bank flow plus latent external mass equals the total-wallet median exactly; the current maximum reconciliation error is R0.
5. **Positive–Unlabelled need:** the Elkan–Noto correction retains the SCAR assumption, selection constant and observed-positive indicator on every result.
6. **Temporal signals:** 100 Bayesian run-length series produce explicit 30-, 60- and 90-day event probabilities. Every leakage output is labelled `MODELLED_SIGNAL_NOT_CONFIRMED_LEAKAGE`.
7. **Robust decision portfolio:** 512 scenario draws and lower-tail CVaR select 12 actions subject to one-per-client, four-per-product and four-per-sector caps. Causal incremental value is withheld.
8. **Value of information:** eight evidence requests have positive net decision value after cost and latency. Autonomous external retrieval is disabled.
9. **Sensitivity:** the frozen 3×3 rate/prior benchmark and 10,000-draw Latin-hypercube experiment report rank and composition separately. Trade Finance remains first-ranked but is not majority-dominant.
10. **GenAI:** structured extraction, deterministic currency/period/arithmetic/citation checks, prompt-injection tests, closed claim packs, prohibited phrases and deterministic fallback remain release gates. The LLM cannot publish facts or take customer, pricing or CRM actions.
11. **Contracts and access:** 22 exported JSON Schemas, OpenAPI, required `as_of`, deny-by-default ABAC and immutable access-decision events make every displayed layer traceable and entitled.

## Claim audit

- Measured competitor-share claims: **0**.
- Confirmed leakage events: **0**.
- Causal-value claims: **0**.
- Autonomous evidence retrievals or customer actions: **0**.

These zeros are intentional controls, not missing labels. E3 observations, bank-approved economics and qualified RM outcomes are external production gates.

## Acceptance gates

The release must fail closed on missing or stale critical inputs, incoherent intervals, mass-balance failure, unauthorized access, unsupported narrative claims, non-positive selected VOI or broken portfolio capacity constraints. It must also pass Python tests, API replay, contract export, dashboard tests/build/lint, production dependency audit, PDF visual QA, PowerPoint overflow/fidelity checks and the executed notebook assertions.
