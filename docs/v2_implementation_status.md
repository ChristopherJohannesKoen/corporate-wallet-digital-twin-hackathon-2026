# Corporate Wallet Digital Twin V2 — implementation status

Status as of 9 August 2026:

- **Client demonstration: READY.** The workbench uses the full SynBank simulation, 82 point-in-time public E1 facts, a stratified representative multibank analog and governed scenario economics.
- **Bank production: NOT PROMOTABLE.** Bank-owned infrastructure, observations, approved economics, provider approval and real banker outcomes have not been supplied or approved.

These states are deliberately independent. The demo is complete enough for a client presentation, but simulated truth is never relabelled as an E3 multibank observation, representative rates are never presented as bank-approved pricing and simulated outcomes never support a causal claim.

## Current scorecard

| Capability | Client-demo result | Bank-production result |
|---|---|---|
| Public evidence | **9.0/10** — 82 page-cited E1 facts across all 20 clients; all 51 expanded facts pass automated page-grounding checks. | **8.5/10** — the 51 expanded facts still require Finance-SME plus independent reviewer approval and a signed approval manifest. |
| Wallet modelling | **9.0/10** — five product models, bounds, split-conformal audit and a deterministic 1,500-row stratified known-truth analog. | **8.0/10** — measured competitor share remains unavailable because named E3 multibank observations are zero. |
| Economics | **9.0/10** — complete scenario waterfalls, frontiers, break-even and sensitivity using representative governed packs. | **7.5/10** — production calculations fail closed until approved Treasury, Finance, FTP, capital, risk, cost and hurdle inputs exist. |
| Timing | **8.5/10** — explicit 30/60/90 probabilities, 3,440 surrogate start-stop intervals and a held-out discrete-time challenger. | **7.0/10** — no qualified recommendation/action/outcome history exists for promotion. |
| Causal learning | **8.0/10** — reproducible cluster assignment, 30 simulated clusters and complete event/outcome contracts. | **6.5/10** — uplift and causal value remain prohibited until a powered live randomized trial is completed. |
| GenAI | **9.0/10** — three provider adapters, structured validation, payload guard, circuit breaker, deterministic fallback and 809 governed checks. | **8.5/10** — live-provider publication remains blocked until keys are rotated, the provider is approved and an independently adjudicated evaluation passes. |
| Platform/security | **9.0/10** — 21/21 control definitions, valid Terraform, a pinned provider lock, valid Helm rendering and 53/53 valid Kubernetes resources. | **8.0/10** — the bank AWS/Databricks account, identity, Unity Catalog policies, SIEM destination and independent testing remain external gates. |
| RM experience | **7.5/10** — complete entitled client-demo journey, evidence layers, scenarios and captured interaction contracts. | **4.0/10** — zero supervised real banker sessions and no randomized field trial. |

## Verified release evidence

- Backend: **61/61 tests passed**.
- Frontend: lint passed, production build passed and **2/2 rendered tests passed**.
- Dependency audit: **zero production dependency vulnerabilities** at high severity or above.
- Source credential scan: no pasted OpenAI, Anthropic or Google credential patterns found.
- Client-demo gates: **11/11 passed**; status `CLIENT_DEMO_READY`.
- GenAI/evidence: **809 governed checks**, including a deterministic 640-case stress suite; no live-provider claim is made.
- Production target: **21/21 implementation definitions passed**.
- Terraform: checksum-verified Terraform 1.15.8, provider/module initialization and `terraform validate` passed; no plan or apply was run.
- Kubernetes: Helm lint and template passed; kubeconform validated **53 resources, 53 valid, 0 invalid**.
- Operations rehearsal: 300 local in-process reads at 16 workers, 100% success, **274 ms P95**; entitlement negatives 3/3 denied and 500 events restored byte-identically.
- Wallet mechanics: entity-disjoint synthetic split-conformal 90% coverage was **91.3%**. This is known-truth mechanics evidence, not E3 empirical calibration.
- Timing mechanics: the surrogate challenger improved held-out Brier score by **7.4%** with **3.2%** expected calibration error. This is not a live promotion result.

## Demonstration data estate

| Source | Rows/facts | Permitted use | Prohibited claim |
|---|---:|---|---|
| SynBank simulation | 3,064,295 rows | Client-demo activity, product and event journeys | Real bank activity |
| Audited public evidence | 82 E1 facts | Point-in-time anchors with citations and provenance | Client-attested or multibank-observed evidence |
| Africa trade-finance reference | 10,000 rows | Representative trade-finance simulation and stress | Named-client transactions |
| PaySim federated reference | 6,362,620 remote rows | Transaction-pattern reference and future benchmark work | Bank production observations |
| FinQA | 8,281 public train/development/test cases | Financial-report numerical-reasoning and golden-set design | Client facts or live-provider approval |
| Representative multibank analog | 1,500 generated rows | Model calibration mechanics and known-truth validation | Measured competitor wallet share |
| Simulated trial | 30 clusters | Experiment-pipeline rehearsal | Causal incremental value |

The client-demo watermark is:

`CLIENT DEMONSTRATION — SIMULATED/REPRESENTATIVE DATA — NOT FOR FINANCIAL DECISIONS`

## Production architecture delivered as code

The repository now contains the complete target definitions for private EKS services; object-locked and KMS-encrypted evidence/audit stores; IAM-authenticated MSK and Aurora PostgreSQL; CloudTrail integrity and VPC flow logs; per-service IRSA; Secrets Manager containers; deny-by-default network policy and OPA; Delta data products; Unity Catalog ABAC row filters and masks; an MLflow promotion policy; OpenTelemetry redaction/export; signed evidence manifests; CI supply-chain controls; and the entitled workbench.

Executable validation proves that the definitions are internally valid. It does not prove that an absent bank environment is operating correctly.

## Non-delegable production gates

1. Finance-SME and independent reviewer approval of the 51 queued facts, followed by KMS signing of the immutable manifest.
2. A representative, consented and point-in-time E3 multibank calibration panel.
3. Approved effective-dated bank pricing, FTP, liquidity, expected loss, capital, cost, tax and hurdle inputs.
4. Bank-owned AWS and Databricks accounts, VPC/subnets/DNS, deployment role, metastore, SCIM groups, SSO/MFA, Unity Catalog enforcement and SIEM integration.
5. Rotated provider credentials, third-party/privacy approval and an independently adjudicated live-provider golden-set evaluation.
6. Supervised real RM sessions followed by the powered cluster-randomized trial and reconciled outcomes.

Until those inputs exist, the production runtime remains fail closed and the workbench shows the demo and production release states separately.
