# Corporate Wallet Digital Twin V3.1 — implementation status

**Version:** 3.1.0 · **API major:** `/v3` (unchanged) · **`as_of`:** 2026-06-30 ·
**Week start:** 2026-07-06

V3.1 extends V3 rather than replacing it. V2 remains the governed evidence and
economics substrate, V3 remains the latent-structure and change-detection layer,
and V3.1 adds the decision object a corporate banker actually acts on:

```
(client, stakeholder, business problem, solution bundle, engagement window)
```

The 100 `client × product` V3 opportunity records remain available as analytical
inputs and regression outputs. They are no longer the final banker decision
object.

---

## 1. What is built and measured

| Surface | Measured output |
|---|---|
| Business Model Twin | 20 clients × 12 components = **240 components** |
| Typed business evidence | **905 claims**, 85 E1 (82 legacy facts migrated and relinked), 820 E0 bank-observed/representative |
| Explicit evidence gaps | **71 gap records** across material unsupported domains |
| Business knowledge graph | **993 nodes / 1,154 edges**, attribute + event layers, 0 orphans, 0 dangling edges |
| Business events | **84 dated events** derived from evidence and V3 change points |
| Problem detectors | 20 × 18 = **360 hypotheses**, 224 identified, 194 commercially eligible |
| Solution estimators | 20 × 16 = **320 projections**, 198 available, **122 fail-closed with a stated reason** |
| Funding-route intelligence | 20 projections, probabilities sum to 1.0, challenger registered but not promotable |
| Conversation candidates | **224**, each with stakeholder, window, dual value, feasibility and explanation path |
| Weekly coverage plan | **8 conversations**, MILP solver status `OPTIMAL`, every concentration constraint satisfied |
| Decision-directed questions | 891 evaluated, 308 selected, all positive-net-VOI and all decision-changing |
| Governed events | 12 new types on 4 domain topics; 1,148 published in the fixture run |
| Test suite | Full V1/V2/V3/V3.1 suite, including 77 focused V3.1 tests and the frozen V3.0 boundary; the verified count is emitted by CI |

Reproduce with:

```bash
python scripts/freeze_v3_regression.py     # V3.0 regression boundary
python scripts/export_v31_contracts.py     # schemas, OpenAPI, validation artifacts
pytest tests -q                            # current verified count is emitted by pytest/CI
```

---

## 2. Honest gaps — read this before demonstrating

These are the places where the plan's target and the evidence that actually
exists diverge. Nothing has been fabricated to close them.

### 2.1 The 15-E1-claims-per-client target is not met

The plan targets **15 reviewed E1 claims per client**. The real audited public
evidence base reaches 11 for the deepest client and 3 for most. Manufacturing
220 additional "audited" figures with invented page references would have hit
the number and destroyed the evidence-first premise of the whole system.

Instead the shortfall is reported as an open curation gate:

```
e1_threshold_status: BLOCKING_GATE_OPEN_INSUFFICIENT_AUDITED_PUBLIC_EVIDENCE
e1_threshold_shortfall_clients: all 20
```

The thresholds that *are* met — and are met genuinely — are ≥15 typed claims per
client (minimum 44), ≥9 of 12 domains covered per client (minimum 11), and at
least one approved critical-path claim behind every client-facing problem.

### 2.2 Every conversation is currently DISCOVERY, none is a product proposal

224 conversations, 0 eligible for a product proposal. This is the feasibility
policy working, not a defect. Compliance/conduct and operations/onboarding are
`UNKNOWN` for every bundle because no bank system is connected in the
demonstration boundary, and the governed rule is that a material unknown
converts the action into discovery. A product proposal becomes possible only
once those gates are attested — which is what
`POST /v3/feasibility/{id}/attestations` exists to record.

### 2.3 Three solution families fail closed for all 20 clients

Project finance, sustainable finance and M&A advisory return
`available=False` everywhere, because no reviewed project/SPV topology, ESG
activity evidence or transaction evidence exists. Working-capital revolving is
available for only 1 client, because a positive working-capital gap can be
computed from reviewed evidence for only 1. These are the fail-closed paths
doing their job.

### 2.4 Eleven solution families have no approved rate card

Bank contribution is published only where a V2 rate card exists — the five
legacy products. Every other bundle reports
`bank_value.status = "BLOCKED"` with reason codes, rather than an estimate.

### 2.5 Nothing here is calibrated

No adjudicated problem labels, no financing-event panel, no RM outcome history.
Every new probability is labelled `SCENARIO` with an explicit
`calibration_status`. The only `POSTERIOR` claims are the ones inherited
unchanged from V3.

---

## 3. Interpretation boundaries preserved from V2/V3

| Claim class | Meaning | Where it appears in V3.1 |
|---|---|---|
| `OBSERVED` | Measured in the bank's own books | Bank-observed flows, corridors, currency pairs |
| `IDENTIFIED_BOUND` | A bound that holds without a prior | Indicators, maturity windows |
| `POSTERIOR` | A probability under a stated assumption | V3 PU need, change points, leakage |
| `SCENARIO` | A governed what-if | All 11 new solution families, all new problem weights, both value engines |
| `CAUSAL` | Withheld until a randomized trial closes | Never populated — `causal_incremental_value` is contractually `None` |

Additional invariants enforced by contract validators, not convention:

- An `UNKNOWN` twin component carries **no facts** and must state what is missing.
- An indicator resting on pending-review evidence is `INFERRED`, never `SUPPORTED`.
- A qualitative or unavailable client-value component **cannot carry an interval** —
  risk reduction is never silently converted to rand.
- `guaranteed_saving_claimed` raises on `True`.
- A failed feasibility gate must block; a blocked bundle cannot propose a product.
- Only positive-net-VOI questions that can change a decision may be selected.
- A greedy coverage fallback must be labelled `DEGRADED_FALLBACK`.
- Funding-route probabilities must sum to one.
- Review-candidate graph edges are never explainable, whatever their claim class.

---

## 4. Architecture

```
src/wallet_twin_v31/
  taxonomy.py           10 roles · 18 problems · 16 solutions · 12 domains · 288-pair matrix
  contracts.py          ConversationCandidate and every supporting contract
  events.py             12 event types over 4 domain topics
  business_evidence.py  typed claim registry, migration, gap records, coverage report
  indicators.py         CCC · liquidity buffer · WC gap · refinancing exposure · FX exposure
  business_twin.py      twelve-component snapshots
  business_graph.py     attribute + event layers, explanation paths, entitlement filtering
  change_digest.py      point-in-time "what changed?"
  problems.py           18 interpretable detectors with disconfirming evidence
  stakeholders.py       governed responsibility-matrix resolver
  solutions.py          16 estimators, fail-closed by default
  funding_routes.py     transparent scorecard + registered challenger gate
  value.py              separated client-value and bank-value engines
  feasibility.py        six gates
  timing.py             engagement windows and "why now"
  pareto.py             robust dominance over common scenario draws
  coverage.py           Rockafellar-Uryasev CVaR MILP (HiGHS) + labelled greedy fallback
  questions.py          10-variable VOI library + reviewed client-answer loop
  conversations.py      candidate assembly
  briefs.py             deterministic Why-How-What + claim compiler
  fixtures.py           full projection assembly
  repository.py         fixture / Delta / PostgreSQL repository interfaces
  api.py                additive /v3 routes
```

### New API surface

All modelled reads require `as_of`. `since` must not exceed `as_of`. Mutations
require an `Idempotency-Key` header and create immutable events.

```
GET  /v3/decision-twin
GET  /v3/clients/{id}/business-twin
GET  /v3/clients/{id}/business-graph
GET  /v3/clients/{id}/change-digest
GET  /v3/conversations
GET  /v3/conversations/{id}
GET  /v3/conversations/{id}/brief
GET  /v3/coverage-plan
GET  /v3/funding-routes/{id}
GET  /v3/models/v31-validation
POST /v3/scenarios/conversations/evaluate      (non-publishing)
POST /v3/questions/{id}/responses              (creates a pending E2 candidate)
POST /v3/feasibility/{id}/attestations
```

`/v1` and the existing `/v3` routes are unchanged. There is deliberately no
`/v3.1` route prefix.

---

## 5. Decision engineering

**Benefit** (governed weights, versioned `v31-policy-weights-3.1.0`):

```
Benefit = .25·Need + .20·ClientValue + .20·BankValue + .15·Timing
        + .10·RelationshipValue + .10·StrategicValue

AdjustedBenefit = Benefit × Feasibility × (1 − .50·Risk) × (1 − .35·Friction)
```

**Objective:** `0.45·E[AdjustedBenefit] + 0.55·CVaR₁₀%(AdjustedBenefit)`,
solved as a genuine MILP via `scipy.optimize.milp` (HiGHS) using the
Rockafellar-Uryasev linearisation.

**Robust dominance:** A dominates B when A is no worse on client value, bank
value, need and timing, and no worse on risk and friction, in ≥80% of shared
scenario draws with at least one strict improvement. Draws are common across
candidates, so comparisons are paired. Candidates with wider intervals get wider
draws, so an uncertain candidate cannot dominate a well-evidenced one by luck.

**Weekly constraints:** ≤8 conversations, ≤2 per client, ≤1 per client/role,
≤3 per solution family, ≤3 per sector, no mutually exclusive bundle, no failed
gate. Only client-frontier survivors enter the optimizer.

The legacy V3 `decision_score` is **not** used for V3.1 selection, and a test
asserts the two selections do not coincide.

---

## 6. Bank-production promotion gate

`NOT_PROMOTABLE`. The V2/V3 external gates remain open and V3.1 adds:

- bank approval of the business-domain ontology and stakeholder responsibility policy;
- approved rate cards for the eleven new solution families;
- empirical funding-route and problem-detection validation;
- finance-SME review of the outstanding pending public facts;
- E3 calibration wherever a wallet or share claim is required;
- live-provider adjudication, supervised RM usability pilot, randomized trial
  and thirty clean production-shadow days.

---

## 7. Not yet built (deferred to the next pass)

- Workbench rewrite (`dashboard/`) to the Monday-morning conversation experience.
- Delta table DDL and PostgreSQL operational schemas for the new products.
- MLflow registration entries for the new estimators and policies.
- Regenerated notebook, System Dossier, Technical Foundations, one-page PDF and
  judging deck.
- Sealed GenAI golden-set expansion for the new brief categories.

The analytical core, contracts, evidence base, API, events and test suite are
complete and reproducible today.
