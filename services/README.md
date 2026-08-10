# V3 service deployment map

All services use the same signed, SBOM-attested image but select a different
ASGI entry point. This keeps schemas and control logic identical while the Helm
release gives each deployment its own workload identity, network policy, secret
scope and PostgreSQL credentials.

| Service | `WALLET_SERVICE_APP` | Owned interface |
|---|---|---|
| Ingestion | `ingestion_app` | Feed contracts, quarantine and acknowledgements |
| Evidence | `evidence_app` | Candidate intake and four-eyes review |
| Economics | `economics_app` | Effective-dated rate cards and calculations |
| Wallet model | `wallet_model_app` | Twins and model validation |
| Timing | `timing_app` | Event probability models |
| Recommendation | `recommendation_app` | V1/V3 opportunities, signals, scenarios, portfolios and interactions |
| Experiment | `experiment_app` | Assignments, eligibility and outcomes |
| GenAI | `genai_app` | Controlled extraction and narration |
| Entitlement | `entitlement_app` | Attribute projections and access decisions |
| Workbench BFF | `workbench_bff_app` | Entitled V1/V3 read model and composed Decision Lab payload |

The local executable is a reference adapter, not a claim that EKS, MSK, RDS or
Databricks are available in this workspace. Production adapters must be enabled
only after bank platform and risk approval.
