# Supervised pilot and causal protocol

After shadow approval, a feature flag exposes a small entitled RM cohort with
mandatory feedback and no automated client contact, price, credit, booking or
pipeline-stage action. The supervised phase measures verification time,
actionability, comprehension, omissions, overrides and operational incidents.
The implemented `/v1/pilot/sessions`, session-feedback and readiness endpoints
hash the consent reference and refuse to count fixture sessions as adoption.
Five completed real-participant sessions are the minimum readiness threshold;
this is a workflow gate, not evidence that adoption has occurred.

The later trial randomizes encouragement by RM portfolio/team to reduce
contamination. Eligibility is logged before assignment, including undisplayed
opportunities. Treatment, primary outcome, horizons, exclusions, censoring and
analysis are locked in a hashed pre-registration manifest. The primary outcome is qualified RM action within
the agreed horizon; intention-to-treat is primary. Treatment-on-treated is
allowed only with a valid documented instrument.

The production analyzer reports cluster-robust ITT, randomization inference,
covariate balance, censoring, first stage and a weak-instrument gate. A Wald
treatment-on-treated estimate is withheld when the first stage is below 0.10.
Heterogeneous effects and doubly robust policy evaluation require overlap,
effective sample size and independent validation. Until then the interface and
API prohibit the labels “uplift” and “causal expected incremental value.”
