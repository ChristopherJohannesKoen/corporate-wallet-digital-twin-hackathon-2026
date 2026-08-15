# Corporate Wallet Digital Twin V3.1.1 — superseded historical status

> **Superseded by V3.2.0.** This file preserves the V3.1.1 correction boundary
> for regression history. It is not a current release-status source. Current
> judging facts are generated in `data/v2/submission_truth_v3.2.0.json` and the
> V3.2 judging manifest.

**API major:** `/v3` · **as of:** 2026-06-30 · **team:** Corporate Wallet Digital Twin · **member:** Christopher Koen

## Release states

- **Hackathon:** `HACKATHON_SUBMISSION_BLOCKED_EXTERNAL_GATES` until at least
  three real provider-generated showcase briefs pass critical validation and the
  clean-history public mirror is published and anonymously verified.
- **Bank production:** `NOT_PROMOTABLE`.

These states are intentionally separate. Public evidence and simulations can
demonstrate the mechanics; they cannot close bank calibration, pricing, control
or outcome gates.

## Current canonical result

| Surface | V3.1.1 result | Interpretation |
|---|---:|---|
| Supplied history | 3,064,295 rows / 20 relationships | Confidential private-evaluator input |
| Wallet surface | 20 clients × five products = 100 cells | Five product quantities are not summed as banking spend |
| Active public anchors | 15 cells | Only approved facts activate anchors |
| Prior-led wallet cells | 85 cells | Pending facts are excluded |
| Source-fact estate | 82 = 31 approved + 51 pending | Derived typed claims are not extra audited observations |
| Measurement policy | E1=0.35 active | 0.20 and 0.50 are sensitivity arms; historical 0.84 retired |
| Decision layer | eight weekly conversations | Discovery actions under unknown bank feasibility |
| Business Twin | 20 × 12 components | “12-domain schema; unsupported domains remain explicit” |
| Solution layer | 320 governed evaluations | Available or fail-closed; no missing input silently defaults |
| GenAI adapters | OpenAI, Anthropic and Google | Historical V3.1.1 state; V3.2 records 8 accepted outputs from 9 target runs |
| Measured competitor share | 0 | E3 multibank observations absent |
| Causal incremental value | 0 / null | Qualified randomized RM outcomes absent |

## Governance correction in V3.1.1

V3.1.0 incorrectly allowed the public-evidence tier to appear active across all
100 opportunities. V3.1.1 makes approval authoritative:

1. `PENDING_REVIEW` facts are candidates, not active evidence.
2. `DEVELOPER_VERIFIED` records deterministic QA and does not confer approval.
3. Active anchors require finance-SME `APPROVED` status.
4. Exactly 15 cells across BHP, Glencore and Shoprite are E1 anchored.
5. The other 85 cells use E0 governed priors and explicitly invite discovery.
6. V3.1.0 affected outputs are archived as historical, non-canonical
   restatements; the immutable submission boundary is V3.1.1.

## Wallet product surface

The default workbench is **Wallet Portfolio**, not Decision Lab. It provides a
20×5 heatmap with toggles for:

- observed Syn Bank activity `A`;
- posterior total wallet `T`;
- estimated Syn Bank share `q`;
- contestable gap `G=max(q*·T−A,0)`;
- scenario contribution; and
- evidence/approval state.

Each cell exposes `A`, `T P10/P50/P90`, `q P10/P50/P90`, target-share scenario
`q*`, `G`, claim class, tier, active and pending fact IDs, artifact versions,
timing, action permitted now and conditional commercial action.

FX is an exposure proxy. Liquidity is a liquidity-flow opportunity proxy. Share
is posterior, not measured competitor share.

## Sensitivity conclusion

The 10,000-draw correlated global benchmark reports Trade Finance:

- first-ranked frequency: 100%;
- mean top-ten share: 55.7%;
- majority-dominance frequency: 87.75%; and
- absolute economics as a distribution, not a fixed winner condition.

Under the separate E1 weight sweep at 0.20 / 0.35 / 0.50, Trade Finance remains
first, while its top-ten share falls 70% / 60% / 30% and majority dominance is
true / true / false. That is the desired conclusion: first rank is robust in the
representative benchmark; portfolio dominance is sensitive and must be rerun
with approved bank inputs and E3 evidence.

## GenAI status

The provider gateway, exact-model resolution, sanitized closed packs, structured
schema, deterministic validators, citation/number checks, prompt-injection tests
and fallback are implemented. BHP, Glencore and Shoprite each have a
deterministic brief. The later V3.2 artifact records 8 accepted genuine provider
outputs from 9 targets and retains fallback for the one rejected output.

The comparative report contains nine target rows:

- OpenAI `gpt-5.6-sol` × three clients;
- Anthropic `claude-sonnet-5` × three clients;
- Google `gemini-3.6-flash` × three clients.

Fresh rotated credentials, exact model availability, provider approval flags
and explicit public-only acknowledgement are required to rerun the comparison.
The accepted V3.2 result is hackathon evidence, not bank-authorized LIVE_GENAI.
Previously pasted credentials are treated as compromised and must not be reused.

## Submission artifacts

The canonical writer is:

```text
python scripts/build_submission.py
```

It exports contracts, runs evidence/model/GenAI checks, executes the notebook,
builds and verifies the workbook, one-page PDF and ten-slide PowerPoint, hashes
the artifacts and emits `outputs/judging_manifest_v3.1.1.json`.

Legacy builders and `freeze_v3_regression.py` are not part of normal
reproduction. Only the canonical builder may write final judging deliverables.

## Bank-production open gates

- Representative E3 multibank calibration panel.
- Bank-approved pricing, FTP, liquidity, capital, expected loss, risk, cost and
  hurdle inputs.
- Bank AWS/Databricks, SSO, Unity Catalog, SIEM and independent security approval.
- Finance-SME approval of any pending fact intended for active inference.
- Approved live-provider adjudication.
- Supervised real RM pilot, randomized trial and qualified outcome history.
- Thirty clean production-shadow days.

No hackathon artifact may imply that these gates have been closed.
