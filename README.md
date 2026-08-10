# Corporate Wallet Digital Twin V3

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

> **Data boundary:** client-facing results are a governed demonstration using the
> supplied Syn Bank simulation, public E1 evidence and representative priors
> data. They are not measured competitor share, bank-approved pricing or causal
> incremental value.

## Submission artifacts

- `output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf` - one-page submission.
- `output/presentation/Corporate-Wallet-Digital-Twin.pptx` - 10-minute judging deck.
- `notebooks/01_wallet_twin_demo.ipynb` - executed V3 judging notebook.
- `deliverables/Corporate_Wallet_Digital_Twin_V3_System_Dossier.docx` -
  authoritative end-to-end V3 product, control, validation and handoff record.
- `deliverables/Corporate_Wallet_Digital_Twin_V3_Technical_Foundations.docx` -
  detailed V3 statistical theory, latent-network models, decision engineering,
  production architecture and literature traceability.
- `dashboard/` - entitled portfolio and client workbench.
- `docs/Corporate_Wallet_Digital_Twin_V3_System_Dossier.md` - source edition of
  the complete V3 dossier.
- `docs/Corporate_Wallet_Digital_Twin_V3_Technical_Foundations.md` - source
  edition of the V3 technical white paper.
- `docs/v3_methodology.md` - concise V3 theory, algorithms, contracts and literature.
- `docs/v3_implementation_status.md` - implemented/external-gate status register.

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
uv run python scripts/run_judging_validation.py
uv run python scripts/run_v3_validation.py
uv run python scripts/build_v3_notebook.py
# With the bundled @oai/artifact-tool available:
node scripts/build_presentation.mjs .
```

If the confidential hackathon archive is available, point the pipeline to it
without moving it into the repository:

```powershell
$env:SYNBANK_DATA_ZIP = "C:\secure\hackathon\Data.zip"
uv run python scripts/run_judging_validation.py
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
uv run uvicorn wallet_twin_v2.api:app --host 127.0.0.1 --port 8000
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

Start with `docs/v3_methodology.md`, `docs/v3_implementation_status.md` and
`docs/judging_map.md` for the concise evidence map.
