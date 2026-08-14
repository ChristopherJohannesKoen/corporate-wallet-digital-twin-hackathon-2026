# Corporate Wallet Digital Twin V3.1.1 — operational runbook

## V3.1.1 canonical rebuild and smoke test

V3.1 adds the Business Twin service while keeping `/v1` and existing `/v3`
responses backward compatible. Rebuild contracts, canonical outputs and the
server-only workbench fixture with:

```powershell
uv run python scripts/build_submission.py
```

This is the only command permitted to write the final judging notebook, PDF,
PPTX, workbook and manifest. `freeze_v3_regression.py` is a historical
maintenance utility and is not part of submission reproduction.

Start the composed BFF with `uv run uvicorn wallet_twin_v2.service_apps:workbench_bff_app`
and smoke-test `GET /v3/decision-twin?as_of=2026-06-30&week_start=2026-07-06`.
The separate Business Twin service is
`wallet_twin_v2.service_apps:business_twin_app`. All V3.1 mutations require an
idempotency key and write an immutable domain event/outbox record. Rollback is
atomic at the snapshot manifest; do not mix twin, policy, rate, graph or prompt
versions. A successful internal rebuild does not override `NOT_PROMOTABLE`.

## Scope and current release state

This runbook operates the composed V3 repository: V2 supplies evidence, economics, timing, entitlements, events and the controlled GenAI gateway; V3 adds latent-network reconstruction, PU need, change-point/leakage signals, constrained action selection and decision-directed evidence acquisition. The checked-in deployment is a reproducible client-demonstration candidate. Bank production remains fail-closed until the release object reports no external blocking gates.

## Prerequisites

- Python 3.12 and `uv`.
- Node.js 22.13 or newer for the workbench.
- Docker for container smoke tests.
- Terraform, Helm and bank credentials only for an approved target environment.
- Provider keys only in an approved secret manager; never in source, fixtures, shell history or client bundles.

Install pinned Python dependencies:

```powershell
uv sync --frozen
```

Install workbench dependencies:

```powershell
Set-Location dashboard
npm ci
Set-Location ..
```

## Canonical rebuild

Generate all V1/V2/V3 JSON Schemas, the composed BFF OpenAPI contract, dashboard fixtures and canonical V3 outputs:

```powershell
uv run python scripts/export_v3_contracts.py
```

Expected active outputs:

- `dashboard/app/data/shadow-fixture.json`: governed V2 substrate snapshot.
- `dashboard/app/data/v3-fixture.json`: composed V3 Decision Lab fixture.
- `outputs/v3/decision-lab.json`: canonical machine-readable V3 snapshot.
- `outputs/v3/validation.json`: V3 validation and release decision.
- `outputs/v3/briefs/*.json`: governed briefs for selected actions.
- `contracts/openapi.json`: composed workbench-BFF V1/V3 OpenAPI.
- `contracts/jsonschema/*.schema.json`: canonical schemas.

`legacy/v1/` is immutable regression material. Do not write active outputs there except when intentionally reproducing the frozen baseline into a separate runtime directory.

## Validation sequence

Run the V3 analytical validation and complete test suite:

```powershell
uv run python scripts/run_v3_validation.py
uv run pytest -q --cov=wallet_twin_v2 --cov=wallet_twin_v3 --cov-report=term-missing
uv run ruff check src tests scripts
```

Run workbench gates:

```powershell
Set-Location dashboard
npm run lint
npm test
npm audit --omit=dev --audit-level=high
Set-Location ..
```

Run deliverable gates:

```powershell
uv run python scripts/run_judging_validation.py
```

The generated validation report must retain zero measured competitor-share and zero causal-value claims. Any drift in fixtures, contracts, validation reports or canonical outputs must be reviewed rather than silently committed.

## Local service operation

The ten service deployments use one signed image with separate ASGI entry points. Start the composed workbench BFF locally:

