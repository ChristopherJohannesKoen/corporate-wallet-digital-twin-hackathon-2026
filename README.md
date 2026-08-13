# Corporate Wallet Digital Twin V3.1.1

**Team:** Corporate Wallet Digital Twin

**Member:** Christopher Koen

**Event:** Standard Bank Hackathon 2026

**As of:** 30 June 2026
**Public code:** <https://github.com/ChristopherJohannesKoen/corporate-wallet-digital-twin-hackathon-2026-public>

Corporate Wallet Digital Twin estimates the corporate wallet that one bank
cannot directly observe, sizes the contestable share gap, and turns that gap into
an evidence-backed relationship-manager conversation.

```text
Syn Bank activity + approved public evidence
→ total-wallet and share intervals
→ contestable gap
→ 20 × 5 opportunity heatmap
→ stakeholder/problem/solution/timing
→ grounded GenAI briefing
```

The core identification equation is `A=qT`: Syn Bank observes its activity `A`,
while total wallet `T` and bank share `q` are latent. V3.1.1 therefore exposes
identification bounds and posterior intervals—not a falsely precise point
estimate. Observed, identified, posterior, scenario and causal claims remain
distinct throughout the API, workbench, notebook and submission artifacts.

## Authoritative V3.1.1 result

- 3,064,295 confidential supplied Syn Bank rows in private-evaluator mode.
- 20 supplied relationships × five product mappings = 100 heatmap cells.
- Exactly 15 approved E1-anchored cells and 85 E0 prior-led cells.
- 82 source facts: 31 approved and 51 pending finance-SME review.
- Pending facts may be `DEVELOPER_VERIFIED`, but cannot activate an anchor,
  change a bound/posterior/rank/economic result or support a client-facing claim.
- Active E1 pooling weight 0.35; 0.20 and 0.50 are explicit sensitivity arms.
- Trade Finance is first-ranked in 100% of the 10,000-draw representative global
  benchmark; its mean top-ten share is 55.7% and majority frequency is 87.75%.
  This is a sensitivity result, never a release condition.
- The Decision Twin adds stakeholder role, problem, solution bundle, engagement
  window, feasibility and the highest-positive-net-VOI question. The weekly plan
  contains eight discovery conversations.
- The 16-solution layer performs 320 governed evaluations. Available and
  fail-closed counts are machine-generated; no unavailable model is presented as
  an approved product recommendation.
- Provider adapters and validation controls exist for OpenAI, Anthropic and
  Google. Live execution requires fresh rotated environment credentials and an
  explicit public-only evaluation acknowledgement; access failure is never
  presented as success.

`HACKATHON_SUBMISSION_READY` and bank-production promotion are separate states.
Bank status remains `NOT_PROMOTABLE` until external calibration, approved bank
economics and controls, live-provider adjudication, a supervised RM pilot and a
qualified randomized outcome trial close.

## One-command reproduction

Create the locked environment, then run the single canonical writer:

```powershell
uv sync --frozen --extra dev --extra genai --extra production
uv run python scripts/build_submission.py
```

Private evaluators can supply the confidential archive without copying it into
the repository:

```powershell
$env:SYNBANK_DATA_ZIP = "C:\secure\hackathon\Data.zip"
uv run python scripts/build_submission.py
```

If the archive is unavailable, the notebook uses an independently generated,
anonymized public-mirror fixture. Cached aggregates show their source hash and
transformation version. No raw confidential row is committed or embedded in
notebook output.

Live provider evaluation is opt-in. Never reuse credentials pasted into chat:

```powershell
$env:LIVE_PROVIDER_EVAL_PUBLIC_ONLY_ACK = "true"
$env:OPENAI_API_KEY = "<fresh rotated secret>"
$env:OPENAI_PROVIDER_APPROVED = "true"
$env:OPENAI_MODEL_SNAPSHOT = "gpt-5.6-sol"
# Add equivalent approved Anthropic and Google variables.
$env:RUN_LIVE_PROVIDER_EVAL = "true"
uv run python scripts/build_submission.py
```

## Submission artifacts

- `output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf` — exactly one page.
- `output/presentation/Corporate-Wallet-Digital-Twin.pptx` — ten-slide judging deck.
- `notebooks/01_wallet_twin_demo.ipynb` — executed wallet-first judging notebook.
- `output/notebook/01_wallet_twin_demo.html` — portable notebook rendering.
- `outputs/audit/Public-Facts-Anchor-Register-V3.1.1.xlsx` — 82-fact review and wallet-impact workbook.
- `outputs/judging_manifest_v3.1.1.json` — build, hash, claim and gate manifest.
- `dashboard/` — entitled Wallet Portfolio, Coverage Plan, Client Twin and Governance workbench.
- `docs/judging_map.md` — judge question-to-evidence map.
- `docs/Corporate_Wallet_Digital_Twin_V3_1_System_Dossier.md` — complete system record.
- `docs/Corporate_Wallet_Digital_Twin_V3_1_Technical_Foundations.md` — statistical theory and production engineering.

## Product surfaces

The workbench opens on **Wallet Portfolio**, a 20×5 heatmap. Default colour is
contestable scenario contribution. Judges can toggle observed activity,
posterior wallet, estimated Syn share, contestable gap and evidence status.
Clicking a cell opens the complete `A`, `T P10/P50/P90`, `q P10/P50/P90`, `q*`
and `G` explanation before the Decision Twin action.

FX is labelled an exposure proxy. Liquidity is labelled a liquidity-flow
opportunity proxy. Heterogeneous product quantities are never summed into a
misleading single “banking spend” number; only scenario contribution is
aggregated.

Additive API reads:

- `GET /v3/wallet-portfolio?as_of=`
- `GET /v3/wallet-opportunities/{opportunityId}?as_of=`
- `GET /v3/clients/{clientId}/briefing-notes?as_of=`

All modelled reads require `as_of` and bank identity. Deny-by-default
authorization is tested before any entitled positive path.

## Verification

```powershell
uv run ruff check src tests scripts
uv run pytest
Set-Location dashboard
npm ci
npm run lint
npm test
npm audit --omit=dev --audit-level=high
```

CI also builds and starts the real ASGI image, proves unauthenticated `/v3`
access returns 401, then sends explicit demo entitlements and requires V3.1.1,
eight plan entries, 100 wallet cells and 15 approved anchors.

## Evidence and confidentiality boundary

The source estate contains public fact candidates, but only finance-SME
`APPROVED` facts are active. The 51 pending facts remain pending until an
accountable human reviewer completes the four-eyes pack. Codex deterministic QA
is not finance approval. Derived typed claims are not additional audited public
observations.

The private repository may contain challenge-derived aggregate fixtures and
references to the supplied archive. The public mirror is produced by an
allow-list exporter with independently generated anonymized data and must exclude
`ref/`, `Data.zip`, row-level derivatives, downloaded third-party snapshots,
credentials, provider payloads, caches and rendered intermediates.

## Interpretation contract

Only E3 multibank observation can support a **measured share** label. Public
accounting evidence is a noisy anchor, not a competitor transaction. Commercial
values are representative governed scenarios until bank pricing, FTP, liquidity,
capital, risk, cost and hurdle inputs are approved. Causal incremental value is
null until a qualified randomized RM trial passes its gates. “Uplift”, “optimal
share” and automated customer action remain prohibited.
