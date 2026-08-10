# V1 frozen regression boundary

This directory contains the model 1.1 assumptions, portfolio fixture, evidence
packs, deterministic briefs and generated registers preserved for regression
testing. They are not active V3 outputs and must not be presented as the current
client-demonstration state.

The V2 evidence/economics substrate and additive V3 decision layer consume the
frozen portfolio only as a stable observation fixture. Current governed outputs
are written under `outputs/v3`, `outputs/v3_validation` and
`dashboard/app/data/v3-fixture.json`.

To rerun the historical pipeline explicitly:

```powershell
uv run python -m wallet_twin.pipeline `
  --assumptions legacy/v1/config/assumptions.json `
  --output legacy/v1/outputs/runtime `
  --dashboard-data legacy/v1/outputs/runtime/dashboard-data
```
