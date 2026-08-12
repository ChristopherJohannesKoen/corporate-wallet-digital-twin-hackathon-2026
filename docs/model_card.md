# Corporate Wallet Digital Twin V3.1 — composed model card

> **V3.1 authoritative delta.** The final decision object is now
> `(client, stakeholder role, business problem, solution bundle, engagement window)`.
> V3.1 adds 20 twelve-domain Business Model Twins, 905 typed claims, temporal
> business graphs, 18 problem detectors, 16 solution estimators, separated
> client/bank value, six feasibility gates, funding routes, robust Pareto
> filtering, an eight-conversation CVaR plan and decision-directed questions.
> The current demonstration remains `NOT_PROMOTABLE`: every conversation is
> discovery-only, all clients fall short of 15 reviewed E1 claims, and E3,
> approved bank economics, bank infrastructure and real RM outcomes are absent.

**Model family:** latent-wallet reconstruction and decision support

**Release:** 3.1.0

**Point-in-time demonstration snapshot:** 30 June 2026

**Current release decision:** client demonstration ready; bank production `NOT_PROMOTABLE`

**Substrate:** governed V2 evidence, economics, timing, entitlement and GenAI controls
**Decision layer:** V3 Shadow Wallet, positive-unlabelled need, Bayesian change-point signals, constrained portfolio selection and decision-directed evidence acquisition

## Intended use

V3 helps trained corporate-banking relationship and product teams decide which client-product hypotheses deserve investigation, which evidence should be acquired next and how scarce RM capacity could be allocated under uncertainty. It is a decision-support system. It does not discover measured competitor transactions from public data and does not replace banker, finance, risk, legal, data-owner or client-consent decisions.

The checked-in snapshot is suitable for reproducible judging and controlled client demonstration. It combines the supplied Syn Bank simulation, 82 point-in-time E1 public facts and pinned representative priors. It is not bank-production data.

## Prohibited use

V3 must not be used for automated customer contact, credit approval, eligibility, pricing, market-conduct decisions, revenue recognition, booking, pipeline-stage changes, employee performance management or attribution of activity to a named competitor. Evidence acquisition, portfolio selection and brief generation require human approval. No output may be described as causal incremental value before a valid trial passes the documented gates.

## Composed analytical system

| Component | Method | Output class | Current calibration status |
|---|---|---|---|
| Observed bank activity | Point-in-time activity and balance contracts | `OBSERVED` | Syn Bank simulation in the demo |
| Identification bounds | Deterministic share/wallet envelopes | `IDENTIFIED_BOUND` | Mechanically validated |
| V2 wallet posterior | Five product-specific hierarchical posterior models | `POSTERIOR` | Representative/offline; no E3 panel |
| Shadow Wallet | 256-draw posterior-constrained ensemble with entropy-regularised Sinkhorn transport | `SCENARIO`, `RECONSTRUCTED_NOT_MEASURED` | Exact mass balance on 100 client-product networks; not competitor calibrated |
| Product need | Transparent logistic base learner with Elkan–Noto SCAR correction | `POSTERIOR` | Selection mechanism explicit; no bank-population validation |
| Change point | Bayesian online run-length filtering with Gaussian predictive densities | `POSTERIOR` | Deterministic temporal replay; not RM-outcome calibrated |
| Leakage alarm | Change probability, observed decline and reconstructed external-wallet exposure | `POSTERIOR`, `MODELLED_SIGNAL_NOT_CONFIRMED_LEAKAGE` | Mechanical signal validation only |
| Timing | Seasonal baseline with explicit 30/60/90-day probabilities | `POSTERIOR`/baseline | Surrogate intervals only; Cox promotion gate remains closed |
| Action portfolio | Seeded scenarios with CVaR-aware constrained selection | `SCENARIO` | Constraints and deterministic replay validated; economics simulated |
| Evidence acquisition | Expected decision value minus acquisition and latency cost | `SCENARIO` | Eight positive-net-VOI requests; approval required |
| Decision brief | Closed claim-pack compiler plus governed LLM gateway or deterministic fallback | Approved claim classes only | Fixture/golden-set controls; no bank-approved live-provider evaluation |

## Evidence and label semantics

Evidence tiers are immutable semantics, not confidence decorations:

- `E0`: governed prior or representative reference.
- `E1`: point-in-time public evidence with source title, URL, page, document hash, period and `available_date`.
- `E2`: client or RM attestation.
- `E3`: consented multibank observation capable of supporting measured share.
- `E4`: reconciled economics or outcomes.

Claim classes remain separate: `OBSERVED`, `IDENTIFIED_BOUND`, `POSTERIOR`, `SCENARIO` and `CAUSAL`. The V3 fixture contains zero measured competitor-share claims and zero causal-value claims. Anonymous provider nodes are mathematical allocation nodes, not inferred competitor identities.

The public register contains 82 E1 facts across all 20 clients. Thirty-one facts for BHP, Glencore and Shoprite are `APPROVED`; 51 facts are `PENDING_REVIEW` and cannot support approved-anchor claims. Fifteen approved accounting, FX, liquidity and trade proxies remain active for the three showcase clients.

