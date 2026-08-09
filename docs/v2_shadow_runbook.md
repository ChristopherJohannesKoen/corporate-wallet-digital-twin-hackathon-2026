# Controlled shadow runbook

1. Freeze a point-in-time source manifest and verify source hashes.
2. Reconcile all critical feeds; quarantine failures and stop dependent outputs.
3. Materialize entitled features and register dataset/transformation versions.
4. Run bounds, posterior, timing, economics and sensitivity jobs.
5. Reject commercial output with any missing, stale, unapproved or unreconciled rate.
6. Generate recommendations for validation only; do not emit RM-visible exposure.
7. Persist eligibility—including undisplayed cases—assignment probability,
   evidence, rank, artifacts, entitlement and censoring state.
8. Reconcile commercial totals to approved finance/management information.
9. Evaluate all release gates and publish the signed validation report.
10. Maintain shadow operation for at least 30 consecutive clean days.

Rollback is version-based: restore the last approved model, prior,
transformation, prompt, schema, rate card and application digest; do not mutate
history. Any Sev-1/Sev-2, entitlement breach, critical unsupported claim,
point-in-time leakage or material reconciliation failure resets the clean-day
clock and blocks promotion.

RPO is one hour and RTO four hours unless bank policy is stricter. Daily refresh
must complete by 06:00 SAST, P95 reads stay below 750 ms, event ingestion below
five minutes and monthly availability at least 99.9%.
