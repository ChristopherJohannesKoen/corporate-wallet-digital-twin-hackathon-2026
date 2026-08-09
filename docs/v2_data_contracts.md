# Data and interface controls

The authoritative machine-readable contracts are `contracts/openapi.json` and
`contracts/jsonschema`. Shared records distinguish E0–E4 evidence and
`OBSERVED`, `IDENTIFIED_BOUND`, `POSTERIOR`, `SCENARIO` and `CAUSAL` claims.

Every curated record carries business/source keys, event time, valid-from/to,
ingestion time, source hash, transformation version, quality state, owner and
entitlement domain. `Money` retains source unit and normalized value plus the FX
policy reference. `IntervalEstimate` retains nominal coverage, model version and
as-of time. Artifact references pin model, prompt, schema, rate-card, prior,
transformation and dataset versions.

Critical missing, stale, ambiguous or invalid fields are quarantined. They are
never replaced with production defaults. Restatements append a new valid-time
version and link to the superseded business key.

All modelled GETs require `as_of`. Events require identifiers, occurrence/as-of
times, assignment probability where applicable, evidence tier, estimates, rank,
reason codes, artifact versions, entitlement context and censoring state.
