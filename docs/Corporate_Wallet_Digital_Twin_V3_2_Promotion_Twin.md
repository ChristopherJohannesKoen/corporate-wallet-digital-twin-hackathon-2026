# Corporate Wallet Digital Twin V3.2 — Promotion Readiness Twin

**Version 3.2.0 · API major `/v3` · Bank production status: `NOT_PROMOTABLE`**

---

## 1. The question V3.2 answers

V3.1.1 answers *what should the banker do?* It produces a wallet estimate, a
ranked coverage plan, and a conversation brief with its evidence trail.

It has no way to express a different question, which is the one a bank actually
asks first:

> **Is this system allowed to be used, and for what?**

That question has no representation anywhere in V1–V3.1. There is a
`bank_production_status` string, a list of open external gates, and a release
report — but no object that says which gates exist, who owns them, what evidence
would satisfy them, what breaks if they are not satisfied, and what the system
may therefore be used for today.

V3.2 adds that object.

---

## 2. Five states, and why they cannot be skipped

```
OFFLINE_CANDIDATE → SHADOW_READY → PILOT_READY → SCALE_READY → CAUSAL_CHAMPION
```

| State | What it licenses |
|---|---|
| `OFFLINE_CANDIDATE` | Offline analysis on governed history; synthetic demonstration |
| `SHADOW_READY` | Scoring live bank flow with nothing reaching a banker |
| `PILOT_READY` | Output shown to a named, supervised RM cohort |
| `SCALE_READY` | Output shown to RMs as part of ordinary work |
| `CAUSAL_CHAMPION` | Claiming the system *caused* incremental revenue |

The state is **recomputed from verified evidence and exact decision-bound
approvals on every read**, never treated as an authorization merely because a
score is high. The walk stops at the first transition whose blocking gates are
not all satisfied or whose four-eyes approval is absent. Passing a later
transition while an earlier one fails advances nothing, and a state cannot
survive the expiry or withdrawal of the evidence behind it.

---

## 3. Two tracks, and why disagreement is the point

Every gate is evaluated twice.

- **REAL** governs actual bank authorisation.
- **REHEARSAL** proves the promotion machinery works.

A rehearsal in which every gate passes demonstrates that the apparatus
functions. It demonstrates *nothing whatever* about whether a bank has approved
anything. Conflating the two would be the single most consequential
misrepresentation this system could make, so the separation is enforced four
times over, deliberately redundantly:

1. **Type** — `DecisionTrack` is an enum, not a boolean, so it cannot be
   inverted by a falsy value.
2. **Mode algebra** — `admits_track()` refuses `SYNTHETIC_REHEARSAL` on the real
   track. There is no override flag.
3. **Storage** — a Postgres `CHECK` constraint restates it, because a `psql`
   session does not go through the Python contracts.
4. **Signature** — the trust registry binds each key to the modes it may sign,
   and the mode lives *inside* the signed payload, so tampering with it
   invalidates the signature.

---

## 4. Two scores, never one

| Score | Track | Synthetic evidence |
|---|---|---|
| **PMR** — Promotion Machinery Readiness | Rehearsal | counts fully |
| **BER** — Bank Evidence Readiness | Real | contributes **zero** |

At V3.2 release: **PMR = 100%, BER = 0%.**

There is deliberately no third number. A composite would let a PMR near 1.0 pull
a BER of 0.0 up to a comfortable-looking middle, and a reader skimming one figure
would conclude the system is halfway to production when the bank has authorised
nothing at all. **The two numbers disagreeing is the finding** — averaging them
destroys it.

`assert_no_composite_score()` enforces this mechanically in the scoring module,
the workbench fixture exporter and the submission build; a dashboard test
enforces it in the view. It cannot be reintroduced in any single layer.

`synthetic_weight_excluded_from_ber` publishes the gap explicitly, turning "BER
is low" into "here is precisely how much of this readiness is simulated".

---

## 5. Capability is not a function of state

Reaching `SHADOW_READY` means the system is operationally sound enough to score
live flow. It says nothing about whether competitor share can be *measured*.
Tying capability to state alone would let operational maturity silently license
an analytical claim no operational gate examines.

| Missing | Disables | Leaves intact |
|---|---|---|
| E3 multibank observation | `MEASURED_SHARE` | hidden shadow scoring and posterior wallet |
| Bank-approved economics | real `SCENARIO_ECONOMICS` and `PRODUCT_PROPOSAL` | discovery conversations |
| Randomised trial / weak first stage | `CAUSAL_VALUE` | `SCALE_READY` non-causal decision support |

