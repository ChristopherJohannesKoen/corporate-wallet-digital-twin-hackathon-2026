# V3.1.1 judging map

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
| Is the GenAI result live? | The deterministic brief is accepted. Live provider runs remain `NOT_EXECUTED` unless fresh rotated credentials and explicit acknowledgement are present. |
| Is this production-ready for a bank? | No. Hackathon submission status is separate; bank release remains `NOT_PROMOTABLE`. |
| What is confidential? | Supplied Syn Bank rows and challenge-derived row-level data remain private. The public mirror uses independently generated anonymized fixtures. |
