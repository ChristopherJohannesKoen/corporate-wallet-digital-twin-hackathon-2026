# Runbook

## Rebuild analytics

From the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m wallet_twin.pipeline
```

Expected outputs include `outputs/data/portfolio.json`, `outputs/opportunity_register.csv`, 20 client evidence packs, 20 banker briefs, validation JSON and the mirrored `dashboard/public/data/portfolio.json`.

## Validate

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
cd dashboard
npm test
```

## Optional LLM brief

```powershell
$env:OPENAI_API_KEY = "..."
$env:PYTHONPATH = "src"
python -m wallet_twin.genai --evidence outputs/evidence/E01.json --output outputs/briefs/E01-llm.md
```

Never place keys in source control. Without the key, the command intentionally emits the deterministic fallback.

## Refresh public facts

Add governed records to `data/public_facts.csv`, including `available_date`, source URL and page. Rebuild the pipeline. Do not overwrite original source values or insert facts without provenance.

## Capture outcomes

Append recommendation, action and outcome events to `data/interventions.csv`. Do not interpret missing outcomes as failures; distinguish not-actioned, pending and unknown.

## Troubleshooting

- Missing ZIP: verify `ref/Data Sets/Data.zip`.
- Portfolio JSON missing in app: rerun the Python pipeline.
- Low confidence: expected when public or competitor evidence is absent; investigate rather than weaken the threshold.
- Large ranking movement: inspect product economic-rate assumptions and `P(top 10)` before acting.

