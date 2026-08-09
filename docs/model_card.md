# Model card

## Intended use

Prioritise evidence-led discovery conversations for trained corporate-banking relationship teams. The system is a decision-support prototype and requires banker judgement.

## Out-of-scope use

Do not use it for credit approval, customer eligibility, automated pricing, revenue booking, employee performance management, market conduct decisions or unsupervised client outreach.

## Training and labels

There is no supervised training set. Product share is represented by declared hierarchical priors conditioned on transparent relationship signals. Timing uses a seasonal-naive baseline. Synthetic data tests calibration under the declared prior but does not validate that prior in the real world.

## Performance

The pipeline writes current temporal WAPE and synthetic P10–P90 recovery coverage to `outputs/validation.json`. Performance must be re-evaluated whenever source scope, assumptions or the as-of date changes.

## Key risks

- identification risk: bank share and total wallet are jointly unknown;
- pricing risk: basis-point economics are placeholders;
- coverage risk: audited public statements cover three showcases only and competitor transactions remain unavailable;
- translation risk: BHP and Glencore USD facts use a declared common point-rate translation, not audited ZAR restatements;
- anchor risk: accounting identities, FX turnover multiples and trade-utilisation ranges are proxies rather than observed bankable wallet totals;
- actionability risk: a high gap may still be unwinnable;
- bias risk: sector priors can favour products with higher assumed rates;
- leakage risk: future public facts must be gated by available date;
- narrative risk: an LLM may overstate inference without claim-level controls.

## Controls

Provenance tags, page-cited point-in-time facts, prior-only/anchored interval comparisons, explicit rate/prior sensitivity, partial-identification ranges, scenario sliders, P(top 10), deterministic fallback briefs, abstention, invariant tests, a governed audit workbook, versioned assumptions and human approval before action.

## Monitoring

Track input coverage, duplicate and missingness rates, feature drift, interval coverage where anchors become available, rank stability, banker overrides, action rate, outcome rate, unsupported-claim rate, citation precision/recall, latency P50/P95 and cost per accepted brief.
