# Corporate Wallet Digital Twin V3.1.1 — data dictionary

## V3.1.1 primary wallet products

`WalletPortfolioProjection` contains exactly 20 clients, five products and 100
`WalletPortfolioCell` records. Each cell keeps observed activity `A`,
identification bounds, posterior wallet `T`, share `q`, target-share scenario
`q*`, contestable gap `G`, scenario contribution, timing, evidence/approval
state and artifact versions. `WalletOpportunityDetail` is the complete
`A/T/q/q*/G` explanation and claim boundary. `ProviderBriefEvaluation` records
the provider, canonical model ID, pack hash, prompt/schema versions, validation
metrics, latency, tokens, estimated cost and acceptance status.

Only `APPROVED` E1 facts may affect these products. Consequently the V3.1.1
private judging projection has 15 approved-anchor cells and 85 prior-led cells.
FX is an exposure proxy and Liquidity is a liquidity-flow opportunity proxy;
heterogeneous activity quantities are never summed as a single banking-spend
measure.

## V3.1 canonical decision products

V3.1 keeps all V2/V3 products and adds `BusinessTwinSnapshot`,
`BusinessEvidenceClaim`, attribute/event graph nodes and edges, business events,
problem hypotheses, stakeholder resolutions, 320 client–solution estimates,
funding-route estimates, client- and bank-value components, feasibility
assessments, `ConversationCandidate`, Pareto results, weekly coverage plans,
information questions, approved client answers, change digests and conversation
outcomes. Canonical schemas are in `contracts/jsonschema/v31/`; all modelled
reads require `as_of`, and all records retain valid, event, ingestion and
availability time plus source/artifact lineage and entitlement domain.

`ConversationCandidate` is the banker-facing object. Its identity is a stable
hash over client, stakeholder role, problem, solution bundle, engagement window
and snapshot version. The original 100 client–product records remain analytical
inputs and frozen regression outputs.

## Conventions common to curated records

| Field | Type | Meaning |
|---|---|---|
| `business_key` | string | Stable domain key for the logical record |
| `source_system_key` | string | Identifier in the originating system |
| `event_time` | timestamp | When the business event occurred |
| `valid_from` / `valid_to` | timestamp | Effective-time interval; history is never overwritten |
| `ingestion_time` | timestamp | When the platform received the record |
| `as_of` | date | Required point-in-time model snapshot |
| `available_date` | date | Earliest date the evidence may be used without future leakage |
| `source_hash` | string | Content-addressed source/snapshot hash |
| `transformation_version` | string | Immutable transformation reference |
| `quality_status` | enum | `VALID`, `QUARANTINED`, `STALE` or governed equivalent |
| `owner` | string | Accountable data or model owner |
| `entitlement_domain` | string | Row/object authorization domain |
| `artifact_versions` | object | Model, prior, transformation, prompt, schema, rate and dataset versions |

Money uses decimal amounts, ISO currency, source unit, normalized amount and an FX-policy reference. Intervals contain lower/median/upper, nominal coverage, model version and as-of timestamp.

## Evidence and claim enums

`EvidenceTier`: `E0`, `E1`, `E2`, `E3`, `E4`.