## Data and point-in-time controls

Every curated record carries business/source keys, event time, valid time, ingestion time, source hash, transformation version, quality status, owner, entitlement domain and `available_date`. Reads require an explicit `as_of`. Future-dated facts are excluded. Restatements append a new version and never overwrite historical state.

The active V3 demonstration products are `dashboard/app/data/shadow-fixture.json`, `dashboard/app/data/v3-fixture.json` and canonical exports under `outputs/v3/`. Frozen V1 calculations live under `legacy/v1/` and are regression inputs only.

## Validation evidence

The checked-in V3 mechanical validation proves:

- 100 client-product reconstructions and 1,500 anonymous external edges reconcile to their declared transport marginals;
- 256 ensemble draws are used per reconstruction;
- PU probabilities retain the SCAR assumption and selection constant;
- 100 point-in-time change series replay deterministically;
- action selection respects capacity, product, sector and client constraints;
- eight selected evidence requests have positive net value of information;
- provider identities remain anonymous and no reconstructed flow becomes measured;
- route-level `as_of` and deny-by-default entitlement checks remain active;
- deterministic brief compilation preserves approved numbers and citations.

The evidence is mechanical, not a claim of representative-bank calibration. V2 interval coverage and CRPS promotion gates remain blocked until a representative E3 multibank panel exists. Timing promotion requires at least 200 eligible events and 10 outcome events per effective model degree of freedom.

## Sensitivity and robustness

The V2 continuity benchmark retains the nine low/base/high rate-by-prior cases. The global lab uses 10,000 reproducible Latin-hypercube draws across share prior, wallet, target share, anchor error, competitor-data error, FX policy, price, FTP and capital. The governed correlation matrix and seed are part of the artifact.

In the current representative fixture, Trade Finance is first-ranked in 100% of draws and has a mean 25.2% share of the top 10, but its majority-dominance frequency is 0%. Cross-border FX has a 79.7% majority-dominance frequency. V3 therefore reports Trade Finance as a robust leading product without hard-coding it as the portfolio strategy.

## Principal risks and mitigations

| Risk | Consequence | Control |
|---|---|---|
| Joint wallet/share non-identification | False precision | Independent bounds, posterior intervals, Shadow Wallet `SCENARIO` label |
| Missing E3 competitor observations | Inferred share mistaken for measured | Measured-share gate fails closed |
| PU selection misspecification | Need probabilities biased | SCAR mechanism, class prior and validation report registered |
| Change-point false alarms | Normal volatility called leakage | Explicit baseline/hazard, alarm calibration and `NOT_CONFIRMED` label |
| Public-fact extraction or restatement error | Incorrect anchors | Hash/page/date lineage, deterministic validation, four-eyes approval |
| Simulated rates and margins | Misleading economics | `SIMULATED` watermark; production economics blocked until approved/reconciled |
| Scenario optimization overfit | Brittle action selection | Seeded stress scenarios, CVaR, caps, rollback and sensitivity |
| VOI model error | Wasteful evidence work | Positive-net-VOI threshold, budget, human approval, no autonomous retrieval |
| LLM unsupported claim | Hallucinated brief | Closed claim pack, schema constraints, numeric/citation validation and fallback |
| Entitlement failure | Cross-client disclosure | Gateway/service/query/UI enforcement and immutable access decisions |
| Selection and outcome bias | Invalid uplift claim | Log all eligibility, randomized encouragement and ITT-first analysis |

## Monitoring

Monitor source reconciliation, future-data leakage, missingness, staleness, restatements, transport residuals, normalized entropy, PU selection drift, class-prior drift, change-point false alarms, signal rates, scenario concentration, CVaR breach, portfolio churn, VOI realization, interval coverage, CRPS, rank stability, GenAI schema/abstention/citation metrics, authorization denials, cross-client negative tests, event completeness, latency, availability, cost and rollback readiness.

## Promotion gates

Candidate-to-shadow requires point-in-time integrity, independent reproduction, registered transport/PU/hazard/public-sensor/CVaR/VOI artifacts, exact mass balance, anonymous providers, constraint satisfaction and zero measured/causal mislabelling. Shadow-to-champion additionally requires an approved E3 panel, approved/reconciled economics, bank AWS/Databricks/SSO/Unity Catalog/SIEM deployment, security and model-risk approval, live-provider adjudication and 30 clean shadow days. RM exposure and causal labels require the supervised pilot and randomized trial.

## Reproducibility and ownership

Schemas and OpenAPI are generated by `scripts/export_v3_contracts.py`; V3 mechanical validation by `scripts/run_v3_validation.py`; the judging manifest by `scripts/run_judging_validation.py`. Artifact versions, seeds and snapshots are checked into safe fixtures. Production owners remain evidence/finance, model risk, product finance/Treasury, data owner, security, platform and the RM pilot sponsor.