```powershell
$env:WALLET_SERVICE_APP = "workbench_bff_app"
$env:WALLET_DEPLOYMENT_MODE = "FIXTURE"
uv run uvicorn wallet_twin_v2.service_apps:workbench_bff_app --host 127.0.0.1 --port 8000
```

Smoke-test health and the live V3 decision payload:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod "http://127.0.0.1:8000/v3/decision-lab?as_of=2026-06-30"
```

Expected health version is `3.0.0`. Outside fixture mode, missing bank identity must produce `401`; entitlement denials must produce `403` and an immutable access decision.

## Container smoke test

```powershell
docker build -t corporate-wallet-digital-twin:v3 .
docker run --rm -d --name wallet-v3-smoke -p 8000:8000 `
  -e WALLET_SERVICE_APP=workbench_bff_app `
  -e WALLET_DEPLOYMENT_MODE=FIXTURE `
  corporate-wallet-digital-twin:v3
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod "http://127.0.0.1:8000/v3/decision-lab?as_of=2026-06-30"
docker stop wallet-v3-smoke
```

The image must contain `data/v3/public_sensor_registry.json` and `legacy/v1/fixtures/portfolio.json`. A successful image build without the V3 service-start smoke test is not evidence that the image is runnable.

## Workbench modes

Without `WALLET_API_BASE_URL`, the server route returns the bundled V3 fixture and sets `x-wallet-mode: governed-fixture-v3`. With the base URL configured, it proxies `/v3/decision-lab`, returns the live entitlement-filtered payload and sets `x-wallet-mode: bank-api-live-v3`. It must never probe a live API and then substitute fixture data.