`ClaimClass`: `OBSERVED`, `IDENTIFIED_BOUND`, `POSTERIOR`, `SCENARIO`, `CAUSAL`.
`ApprovalStatus`: `DRAFT`, `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `EXPIRED`.

Presence of E1 evidence does not imply approval. Measured competitor share requires E3. Causal value requires a validated trial and `CAUSAL` claim class.

## Source activity products

### `client_product_activity`

One point-in-time client/product activity record. Important fields: `activity_id`, `client_id`, `client_region`, `legal_entity_id`, `product`, `activity_type`, `event_time`, `as_of`, decimal `amount`, `currency`, `available_date` and common lineage fields.

### Supplied Syn Bank input domains

- Transactional banking: deduplicated transaction ID, client, date, leg type, direction, ZAR amount, currency, channel, beneficiary and reference.
- Cross-border payments: transaction ID, client, date, direction, currency pair, ZAR value, country and corridor type.
- Trade finance: instrument ID, client, date, instrument type, direction, tenor, ZAR value, country, contract type and status.

These are simulation inputs in the checked-in demonstration, not bank-production observations.

## Public evidence products

### `evidence_fact`

| Field | Meaning |
|---|---|
| `fact_id` / `business_key` | Stable fact version key |
| `entity_id`, `entity_name` | Relationship identifier and display name |
| `concept` | Normalized public concept such as revenue, debt, cash, FX exposure or working-capital balance |
| `value`, `unit`, `currency` | Source value preserved without silent normalization |
| `period_start`, `period_end` | Reporting period |
| `available_date` | Public availability gate |
| `tier` | Evidence tier; current public facts are E1 |
| `confidence` | Extraction/review confidence, not empirical model confidence |
| `approval_status` | Workflow state; only `APPROVED` facts may support approved-anchor claims |
| `source_title`, `source_url`, `page` | Human-verifiable citation |
| `document_hash` | Immutable source-document SHA-256 |
| `bounding_box` | Optional page geometry for production extraction |
| `restates_business_key` | Prior fact superseded by a restatement |

The V3 register contains 82 E1 facts covering all 20 clients: 31 approved and 51 pending.

### Approved product anchor

Transparent proxy with `product`, `name`, `low_zar`, `base_zar`, `high_zar`, `weight`, `formula`, `transformation_assumption`, `fact_ids`, `source_pages`, `period_end`, `available_date` and approval state. Fifteen approved anchors cover BHP, Glencore and Shoprite across Collections, Payments, Cross-border FX, Liquidity and Trade Finance.

## V2 governed substrate outputs

| Field | Meaning | Claim class |
|---|---|---|
| `observed_activity_zar` | Point-in-time focal-bank activity or disclosed proxy | `OBSERVED` or explicitly derived |
| `partial_identification_zar` | Deterministic envelope under transparent assumptions | `IDENTIFIED_BOUND` |
| `current_share.lower/median/upper` | Product-specific hierarchical posterior share | `POSTERIOR` |
| `total_wallet_zar.lower/median/upper` | Posterior wallet interval | `POSTERIOR` |
| `revenue_gap_zar.lower/median/upper` | Contestable scenario economics | `SCENARIO` |
| `evidence_tier` | Highest governing evidence tier | label, not probability |
| `calibration_status` | Prior-led/publicly anchored/client-validated/empirically calibrated | governance state |
| `top10_probability` | Monte Carlo rank probability | `POSTERIOR` |
| `timing_30d/60d/90d` | Named-event probability by horizon | baseline/posterior |

## V3 Shadow Wallet

### `shadow_wallet_reconstruction`

| Field | Meaning |
|---|---|
| `reconstruction_id` | Immutable reconstruction version key |
| `opportunity_id`, `entity_id`, `product`, `as_of` | Grain and point-in-time key |
| `observed_bank_flow` | Focal-bank activity supplied to the reconstruction |
| `latent_external_wallet` | Lower/median/upper external-wallet scenario interval |
| `total_wallet` | Observed plus reconstructed wallet interval |
| `bank_share` | Lower/median/upper scenario share |
| `flows[]` | Anonymous provider/corridor edge allocations |
| `ensemble_draws` | Number of reproducible posterior/transport draws; current fixture uses 256 |
| `normalized_entropy` | Allocation diffuseness diagnostic |
| `method` | Posterior-constrained ensemble and entropy-regularised Sinkhorn transport |
| `measurement_status` | Always `RECONSTRUCTED_NOT_MEASURED` in the current fixture |
| `provenance` | Simulation/public/representative source boundary |

### `shadow_wallet_draw` Delta product

One row per reconstruction/draw/client/product with latent wallet, share, evidence tier, model/policy versions, random seed, source snapshot, availability and entitlement domain.

### `shadow_wallet_edge` Delta product

One row per anonymous allocation edge with provider node, corridor/product, flow, transport cost, regularization, marginal residual and immutable reconstruction lineage. `provider_is_anonymous` must remain true without E3 data.

## PU product-need estimate

| Field | Meaning |
|---|---|
| `positive_label_observed` | Whether the opportunity appears in the selected-positive set |
| `labelled_positive_probability` | Transparent base learner probability |
| `selection_constant` | Elkan–Noto SCAR estimate of positive-label selection |
| `product_need_probability` | Corrected probability, clipped to the governed domain |
| `assumptions` | Selected positives correct; SCAR; unlabelled may contain positives; demo is not population calibration |
| `claim_class` | `POSTERIOR` |

The Delta product also retains lower/median/upper, class prior, selection mechanism, model version and source snapshot.

## Change-point state and leakage alarm

### Change-point state

`current_probability`, `recent_peak_probability`, `run_length_mode_months`, `signed_level_shift`, horizon probabilities, hazard-configuration version, baseline version, model version and source snapshot. These values are temporal posterior signals.

### Leakage alarm

`alarm_id`, `opportunity_id`, `severity`, `leakage_probability`, `change_probability`, `observed_level_decline`, `expected_external_flow_at_risk_zar`, `reason_codes`, threshold-policy version and `measurement_status`. The required status is `MODELLED_SIGNAL_NOT_CONFIRMED_LEAKAGE` unless an external observation confirms the interpretation.

## Treasury graph snapshot

Client-level scenario graph with `graph_id`, `as_of`, `client_id`, graph version, node/edge counts, concentration index, serialized node/edge payload, source snapshot, availability and entitlement domain. External nodes are anonymous.

## Economics and scenarios

### Effective rate card

Effective-dated product/legal-entity/segment/currency record with gross price, discount, FTP, liquidity, expected loss, capital, total cost, hurdle, approval, reconciliation, owner and source lineage. Production commercial output is blocked if any required value is missing, stale, unapproved or unreconciled.

### Portfolio scenario

`scenario_id`, `as_of`, `scenario_index`, `policy_version`, `random_seed`, `scenario_probability`, opportunity-value vector and source snapshot. Representative fixture scenarios are simulated.

### Portfolio selection

| Field | Meaning |
|---|---|
| `selection_id`, `portfolio_id` | Immutable decision artifact |
| `opportunity_id`, `client_id`, `product` | Selected/not-selected action grain |
| `expected_value` | Scenario expected contribution |
| `value_at_risk` / `conditional_value_at_risk` | Downside risk metrics |
| `marginal_capacity_cost` | Opportunity cost of constrained capacity |
| `constraint_reason_codes` | Capacity, concentration, product/sector/client constraints |
| `policy_version`, `source_snapshot_hash` | Reproduction lineage |
| `commercial_status` | `SIMULATED` until approved economics are used |
| `causal_status` | Must remain unvalidated until the trial gates pass |

The checked-in portfolio has capacity 12 and selects four Trade Finance, four Cross-border FX and four Liquidity actions.

## Evidence acquisition plan

`plan_id`, `candidate_id`, `opportunity_id`, `client_id`, `product`, evidence type/concept, acquisition cost, latency penalty, expected rank-flip probability, expected interval-width reduction, expected decision value, expected/net value of information, selection flag, approval status, required approval, policy version and source snapshot. `autonomous_external_retrieval` is false.

## Recommendation, experiment and V3 operational events

Every event uses `EventEnvelope`: event ID/type, occurred time, as-of, client/product/RM/team IDs, assignment arm/probability, evidence tier, estimates/rank, reason codes, artifact versions, entitlement context, censoring state and payload.

V1/V2 types remain `EligibilityRecorded`, `RecommendationAssigned`, `RecommendationDisplayed`, `RecommendationOpened`, `RecommendationDismissed`, `BankerActionRecorded`, `PipelineMilestoneRecorded`, `OutcomeRecorded`, `EvidenceApproved` and `AccessDecisionLogged`.

V3 adds `ShadowWalletReconstructed`, `LeakageSignalPublished`, `ActionPortfolioSelected`, `EvidenceAcquisitionApproved` and `DecisionBriefCompiled`. Operational PostgreSQL state is versioned in `decision_intelligence.reconstruction_run`, `signal_publication`, `portfolio_selection`, `evidence_acquisition_approval` and `brief_compilation`.

## Brief artifact

A decision brief contains the opportunity ID, title, summary, observed facts, identified bounds, posterior/scenario claims, citations, uncertainty, action status, evidence plan, artifact versions and measurement boundary. Every number/citation must exist in the closed evidence pack. Provider output is never an approval or CRM action.

## Active and legacy paths

| Path | Role |
|---|---|
| `data/v3/public_sensor_registry.json` | Canonical point-in-time public-sensor input |
| `dashboard/app/data/shadow-fixture.json` | V2 governed substrate fixture |
| `dashboard/app/data/v3-fixture.json` | V3 Decision Lab fixture |
| `outputs/v3/` | Canonical V3 machine outputs and selected briefs |
| `outputs/v3_validation/` | V3 validation report |
| `outputs/audit/Public-Facts-Anchor-Register-V3.1.1.xlsx` | Human-auditable evidence/approval/impact workbook |
| `contracts/` | Composed OpenAPI and JSON Schemas |
| `legacy/v1/` | Frozen V1 assumptions and outputs; regression only |

## V3.2 promotion artifacts

| Path | Contents |
|---|---|
| `contracts/promotion-gate-catalogue.json` | 24 gates as governed data, generated from the enforced catalogue |
| `contracts/jsonschema/v32-*.schema.json` | The 12 V3.2 contract schemas |
| `outputs/v32/v32_promotion_policy.json` | States, tracks, evidence modes, capability prerequisites, scoring policy |
| `outputs/v32/v32_signing_posture.json` | Which signers ran; `NO_REAL_BANK_SIGNING_CAPABILITY_ON_THIS_BUILD` |
| `outputs/v32/v32_simulation_laboratories.json` | Canonical-tier results for all seven laboratories |
| `outputs/v32/v32_shadow_rehearsal.json` | 47 simulated days, day-17 incident, 30 clean days, 0 bank days |
| `dashboard/app/data/promotion-fixture.json` | The promotion readiness view's projection |
| `infra/sql/002_promotion_schemas.sql` | Append-only promotion schema with the invariants restated as CHECK constraints |

### Key fields that must never be conflated

| Field | Meaning |
|---|---|
| `as_of` | The business date the evidence describes; the point-in-time boundary |
| `generated_at` | Wall-clock time the artifact was computed; provenance only |
| `published_at` | When it became visible to consumers; later than `generated_at` when review sits between |
| `simulation_clock` | Virtual clock position. **Present only on synthetic evidence** |
| `expires_at` | Freshness horizon; orthogonal to the four above |
| `shadow_rehearsal_days` | Simulated days. Always published beside the next row |
| `elapsed_bank_shadow_days` | Real elapsed bank days. **Zero, and structurally unable to be otherwise in a rehearsal** |
