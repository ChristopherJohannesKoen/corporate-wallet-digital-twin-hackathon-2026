# Corporate Wallet Digital Twin V2.1

**Team:** Corporate Wallet Digital Twin  
**Team member:** Christopher Koen  
**Event:** Standard Bank Hackathon 2026  
**Repository:** <https://github.com/ChristopherJohannesKoen/corporate-wallet-digital-twin-hackathon-2026>

Corporate Wallet Digital Twin converts Syn Bank activity, audited public evidence
and governed assumptions into an uncertainty-aware list of corporate transaction-
banking conversations. It answers four questions for a relationship manager:
**who** to call, **what** product to discuss, **when** to act and **why** the
recommendation is defensible.

> **Data boundary:** client-facing results are a governed demonstration using the
> supplied Syn Bank simulation, public E1 evidence and representative benchmark
> data. They are not measured competitor share, bank-approved pricing or causal
> incremental value.

## Submission artifacts

- `output/pdf/Corporate-Wallet-Digital-Twin-One-Pager.pdf` - one-page submission.
- `output/presentation/Corporate-Wallet-Digital-Twin.pptx` - 10-minute judging deck.
- `notebooks/01_wallet_twin_demo.ipynb` - executed V2 judging notebook.
- `deliverables/Corporate_Wallet_Digital_Twin_V2_Technical_Foundations.docx` -
  detailed methodology, theory, architecture and limitations.
- `dashboard/` - entitled portfolio and client workbench.

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

## Reproduce the judging evidence

Python 3.11 or 3.12 and Node.js 22 are recommended. `uv` gives the exact locked
environment:

```powershell
uv sync --frozen --extra dev --extra genai --extra production
uv run python scripts/run_judging_validation.py
uv run jupyter nbconvert --execute --to notebook --inplace notebooks/01_wallet_twin_demo.ipynb
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

Start with `docs/judging_map.md`, `docs/v2_model_validation.md` and
`docs/client_demo_release.md` for the concise evidence map.