`AUTONOMOUS_CLIENT_ACTION` is **permanently withheld** at every state and any
evidence. It is not "not yet reached"; it is outside what this system is for.

A null trial result leaves the system `SCALE_READY`. The honest outcome of a
trial that found nothing is a null result, not a demotion and not a champion.

---

## 6. The gate catalogue

**30 gates across 4 transitions**, as governed data generated from the same
catalogue the engine evaluates — so the published policy and the enforced policy
cannot drift apart.

This replaced three broken things:

- `ShadowReleaseGate` hardcoded twenty checks in one method with string
  thresholds, no evidence binding, no owner and no statement of what failure
  costs. It could compute a verdict; it could not explain one.
- `config/mlflow_promotion_policy.json` formerly declared gate ids for two
  transitions and **no code parsed it**. V3.2 now generates the enforced
  five-state policy from the catalogue; MLflow records its artifacts but never
  authorises a transition.
- The two vocabularies named identical requirements differently
  (`interval-coverage-90` vs `90pct_coverage_between_85pct_and_95pct`). 38 legacy
  aliases are preserved so earlier artifacts remain traceable.

Each gate carries: severity (CRITICAL 5 / HIGH 3 / STANDARD 1), whether it
blocks, the requirement, **what breaks if it fails**, the minimum admissible
real-track evidence mode, owner and approver roles, freshness, and **what would
make the real gate pass**. That last field is what a reviewer acts on — a red
cell with no next action is a complaint, not a control.

---

## 7. Accelerated shadow rehearsal

The V2 `thirty_day_shadow_rehearsal` looped thirty times with every field set to
`passed`. Every day was clean by construction, so it could not fail and
therefore established nothing. A rehearsal whose only possible outcome is success
is a constant, not a test.

The replacement runs on a virtual clock and **does** fail:

```
days 1–16   clean
day 17      critical reconciliation failure → clean-day counter resets to 0
days 18–47  clean → 30 consecutive clean days
```

Forty-seven simulated days to reach thirty clean ones. A run that counted
straight to thirty would publish the same headline number while proving far less;
**the reset is what shows the counter is a control rather than a loop bound**.

Ten ordered daily steps; a failed day stops at the broken step. Seven negative
scenarios, each run in isolation and each required to break its own named gate.

`VirtualClock` has **no** `elapsed_bank_shadow_days` field, no method that
increments one, and no parameter that sets one. A counter a simulation could
advance is one it eventually does.

> **`shadow_rehearsal_days = 30` and `elapsed_bank_shadow_days = 0` are published
> together everywhere.** The second is what keeps the first honest.

---

## 8. Signing and trust

`rfc8785.py` is deliberately **separate** from `canonical.py`. That module rounds
floats to the published precision and emits indented JSON — correct for
byte-reproducible artifacts, and disqualifying for a signature, because signing a
rounded payload signs a different number than the one published.

Two conformance details that would have produced signatures a conforming verifier
rejects, with no visible cause:

- **Number form.** Python's `repr` and ECMAScript's `Number::toString` are both
  shortest-round-trip but disagree twice: `100.0` vs `100`, and the exponential
  threshold at 1e16 vs 1e21.
- **Key order.** JCS sorts by UTF-16 code unit; Python sorts by code point. They
  differ for supplementary characters — U+1F600 sorts *before* U+FB00 under
  UTF-16 and after under code point.

| Signer | Signs | Exercised here? |
|---|---|---|
| `LocalECDSASigner` | rehearsal only | **yes**, fully in CI |
| `SigstoreSigner` | rehearsal, public package | no — needs GitHub OIDC |
| `KMSSigner` | real bank, attested | no — needs live AWS + a new ECDSA key |

Both unavailable signers **raise rather than returning plausible bytes**, and
`v32_signing_posture.json` publishes
`NO_REAL_BANK_SIGNING_CAPABILITY_ON_THIS_BUILD` so three listed signers cannot be
read as three exercised ones.

Promotion decisions use the same canonicalization and DSSE-style envelope as
gate evidence. An approval records both `decision_id` and the SHA-256 digest of
the exact RFC 8785 decision payload. The repository rejects a stale decision id
or a mismatched digest, and approval events repeat both fields for audit. A
later recalculation therefore cannot inherit approval granted to an earlier
decision. The fixture decision is signed only by the local rehearsal trust
domain and explicitly records `bank_authority_conferred=false`.

The existing Terraform KMS key is **RSA-3072**, not the `ECDSA_SHA_256` this
signer needs; a second key resource is required.
`production_adapters.KMSManifestSigner` also has `sign()` but no `verify()`, and
verification is the half that matters — signing alone proves only that an API
call succeeded.

---

## 9. Nine simulation laboratories