```powershell
Set-Location dashboard
$env:WALLET_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

## Public evidence workflow

1. Ingest allow-listed documents, hash them and store originals immutably.
2. Retain page geometry, tables, period, currency, unit and `available_date`.
3. Create extraction candidates; never publish candidates directly.
4. Run deterministic unit/sign/period/arithmetic/duplicate/restatement/citation validators.
5. Require finance-SME review and four-eyes approval for material facts.
6. Publish `EvidenceApproved` only after approval; restatements append a new version.
7. Rebuild the audit workbook and ensure all formula checks pass.

The active register is
`outputs/audit/Public-Facts-Anchor-Register-V3.1.1.xlsx`: 82 E1 source facts,
20 clients, 31 approved and 51 pending. Pending facts remain candidate evidence
and cannot activate anchors. The expected wallet surface is exactly 15 E1
anchored and 85 E0 prior-led client-product opportunities.

## V3 analytical cycle

For each `as_of` snapshot:

1. Reconcile observed activity and public-sensor eligibility.
2. Run deterministic bounds and V2 posterior substrate.
3. Reconstruct Shadow Wallet draws/edges and check transport mass balance.
4. Produce PU product-need estimates with selection mechanism and class prior.
5. Update Bayesian run-length state and leakage alarms.
6. Generate seeded economic scenarios from approved inputs or simulated demo packs.
7. Select the CVaR-aware portfolio subject to client/product/sector/capacity constraints.
8. Rank evidence acquisitions by net VOI and route them for approval.
9. Compile closed claim packs and deterministic/LLM briefs.
10. Publish versioned completion, signal, selection, approval and brief events.

Failed mass balance, missing point-in-time fields, stale rates, unregistered artifacts, entitlement failures or unsupported claims quarantine the run.

## GenAI operation

The provider gateway is disabled by default. Enable only after provider, privacy, residency, retention and third-party-risk approval. Use schema-constrained output, a pinned model, `store: false`, no external tools and minimized entitled evidence. Production extraction and narration require sealed-set evaluation and independent adjudication.

If the provider is unavailable or any validation fails, return the deterministic brief. The model cannot approve facts, acquire evidence, change CRM state or contact clients.

## Databricks and MLflow

Apply `infra/databricks/curated_tables.sql` and `infra/databricks/data_products.sql` through a migration identity with governed-tag `ASSIGN` permission. V3 data products include Shadow Wallet draws/edges, PU estimates, change-point state, leakage alarms, Treasury graphs, scenarios/selections and evidence-acquisition plans.

Register all artifacts listed by `config/mlflow_promotion_policy.json`. Automatic promotion and rollback are disabled. Promotion requires signed human approval and the candidate/shadow/champion gates documented in the model card.

## AWS/EKS release

1. Obtain architecture, privacy, security, model-risk and third-party approvals.
2. Provision through bank CI with remote encrypted Terraform state.
3. Apply Unity Catalog tags/policies and PostgreSQL operational schemas.
4. Create MSK topics and schema compatibility rules.
5. Deploy signed containers by Helm using separate workload identities and databases.
6. Connect OpenTelemetry to the approved SIEM.
7. Verify SSO/MFA, short-lived identities, deny-by-default ABAC and row-level controls.
8. Execute cross-client/cross-region/sensitive-economics negative tests.
9. Run shadow mode for 30 consecutive clean days before any supervised RM exposure.

## Incident and rollback

Stop publication immediately for a source reconciliation failure, future-data leak, entitlement breach, critical unsupported claim, transport mass-balance failure, invalid economics, schema incompatibility or material monitoring breach. Preserve source snapshots, events, access decisions and artifacts. Roll back application, model, prior, prompt, rate, policy or schema by immutable version/alias; do not overwrite history.

## Troubleshooting

- **`/v3` missing:** confirm `WALLET_SERVICE_APP` selects recommendation or workbench BFF and health reports 3.0.0.
- **Decision Lab still shows fixture:** verify `WALLET_API_BASE_URL`, the live response and `x-wallet-mode`.
- **Image import fails:** confirm `data/v3/public_sensor_registry.json` is in the container.
- **Commercial values blocked:** inspect rate approval/effective dates and reconciliation; do not default missing rates.
- **Low or unstable score:** inspect evidence tier, interval width, PU selection assumptions, change state and scenario sensitivity.
- **Workbook check fails:** rebuild fixtures first, then rebuild/verify the workbook; do not edit computed cells manually.
- **Provider evaluation fails:** disable the provider and retain deterministic fallback.
- **Cross-client result appears:** treat as a security incident; disable the route and preserve access-decision evidence.

## V3.2 promotion twin

- **Promotion state looks wrong:** it is recomputed from gate evaluations on
  every read and never stored. Inspect `/v3/promotion/transitions` for the first
  transition whose blocking gates are unsatisfied; the walk stops there.
- **A gate shows red with no action:** every gate carries
  `what_would_make_real_pass`. If it is empty, that is a catalogue defect, not a
  blocked gate.
- **Fixture mode rejects a write (409):** expected. A demonstration fixture must
  never be able to produce bank authorisation. Real-track writes require a
  non-fixture deployment.
- **`POLICY_DIVERGENCE_DENIED`:** OPA and the in-process policy disagreed, so the
  request was denied and recorded. Run
  `python scripts/check_policy_agreement.py` against the lab to see the full
  matrix. Do not "fix" this by preferring one policy — one of them has drifted
  and both need review.
- **OPA unreachable:** the gateway raises rather than allowing. Restore OPA;
  never fail open.
- **MinIO object-lock bootstrap fails:** object lock cannot be enabled on an
  existing bucket. Recreate them: `docker compose down -v && docker compose up -d`.
- **Rehearsal reports 30 clean days:** that is simulated time. Check
  `elapsed_bank_shadow_days` in the same payload; it is 0 and cannot be
  otherwise. Thirty *elapsed* bank days is a separate, unmet gate.
- **A signer reports `NOT_EXECUTED`:** Sigstore needs an ambient GitHub OIDC
  token and KMS needs a live AWS account plus an `ECDSA_SHA_256` key — the
  existing Terraform key is RSA-3072. Neither returns plausible bytes when
  unavailable; both raise.
