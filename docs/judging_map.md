# V3.2.0 judging map

| Criterion | What to show | Canonical evidence |
|---|---|---|
| Business insight — 40% | 20×5 wallet heatmap; BHP `A/T/q/q*/G`; eight discovery conversations | `dashboard/app/data/wallet-v311-fixture.json`, `outputs/v31/v31_coverage_plan.json` |
| Analytical rigour — 30% | `A=qT`; bounds independent of priors; approval-authoritative anchors; 0.20/0.35/0.50 E1 sensitivity; 10,000 global draws | `src/wallet_twin_v2/wallet_model.py`, `outputs/v2_validation/measurement_policy_sensitivity.json` |
| GenAI — 20% | closed evidence packs; deterministic validators/fallback; three-provider target report; no fabricated live success | `outputs/v2_validation/genai_golden_eval.json`, `outputs/v2_validation/live_provider_comparison.json` |
| Presentation — 10% | one-page commercial answer; exact ten-slide wallet-first deck; executed notebook | `output/pdf/`, `output/presentation/`, `notebooks/01_wallet_twin_demo.ipynb` |

## Live demonstration path

1. Open **Wallet Portfolio** and show all 100 cells.
2. Toggle contestable contribution, observed `A`, posterior `T`, estimated `q`,
   contestable `G` and evidence status.
3. Open BHP Trade Finance and explain `A → T → q → q* → G`.
4. Show that only BHP, Glencore and Shoprite cells are E1-approved; the remaining
   85 cells are E0 prior-led because the 51 pending facts are excluded.
5. Move to **Coverage Plan** and explain how the Decision Twin converts wallet
   evidence into stakeholder, problem, solution, timing and the next-best question.
6. Open the deterministic grounded brief and the provider evaluation metadata.
7. Close on the validation hierarchy and explicit `NOT_PROMOTABLE` bank boundary.

## Questions judges are likely to ask

| Question | Answer boundary |
|---|---|
| Is share measured? | No. It is posterior unless an E3 multibank observation exists. |
| Why 31 approved but 82 public facts? | 51 are developer-verified candidates pending accountable finance-SME review; they are excluded from active inference. |
| Is Trade Finance hard-coded to win? | No. The engine reports rank frequency, top-ten share, majority frequency and absolute economics. It loses majority dominance at E1 weight 0.50. |
| Is the GenAI result live? | For hackathon evaluation, yes: 8 of 9 genuine provider outputs were accepted across OpenAI, Anthropic and Google and all three showcase clients. One output was blocked by the claim compiler and fallback retained. This is not bank-authorized `LIVE_GENAI`. |
| Is this production-ready for a bank? | No. Hackathon submission status is separate; bank release remains `NOT_PROMOTABLE`. |
| What is confidential? | Supplied Syn Bank rows and challenge-derived row-level data remain private. The public mirror uses independently generated anonymized fixtures. |

## V3.2 — Promotion Readiness Twin

| Question | Answer |
|---|---|
| What does V3.2 add? | The question V3.1.1 could not express: *is this system allowed to be used, and for what?* Five ordered states, 30 gates, two evidence tracks and a capability register. |
| Is the system promoted? | No. Real state is `OFFLINE_CANDIDATE`. `BANK_SHADOW_AUTHORIZED = FALSE`. |
| Why does the rehearsal stop at SHADOW_READY while PMR is 100%? | Every gate evaluator has positive and negative machinery tests, but only the first transition received a four-eyes rehearsal approval. Passing metrics alone never advances state. |
| PMR is 100% — is that good? | It means the apparatus works. **BER is 0%**: the bank has no admissible evidence. The two disagreeing is the finding, which is why there is no combined score. |
| Why no single promotability percentage? | It would let a fully rehearsed system with no bank evidence read as nearly production-ready. `assert_no_composite_score` enforces the prohibition in four places. |
| You report 30 shadow days — is that a month of operation? | No. Those are *simulated* days on a virtual clock. `elapsed_bank_shadow_days = 0` is published beside them everywhere, and the clock has no field, method or parameter that could advance it. |
| Why does the rehearsal fail on day 17? | Deliberately. A run that counted straight to thirty would show the same number while proving far less; the reset shows the counter is a control, not a loop bound. |
| Is anything signed? | Rehearsal evidence, by a local ECDSA key that is cryptographically barred from signing `REAL_BANK` evidence. Sigstore and KMS ship as adapters and report `NOT_EXECUTED`; neither returns plausible bytes when unavailable. |
| How many E3 clients would you need? | `NOT_DETERMINED_UP_TO_150`. The sweep did not converge, and returning 150 would recommend a data contract the analysis says would not work. |
| Is the trial design sound? | Type I error is controlled; **power is 0.20**, so it is reported `UNDERPOWERED_AT_THIS_CLUSTER_COUNT`. A null result from it would be uninformative. |
| Do the 120 RM sessions show adoption? | No. Every one carries `real_participant=False` as a non-init field, so no simulated session can satisfy the supervised-pilot gate. |
| Did wiring OPA change anything? | It found three live entitlement gaps: the Rego ignored the `"*"` wildcard, the in-process policy never checked region, and evidence approval was not product- or region-scoped. All three are fixed and 4,860 principal/request combinations now agree. |
