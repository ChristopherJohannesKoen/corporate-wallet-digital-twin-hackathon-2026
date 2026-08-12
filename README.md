# Corporate Wallet Digital Twin V3.1

**Team:** Corporate Wallet Digital Twin  
**Team member:** Christopher Koen  
**Event:** Standard Bank Hackathon 2026  
**Repository:** <https://github.com/ChristopherJohannesKoen/corporate-wallet-digital-twin-hackathon-2026>

Corporate Wallet Digital Twin reconstructs the latent corporate financial system
from one bank's partial observations, then decides where scarce RM and evidence-
acquisition capacity has the greatest robust value. It combines Syn Bank activity,
audited public evidence and governed priors to answer **what is unseen**, **what is
changing**, **which actions survive uncertainty** and **which missing evidence is
worth acquiring next**.

**V3.1 changes the decision object.** V3 ranked `(client, product)`. V3.1 ranks
the conversation a banker actually has:

```
(client, stakeholder, business problem, solution bundle, engagement window)
```

It reconstructs each client's business model from twelve evidence-linked
components, detects which of eighteen banking problems that model implies,
resolves the responsible stakeholder role, evaluates all sixteen supported
solutions, quantifies client value and bank value **separately**, applies six
feasibility gates, works out the timing, proposes the highest-value question to
ask, and turns the result into an eight-conversation weekly coverage plan under a
mixed-integer CVaR objective. V3.1 is additive: V3.0 outputs are frozen as a
regression boundary and reproduce at the frozen published two-decimal precision.

> Start with `docs/v31_implementation_status.md` — it states what is built, what
> is measured, and where the evidence base falls short of the target rather than
> papering over the gap.

> **Data boundary:** client-facing results are a governed demonstration using the
> supplied Syn Bank simulation, public E1 evidence and representative priors
> data. They are not measured competitor share, bank-approved pricing or causal
> incremental value.

## Submission artifacts

- `output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf` - one-page submission.
- `output/presentation/Corporate-Wallet-Digital-Twin.pptx` - 10-minute judging deck.
- `notebooks/01_wallet_twin_demo.ipynb` - executed V3.1 judging notebook.
- `deliverables/Corporate_Wallet_Digital_Twin_V3_1_System_Dossier.docx` -
  authoritative end-to-end V3.1 product, control, validation and handoff record.
- `deliverables/Corporate_Wallet_Digital_Twin_V3_1_Technical_Foundations.docx` -
  detailed V3.1 statistical theory, latent-network models, decision engineering,
  production architecture and literature traceability.
- `dashboard/` - entitled portfolio and client workbench.
- `docs/Corporate_Wallet_Digital_Twin_V3_1_System_Dossier.md` - source edition of
  the complete V3.1 dossier.
- `docs/Corporate_Wallet_Digital_Twin_V3_1_Technical_Foundations.md` - source
  edition of the V3.1 technical white paper.
- `docs/v3_methodology.md` - concise V3 theory, algorithms, contracts and literature.
- `docs/v3_implementation_status.md` - implemented/external-gate status register.
- `docs/v31_implementation_status.md` - **V3.1 Decision Twin status, measured
  outputs and the honest gaps**.

## What V3.1 adds

- 20 Business Model Twins x 12 components = 240 evidence-linked components.
- 905 typed business evidence claims, with the existing 82 public facts migrated
  and relinked rather than discarded, plus 71 explicit gap records.
- A two-layer business knowledge graph: 993 nodes, 1,154 edges, zero orphans,
  zero dangling edges, reproducible for the same `as_of`.
- 360 problem hypotheses from 18 interpretable detectors, each storing
  disconfirming evidence separately from supporting evidence.
- 320 client-solution projections across 16 solution families - 198 quantified,
  122 deliberately fail-closed with a stated reason.
- Client value and bank value computed by separate engines that are never netted;
  hedging solutions report risk reduction and refuse to monetise it.
- An eight-conversation weekly plan from a genuine mixed-integer CVaR program
  (`scipy.optimize.milp`/HiGHS, Rockafellar-Uryasev linearisation) with a
  labelled greedy fallback.
- 308 decision-directed questions selected from 891 evaluated - every one has
  positive net VOI and can change a rank, bundle, feasibility state or abstention.
- A full V1/V2/V3/V3.1 test suite, including the frozen V3.0 boundary; the
  current verified count is reported by CI rather than hard-coded here.

## What the current demonstration proves

- 3,064,295 supplied Syn Bank rows across 20 relationships and five products.
- 82 point-in-time public E1 facts; 51 expanded facts remain clearly marked as
  pending finance-SME approval.
