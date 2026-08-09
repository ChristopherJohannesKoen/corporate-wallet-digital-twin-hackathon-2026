# Client-demo release

Status as of 9 August 2026: **CLIENT_DEMO_READY**.

The client-demo release is designed for an informed client walkthrough using
real public corporate facts and a governed simulated banking environment. It is
not a financial-decision or bank-production release.

## Data estate

| Source | Records | Classification | Permitted use |
|---|---:|---|---|
| Supplied SynBank banking pack | 3,064,295 | Synthetic simulation | Activity, seasonality, data-quality and service-contract demonstration |
| Official issuer reports | 82 facts, 20 clients | Public audited E1 | Point-in-time noisy accounting, FX, trade and maturity anchors |
| African trade-finance gap reference | 10,000 | Public representative synthetic, CC-BY-4.0 | Trade-finance scenario distributions and stress tests |
| Federated PaySim bank reference | 6,362,620 remote rows | Public representative synthetic, CC-BY-4.0 | Partition and scale-contract design only |
| FinQA | 8,281 public train/development/test cases | Public research benchmark, CC-BY-4.0 | Financial-report numerical-reasoning and golden-set design only |
| Representative multibank analog | 1,500 | Reproducible synthetic known truth | Wallet mechanics, selection weighting and interval calibration |
| Trial analog | 1,500 opportunities, 30 clusters | Reproducible synthetic outcomes | Event, assignment and causal-analysis rehearsal |

Every external source is pinned to a revision and recorded in
`data/v2/external_dataset_registry.json`. The locally used trade-finance file is
hash-verified. Representative records have `production_e3_eligible=false`, and
the multibank analog has no EvidenceTier value by design.

## Passed demo gates

- Dataset registry, revisions, local hashes and licence metadata validate.
- All 20 showcase clients have public E1 coverage; 51/51 expanded facts pass
  page-grounding automation.
- The representative wallet analog covers 300 relationships, every product and
  size, geography, sector and relationship-maturity strata.
- Known-truth split-conformal wallet coverage remains within the 85–95% gate.
- 809 deterministic GenAI/evidence checks pass, including a 640-case stress
  suite with a one-sided 95% zero-failure upper bound below 0.5%.
- Entitlement negative tests and event-recovery rehearsal pass.
- AWS/Databricks production control definitions pass 21/21 static controls.
- The demo never emits measured-share, causal-uplift or financial-decision claims.

## Display contract

The workbench watermark is:

`CLIENT DEMONSTRATION — SIMULATED/REPRESENTATIVE DATA — NOT FOR FINANCIAL DECISIONS`

That wording permits a client demonstration while preserving the origin and
decision-use boundary. It replaces the older “not for client use” wording; it
does not convert the underlying data into real bank or competitor observations.