Each states in its own report what it does **not** establish. Two produced
findings worth recording rather than tuning away:

- **E3 sample-size planner** returns `NOT_DETERMINED_UP_TO_150`. At 150 observed
  clients the posterior half-width is still above the 0.05 target, so no tested
  n qualifies. Returning 150 would tell the bank to buy a data contract this
  analysis says would not work.
- **Causal operating characteristics**: Type I error controlled at nominal (0.03,
  Wilson [0.014, 0.064]) but **power at the target effect is 0.20**. The design
  is reported `UNDERPOWERED_AT_THIS_CLUSTER_COUNT`, and a null result from it
  would mean "we do not know", not "there is no effect".

**RM persona simulator**: 5 personas × 8 tasks. Every session carries
`real_participant=False` as a non-init field — a parameter that could be flipped
to `True` is one that eventually is. No simulated session can satisfy the
supervised-pilot gate.

**Compute split**: canonical tiers run on CPU because their artifacts are
byte-gated and must reproduce on a GPU-less CI runner; nightly tiers may use the
GPU because they publish a statistical summary rather than a fixture. **No
committed number depends on the GPU path.** With CuPy absent the nightly tiers
report `NOT_EXECUTED` rather than silently running at canonical size and
publishing a precision never achieved.

---

## 10. Bank-shaped lab, and what wiring OPA found

`WALLET_OPA_URL` was configured, validated, and **never called**. Every
authorisation decision was computed in-process; the policy engine was
documentation, not a control.

Putting OPA in the request path found three entitlement gaps that had been live
the whole time, none of which any existing test could have caught, because
catching them requires two policies to compare:

1. The Rego did a literal membership test and so **did not honour the `"*"`
   wildcard** the in-process ABAC has always honoured. With OPA at the gateway,
   every administrator would have been locked out.
2. The in-process policy **never checked region at all**. A principal entitled to
   a client in one region could read that client from any other.
3. Evidence approval required only `owns_client`, so a reviewer could **approve a
   fact about a product or region they could not see**.

The third came from a combinatorial sweep of **4,860 principal/request pairs**
that found 96 divergences after the first two were fixed. All three lived in
combinations nobody had thought to write down, which is why the matrix is
generated rather than curated. All 4,860 now agree, and CI asserts the divergence
log is empty.

The gateway **denies on disagreement** rather than preferring either side. Two
policies drifting apart silently is the failure this arrangement is most likely
to produce; denying turns a silent drift into a loud one. An unreachable OPA
raises rather than allowing — an authorisation service that fails open is worse
than none, because it looks like one.

**MinIO object lock** is new. No bucket creation step existed, so every
"immutable evidence" claim rested on a bucket nobody had created with a retention
mode nobody had set. Object lock can only be enabled *at bucket creation*, and a
bucket created without it looks identical in every listing. The bootstrap
verifies its own work: it writes an object to a locked bucket and confirms
permanent deletion is refused (`WORM protected and cannot be overwritten`), with
the unlocked bucket confirming the probe is not vacuous.

---

## 11. The honest release position

```
HACKATHON_SUBMISSION_BLOCKED_EXTERNAL_GATES
OFFLINE_CANDIDATE_VALIDATED
SHADOW_PROMOTION_REHEARSAL_PASSED
SHADOW_DEPLOYMENT_PACKAGE_READY

BANK_SHADOW_AUTHORIZED  = FALSE
PILOT_READY             = FALSE
SCALE_READY             = FALSE
CAUSAL_CHAMPION         = FALSE

PMR = 100%   BER = 0%
shadow_rehearsal_days = 30   elapsed_bank_shadow_days = 0
BANK_PRODUCTION_STATUS = NOT_PROMOTABLE
```

### What V3.2 does not establish

- No E3 multibank observation. Competitor share remains unmeasurable, and
  `MEASURED_SHARE_REPORTING` is refused.
- No bank-approved economics beyond the five legacy rate cards. No money value
  may be attached to an opportunity.
- Eight of nine external-provider outputs are accepted in the committed
  hackathon evidence, with all three providers and showcase clients covered.
  This does not establish the bank live-provider gate: provider approval, contracting, residency,
  bank-controlled credentials or independent finance-SME adjudication.
- No elapsed bank shadow day. Thirty *simulated* days are not one bank day.
- No real RM session. Adoption is zero and the fixture cannot change that.
- No trial. Causal value is null.
- No real-bank signing capability on this build.

Every one of those is a gate in the catalogue, with an owner, an approver, and a
statement of what would satisfy it. That is the whole point: the system does not
merely decline to overclaim, it says precisely what it would take to claim more.