- Independent identification bounds plus five product-specific posterior models.
- A 1,500-row, 300-relationship known-truth multibank analog used only to validate
  model mechanics; it is never relabelled as real E3 observation.
- Split-conformal 90% wallet interval coverage of 91.3% in that known-truth lab.
- Correlated 10,000-draw sensitivity plus the frozen 3x3 rate/prior benchmark.
- 30/60/90-day timing outputs and 3,440 transaction-derived start-stop intervals.
- Three controlled GenAI adapters, deterministic validation and 809 governed
  checks, including a 640-case stress suite with zero validator failures.
- 1,500 entropy-constrained anonymous shadow-flow edges across 100 client-product
  reconstructions, all satisfying exact wallet mass balance.
- Positive-unlabelled product-need estimates with the SCAR assumption exposed.
- 100 Bayesian online change-point replays and explicitly modelled leakage alarms.
- A 12-action RM portfolio satisfying client, product and sector concentration
  constraints under 512 commercial scenarios and lower-tail CVaR.
- An eight-request decision-directed evidence queue containing only positive-net-
  value-of-information requests; autonomous retrieval remains disabled.

## Reproduce the judging evidence

Python 3.11 or 3.12 and Node.js 22 are recommended. `uv` gives the exact locked
environment:

```powershell
uv sync --frozen --extra dev --extra genai --extra production
uv run python scripts/export_v3_contracts.py
uv run python scripts/freeze_v3_regression.py    # V3.0 regression boundary
uv run python scripts/export_v31_contracts.py    # V3.1 schemas, OpenAPI, artifacts
uv run --extra dev python scripts/run_judging_validation.py
uv run python scripts/run_v3_validation.py
uv run --extra dev python scripts/build_v3_notebook.py
# With the bundled @oai/artifact-tool available:
node scripts/build_presentation.mjs .
```

If the confidential hackathon archive is available, point the pipeline to it
without moving it into the repository:

```powershell
$env:SYNBANK_DATA_ZIP = "C:\secure\hackathon\Data.zip"
uv run --extra dev python scripts/run_judging_validation.py
```

Without that archive, the runner reproduces the public/representative validation
laboratory and retains the frozen aggregate transaction-history results supplied
in `outputs/v2_validation/offline_validation_report.json`.

Downloaded issuer PDFs, extracted page text and third-party dataset snapshots are
also intentionally absent from Git. Registry and model-mechanics checks remain
fully reproducible from the committed aggregate fixtures. Page-level evidence QA
reports an incomplete local source cache rather than silently passing; hydrate the
pinned paths in `data/v2/external_dataset_registry.json` to rerun that source audit.

Run the API and workbench:

```powershell
$env:WALLET_DEPLOYMENT_MODE = "FIXTURE"
uv run uvicorn wallet_twin_v2.service_apps:workbench_bff_app --host 127.0.0.1 --port 8000
Set-Location dashboard
npm ci
npm run dev
```

Run verification:

```powershell
uv run pytest -q
Set-Location dashboard
npm ci
npm run lint
npm test
```

The active machine outputs are `outputs/v3/`, the composed contract is
`contracts/openapi.json`, and the V3 evidence workbook is
`outputs/audit/Public-Facts-Anchor-Register.xlsx`. Frozen V1 assumptions,
fixtures and expected outputs are regression-only assets under `legacy/v1/`.

## Repository safety

The supplied hackathon archive, raw/row-level derivatives, downloaded external
repositories, temporary OCR files and all credentials are excluded by
`.gitignore`. Never commit `ref/`, `data/v2/external/`, `.env`, API keys or
provider tokens. External sources are recorded by URL, revision and hash in
`data/v2/external_dataset_registry.json`.

## Interpretation contract

Observed activity, identified bounds, posterior estimates, commercial scenarios
and causal value are distinct claim classes. Only E3 multibank observation can
support a "measured share" label. Accounting facts are noisy anchors rather than
exact wallet labels. Scenario economics fail closed when approved inputs are
missing. "Uplift", "optimal" and "expected incremental value" remain prohibited
until the registered causal gates pass.

V3.1 adds four contract-enforced boundaries on top of these. An `UNKNOWN` twin
component carries no facts and must say what is missing. An indicator resting on
pending-review evidence is `INFERRED`, never `SUPPORTED`. Qualitative client
value cannot carry an interval, so risk reduction is never silently converted to
rand. A failed feasibility gate blocks the bundle, and a material unknown gate
converts a product proposal into a discovery conversation.

Start with `docs/v31_implementation_status.md`, then `docs/v3_methodology.md`,
`docs/v3_implementation_status.md` and `docs/judging_map.md` for the concise
evidence map.
