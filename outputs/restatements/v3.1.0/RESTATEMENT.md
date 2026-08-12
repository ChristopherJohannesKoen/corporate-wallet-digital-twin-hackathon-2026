# Restatement V3.1.1-ANCHOR-APPROVAL

**Supersedes:** V3.1.0 · **Reason code:** `ANCHOR_ACTIVATED_WITHOUT_APPROVAL_CHECK`
**As-of:** 2026-06-30 · **Bank production status:** `NOT_PROMOTABLE` (unchanged, before and after)

This directory holds the superseded V3.1.0 artifacts exactly as they were published.
They are retained as historical evidence and are **not** regenerated. The live
surface is the V3.1.1 output at the repository root.

---

## 1. The defect

The system's central claim is that only approved evidence may move a published
number. It did not do that.

`src/wallet_twin_v2/public_evidence.py` correctly computed
`PublicAnchor.approval_status` from the facts behind each compiled anchor.
`src/wallet_twin_v2/fixtures.py` then copied only `low_zar`, `base_zar` and
`high_zar` out of that anchor and discarded the approval field. Tier was assigned
as:

```python
tier = EvidenceTier.E1 if anchor else EvidenceTier.E0   # existence, not approval
```

`PublicAnchor.approval_status` had **zero readers anywhere in the repository**.

Consequences in the superseded output:

- All **100** client-product cells were published as `E1` / `PUBLICLY_ANCHORED`.
- **51 facts that no finance SME had approved** were pooled into posterior wallet
  estimates at the E1 anchor weight.
- Every unapproved cell cited those facts in `evidence_fact_ids`, so a reader
  following the citation trail would have found pending evidence presented as the
  basis of a published estimate.
- `wallet_model.py` labelled the resulting bounds
  `basis="approved noisy measurement range"` — a label that was never true for 85
  of the 100 cells.

The same defect existed at client level: `evidence_tier` was `E1` for any client
holding *any* public fact, giving 20 E1 clients.

## 2. The correction

Activation is now a separate, governed gate
(`ANCHOR_ACTIVATION_POLICY_VERSION = public-anchor-activation-1.0.0`). A compiled
anchor may inform an estimate only when **every** fact behind it is `APPROVED`. A
single pending fact withholds the whole anchor and the cell falls back to the
prior-led path.

The rule is derived from fact state, never from a hard-coded entity list. When a
finance SME approves pending facts, the affected anchors activate on the next run
with no code change.

`AnchorDecision` cannot expose an `anchor_range` unless the decision is
`ACTIVATED`, and an `OpportunityView` validator rejects any cell that cites
anchoring evidence or claims `E1` without activation. Withheld evidence is
published in the new `pending_evidence_fact_ids` field rather than silently
dropped.

**Affected population: 100 cells assessed → 15 activated, 85 withheld.**
Activated clients: E01, E02, E09 — the three entities holding the 31 approved
seed facts. The 17 clients whose evidence is the 51 pending expanded facts are
prior-led.

## 3. Numeric effect

Measured against the superseded artifacts in this directory.

| Quantity | Effect |
|---|---|
| Cells assessed | 100, identical id set before and after |
| Cells changing rank | **95 / 100** |
| Absolute rank move | median **9.5**, p90 **24**, max **92** |
| Posterior wallet median change | p10 **−84.0%**, p50 **−47.2%**, p90 **+0.5%** |
| Cells whose wallet median fell | **75 / 100** |
| V2 top-8 overlap | **5 / 8** retained |
| V3 12-action portfolio overlap | **8 / 12** retained |
| V3.1 weekly coverage plan overlap | **6 / 8** retained |
| V3.1 MILP solver status | `OPTIMAL` → `OPTIMAL` |
| V3.0 boundary digests moved | **5 of 6** (`validation` unchanged) |
| Governance invariants moved | **0** |

The direction is expected and is the point: the withdrawn anchors were large
audited accounting figures that had been pulling posterior wallet upward. Removing
them from 85 cells lowers total wallet, lowers the contestable gap
`G = max(q*·T − A, 0)`, and lowers rank. The published portfolio was materially
inflated by evidence nobody had approved.

## 4. What did not change

`tests/regression/v3_0/test_v3_0_frozen_surface.py` asserts
`current["invariants"] == historical["invariants"]`, and it passes. The restatement
moved measured quantities and **no governance claim**:

- capacity, `causal_status`, `commercial_status`
- `measured_competitor_share_claims` = 0
- `causal_value_claims` = 0
- `bank_production_status` = `NOT_PROMOTABLE`

Cell counts are also unchanged (100 opportunities, 100 shadow reconstructions,
20 treasury graphs, 12 selected actions, 8 evidence requests). This is a
restatement of measurement, not a change of policy or scope.

## 5. Ranking is not simply ordered by evidence availability

A reasonable concern with a fail-closed evidence rule is that it degenerates into
"whoever has approved evidence wins". It does not. The 15 activated cells land at
ranks:

```
1, 2, 3, 4, 5, 11, 12, 14, 15, 22, 24, 30, 31, 35, 100
```

They are interleaved with prior-led cells throughout the table, and one activated
cell ranks last of 100. Observed activity and product economics continue to drive
the ranking; approved evidence sharpens the wallet estimate rather than
determining the order.

## 6. Sensitivity to the E1 anchor weight

`outputs/v2_validation/measurement_policy_sensitivity.json` sweeps the E1 pooling
weight across 0.20 / 0.35 / 0.50 under common random numbers.

The overall ordering is robust — Kendall's τ against the 0.35 baseline is **0.94**
at 0.20 and **0.98** at 0.50 — but the **top-8 selection is not invariant**:
6 of 8 members are retained at both 0.20 and 0.50, and one activated cell moves
63 ranks at 0.20.

Stated plainly: the E1 anchor weight materially affects which conversations reach
the weekly plan. **0.35 is therefore a parameter requiring product/model-risk
approval, not an implementation default.** It is now versioned as
`v2-wallet-measurement-policy-1.1.0`, and `docs/methodology.md` is generated from
that policy so the documented value cannot drift from the shipped one again — it
previously stated a V1-era 0.84 for the whole life of V2 and V3.

## 7. Was any decision taken on the superseded numbers?

No. `bank_production_status` was `NOT_PROMOTABLE` throughout, no recommendation was
ever released to a relationship manager (`EligibilityState.SHADOW_ONLY` on every
cell), and no client-facing communication was generated. The superseded figures
appeared only in the demonstration workbench and submission artifacts.

## 8. Contents of this directory

Captured from commit `65f6580` — the last commit before the correction.

```
contracts/openapi.json, contracts/openapi-v31.json
dashboard/app/data/{shadow,v3,v31}-fixture.json
outputs/v3/**              (decision lab, validation, 12 superseded briefs)
outputs/v31/**             (validation report, coverage plan, twins, estimates, claims)
outputs/v3_validation/v3_validation_report.json
outputs/judging_validation_manifest.json
tests/regression/v3_0/v3_0_frozen_surface.json
```

`scripts/build_submission.py` refuses to write anywhere under
`outputs/restatements/`.
