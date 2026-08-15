CREATE SCHEMA IF NOT EXISTS wallet_twin.raw;
CREATE SCHEMA IF NOT EXISTS wallet_twin.conformed;
CREATE SCHEMA IF NOT EXISTS wallet_twin.training;
CREATE SCHEMA IF NOT EXISTS wallet_twin.registry;
CREATE SCHEMA IF NOT EXISTS wallet_twin.features;
CREATE SCHEMA IF NOT EXISTS wallet_twin.curated;
CREATE SCHEMA IF NOT EXISTS wallet_twin.monitoring;
CREATE SCHEMA IF NOT EXISTS wallet_twin.governance;

-- V3 decision-intelligence products are point-in-time and append-only. Draws
-- remain reproducible from their seed, policy, source snapshot and model refs.
CREATE TABLE IF NOT EXISTS wallet_twin.features.shadow_wallet_draw (
  reconstruction_id STRING NOT NULL,
  draw_id BIGINT NOT NULL,
  as_of DATE NOT NULL,
  client_id STRING NOT NULL,
  product STRING NOT NULL,
  latent_wallet_amount DECIMAL(38,9) NOT NULL,
  focal_bank_share DOUBLE NOT NULL,
  measurement_status STRING NOT NULL,
  evidence_tier STRING NOT NULL,
  model_version STRING NOT NULL,
  transport_policy_version STRING NOT NULL,
  random_seed BIGINT NOT NULL,
  source_snapshot_hash STRING NOT NULL,
  available_date DATE NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.features.shadow_wallet_edge (
  reconstruction_id STRING NOT NULL,
  edge_id STRING NOT NULL,
  as_of DATE NOT NULL,
  client_id STRING NOT NULL,
  product STRING NOT NULL,
  provider_node_id STRING NOT NULL,
  provider_is_anonymous BOOLEAN NOT NULL,
  flow_amount DECIMAL(38,9) NOT NULL,
  transport_cost DOUBLE NOT NULL,
  regularization DOUBLE NOT NULL,
  marginal_residual DOUBLE NOT NULL,
  model_version STRING NOT NULL,
  source_snapshot_hash STRING NOT NULL,
  available_date DATE NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.features.product_need_estimate (
  estimate_id STRING NOT NULL,
  as_of DATE NOT NULL,
  client_id STRING NOT NULL,
  product STRING NOT NULL,
  lower DOUBLE NOT NULL,
  median DOUBLE NOT NULL,
  upper DOUBLE NOT NULL,
  positive_unlabelled_probability DOUBLE NOT NULL,
  selection_mechanism STRING NOT NULL,
  class_prior DOUBLE NOT NULL,
  model_version STRING NOT NULL,
  measurement_status STRING NOT NULL,
  available_date DATE NOT NULL,
  source_snapshot_hash STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.features.change_point_state (
  state_id STRING NOT NULL,
  as_of DATE NOT NULL,
  client_id STRING NOT NULL,
  product STRING NOT NULL,
  run_length INT NOT NULL,
  change_probability DOUBLE NOT NULL,
  hazard_configuration_version STRING NOT NULL,
  baseline_version STRING NOT NULL,
  model_version STRING NOT NULL,
  source_snapshot_hash STRING NOT NULL,
  available_date DATE NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.monitoring.leakage_alarm (
  alarm_id STRING NOT NULL,
  as_of DATE NOT NULL,
  client_id STRING NOT NULL,
  product STRING NOT NULL,
  severity STRING NOT NULL,
  leakage_probability DOUBLE NOT NULL,
  change_probability DOUBLE NOT NULL,
  threshold_policy_version STRING NOT NULL,
  reason_codes ARRAY<STRING> NOT NULL,
  status STRING NOT NULL,
  published_at TIMESTAMP NOT NULL,
  source_snapshot_hash STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.features.treasury_graph_snapshot (
  graph_id STRING NOT NULL,
  as_of DATE NOT NULL,
  client_id STRING NOT NULL,
  graph_version STRING NOT NULL,
  node_count INT NOT NULL,
  edge_count INT NOT NULL,
  concentration_index DOUBLE NOT NULL,
  graph_payload VARIANT NOT NULL,
  source_snapshot_hash STRING NOT NULL,
  available_date DATE NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.curated.portfolio_scenario (
  scenario_id STRING NOT NULL,
  as_of DATE NOT NULL,
  scenario_index INT NOT NULL,
  policy_version STRING NOT NULL,
  random_seed BIGINT NOT NULL,
  scenario_probability DOUBLE NOT NULL,
  opportunity_values VARIANT NOT NULL,
  source_snapshot_hash STRING NOT NULL,
  available_date DATE NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.curated.portfolio_selection (
  selection_id STRING NOT NULL,
  as_of DATE NOT NULL,
  opportunity_id STRING NOT NULL,
  client_id STRING NOT NULL,
  product STRING NOT NULL,
  selected BOOLEAN NOT NULL,
  expected_value DECIMAL(38,9) NOT NULL,
  value_at_risk DECIMAL(38,9) NOT NULL,
  conditional_value_at_risk DECIMAL(38,9) NOT NULL,
  marginal_capacity_cost DECIMAL(38,9) NOT NULL,
  constraint_reason_codes ARRAY<STRING> NOT NULL,
  policy_version STRING NOT NULL,
  source_snapshot_hash STRING NOT NULL,
  selected_at TIMESTAMP NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.curated.evidence_acquisition_plan (
  plan_id STRING NOT NULL,
  candidate_id STRING NOT NULL,
  as_of DATE NOT NULL,
  client_id STRING NOT NULL,
  product STRING,
  fact_concept STRING NOT NULL,
  acquisition_cost DECIMAL(38,9) NOT NULL,
  expected_value_of_information DECIMAL(38,9) NOT NULL,
  expected_net_value_of_information DECIMAL(38,9) NOT NULL,
  selected BOOLEAN NOT NULL,
  approval_status STRING NOT NULL,
  policy_version STRING NOT NULL,
  source_snapshot_hash STRING NOT NULL,
  available_date DATE NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.curated.client_product_activity (
  activity_id STRING NOT NULL,
  client_id STRING NOT NULL,
  client_region STRING NOT NULL,
  legal_entity_id STRING NOT NULL,
  product STRING NOT NULL,
  activity_type STRING NOT NULL,
  event_time TIMESTAMP NOT NULL,
  as_of DATE NOT NULL,
  amount DECIMAL(38,9) NOT NULL,
  currency STRING NOT NULL,
  source_hash STRING NOT NULL,
  transformation_version STRING NOT NULL,
  quality_status STRING NOT NULL,
  entitlement_domain STRING NOT NULL,
  available_date DATE NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.training.multibank_calibration_observation (
  observation_id STRING NOT NULL,
  client_id STRING NOT NULL,
  client_region STRING NOT NULL,
  product STRING NOT NULL,
  sector STRING NOT NULL,
  focal_bank_activity DECIMAL(38,9) NOT NULL,
  other_bank_activity DECIMAL(38,9) NOT NULL,
  total_multibank_wallet DECIMAL(38,9) NOT NULL,
  measured_share DOUBLE NOT NULL,
  selection_probability DOUBLE NOT NULL,
  selection_weight DOUBLE NOT NULL,
  observation_period_start DATE NOT NULL,
  observation_period_end DATE NOT NULL,
  available_date DATE NOT NULL,
  consent_reference STRING NOT NULL,
  reconciliation_status STRING NOT NULL,
  evidence_tier STRING NOT NULL,
  source_hash STRING NOT NULL,
  dataset_version STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.curated.effective_rate_card (
  rate_card_id STRING NOT NULL,
  version STRING NOT NULL,
  product STRING NOT NULL,
  legal_entity_id STRING NOT NULL,
  segment STRING NOT NULL,
  currency STRING NOT NULL,
  effective_from DATE NOT NULL,
  effective_to DATE NOT NULL,
  gross_price_bps DECIMAL(38,9) NOT NULL,
  ftp_bps DECIMAL(38,9) NOT NULL,
  liquidity_bps DECIMAL(38,9) NOT NULL,
  expected_loss_bps DECIMAL(38,9) NOT NULL,
  capital_bps DECIMAL(38,9) NOT NULL,
  total_cost_bps DECIMAL(38,9) NOT NULL,
  hurdle_bps DECIMAL(38,9) NOT NULL,
  approval_status STRING NOT NULL,
  reconciliation_status STRING NOT NULL,
  owner STRING NOT NULL,
  source_hash STRING NOT NULL,
  available_date DATE NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.curated.recommendation_event (
  event_id STRING NOT NULL,
  event_type STRING NOT NULL,
  occurred_at TIMESTAMP NOT NULL,
  as_of DATE NOT NULL,
  client_id STRING NOT NULL,
  client_region STRING NOT NULL,
  product STRING NOT NULL,
  rm_id STRING,
  team_id STRING,
  assignment_arm STRING,
  assignment_probability DOUBLE,
  evidence_tier STRING,
  rank INT,
  reason_codes ARRAY<STRING> NOT NULL,
  artifact_versions VARIANT NOT NULL,
  entitlement_context VARIANT NOT NULL,
  censor_date DATE,
  source_hash STRING NOT NULL,
  available_date DATE NOT NULL
) USING DELTA
TBLPROPERTIES (
  'delta.enableChangeDataFeed' = 'true',
  'delta.appendOnly' = 'true',
  'wallet_entitled' = 'true'
);

CREATE TABLE IF NOT EXISTS wallet_twin.registry.promotion_decision (
  artifact_id STRING NOT NULL,
  artifact_type STRING NOT NULL,
  artifact_version STRING NOT NULL,
  evaluated_at TIMESTAMP NOT NULL,
  environment STRING NOT NULL,
  decision STRING NOT NULL,
  gate_results VARIANT NOT NULL,
  approver STRING,
  signature STRING,
  source_hash STRING NOT NULL
) USING DELTA
TBLPROPERTIES ('delta.appendOnly' = 'true');

-- V3.1 Corporate Banking Decision Twin data products. The projection tables
-- are append-only and carry their full point-in-time and entitlement boundary.
CREATE TABLE IF NOT EXISTS wallet_twin.curated.business_twin_component (
  snapshot_id STRING NOT NULL, as_of DATE NOT NULL, client_id STRING NOT NULL,
  legal_entity_ids ARRAY<STRING> NOT NULL, domain STRING NOT NULL, status STRING NOT NULL,
  payload VARIANT NOT NULL, claim_ids ARRAY<STRING> NOT NULL,
  event_time TIMESTAMP, valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, transformation_version STRING NOT NULL,
  owner STRING NOT NULL, quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.features.business_indicator (
  indicator_id STRING NOT NULL, snapshot_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, indicator_type STRING NOT NULL, interval VARIANT,
  formula STRING NOT NULL, inputs VARIANT NOT NULL, missing_inputs ARRAY<STRING> NOT NULL,
  evidence_ids ARRAY<STRING> NOT NULL, valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, transformation_version STRING NOT NULL,
  owner STRING NOT NULL, quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.business_graph_node (
  graph_id STRING NOT NULL, node_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, node_type STRING NOT NULL, label STRING NOT NULL,
  properties VARIANT NOT NULL, claim_class STRING NOT NULL, evidence_tier STRING NOT NULL,
  approval_status STRING NOT NULL, valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, transformation_version STRING NOT NULL,
  owner STRING NOT NULL, quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.business_graph_edge (
  graph_id STRING NOT NULL, edge_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, from_node_id STRING NOT NULL, to_node_id STRING NOT NULL,
  edge_type STRING NOT NULL, direction STRING NOT NULL, claim_ids ARRAY<STRING> NOT NULL,
  claim_class STRING NOT NULL, evidence_tier STRING NOT NULL, approval_status STRING NOT NULL,
  review_state STRING NOT NULL, valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, transformation_version STRING NOT NULL,
  owner STRING NOT NULL, quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.business_event (
  event_id STRING NOT NULL, as_of DATE NOT NULL, client_id STRING NOT NULL,
  event_type STRING NOT NULL, event_time TIMESTAMP NOT NULL, publication_time TIMESTAMP NOT NULL,
  event_window_start DATE, event_window_end DATE, payload VARIANT NOT NULL,
  claim_ids ARRAY<STRING> NOT NULL, valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, transformation_version STRING NOT NULL,
  owner STRING NOT NULL, quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.features.problem_hypothesis (
  problem_id STRING NOT NULL, snapshot_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, problem_type STRING NOT NULL, intensity_interval VARIANT NOT NULL,
  identification_status STRING NOT NULL, commercially_eligible BOOLEAN NOT NULL,
  positive_evidence_ids ARRAY<STRING> NOT NULL, counter_evidence_ids ARRAY<STRING> NOT NULL,
  reason_codes ARRAY<STRING> NOT NULL, policy_version STRING NOT NULL,
  model_version STRING, valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, owner STRING NOT NULL, quality_status STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.features.stakeholder_resolution (
  resolution_id STRING NOT NULL, as_of DATE NOT NULL, client_id STRING NOT NULL,
  problem_id STRING NOT NULL, primary_role STRING NOT NULL, secondary_roles ARRAY<STRING> NOT NULL,
  role_weights VARIANT NOT NULL, rationale STRING NOT NULL, rm_confirmation_required BOOLEAN NOT NULL,
  named_contact_status STRING NOT NULL, policy_version STRING NOT NULL,
  valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP, ingestion_time TIMESTAMP NOT NULL,
  available_date DATE NOT NULL, source_hash STRING NOT NULL, owner STRING NOT NULL,
  quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.features.client_solution_estimate (
  estimate_id STRING NOT NULL, as_of DATE NOT NULL, client_id STRING NOT NULL,
  solution STRING NOT NULL, claim_class STRING NOT NULL, status STRING NOT NULL,
  need_interval VARIANT, amount_interval VARIANT, timing VARIANT,
  fail_closed_reasons ARRAY<STRING> NOT NULL, artifact_versions VARIANT NOT NULL,
  valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP, ingestion_time TIMESTAMP NOT NULL,
  available_date DATE NOT NULL, source_hash STRING NOT NULL, owner STRING NOT NULL,
  quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.features.funding_route_estimate (
  projection_id STRING NOT NULL, as_of DATE NOT NULL, client_id STRING NOT NULL,
  funding_requirement VARIANT, route_probabilities VARIANT NOT NULL,
  exposed_inputs VARIANT NOT NULL, scorecard_version STRING NOT NULL,
  challenger_status STRING NOT NULL, valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, owner STRING NOT NULL, quality_status STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.client_value_component (
  component_id STRING NOT NULL, conversation_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, component_type STRING NOT NULL, value_status STRING NOT NULL,
  value_interval VARIANT, currency STRING, qualitative_value STRING,
  formula STRING, assumptions ARRAY<STRING> NOT NULL, evidence_ids ARRAY<STRING> NOT NULL,
  policy_version STRING NOT NULL, ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, owner STRING NOT NULL, quality_status STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.bank_value_component (
  component_id STRING NOT NULL, conversation_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, value_type STRING NOT NULL, value_status STRING NOT NULL,
  direct_value_interval VARIANT, relationship_value_interval VARIANT,
  causal_value_interval VARIANT, rate_card_version STRING, cost_to_win_version STRING,
  assumptions ARRAY<STRING> NOT NULL, ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, owner STRING NOT NULL, quality_status STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.feasibility_assessment (
  assessment_id STRING NOT NULL, conversation_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, gate_results VARIANT NOT NULL, blocked BOOLEAN NOT NULL,
  permitted_action STRING NOT NULL, risk_score DOUBLE NOT NULL, friction_score DOUBLE NOT NULL,
  policy_version STRING NOT NULL, attestation_refs ARRAY<STRING> NOT NULL,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, owner STRING NOT NULL, quality_status STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.conversation_candidate (
  conversation_id STRING NOT NULL, snapshot_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, legal_entity_ids ARRAY<STRING> NOT NULL,
  stakeholder_role STRING NOT NULL, problem_id STRING NOT NULL, solution_bundle_id STRING NOT NULL,
  engagement_window VARIANT NOT NULL, eligibility STRING NOT NULL, action STRING NOT NULL,
  explanation_path_id STRING, artifact_versions VARIANT NOT NULL,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, owner STRING NOT NULL, quality_status STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.pareto_frontier_result (
  result_id STRING NOT NULL, as_of DATE NOT NULL, client_id STRING NOT NULL,
  conversation_id STRING NOT NULL, frontier_type STRING NOT NULL,
  membership_probability DOUBLE NOT NULL, dominance_threshold DOUBLE NOT NULL,
  dominated_by ARRAY<STRING> NOT NULL, policy_version STRING NOT NULL,
  scenario_snapshot_hash STRING NOT NULL, ingestion_time TIMESTAMP NOT NULL,
  available_date DATE NOT NULL, source_hash STRING NOT NULL, owner STRING NOT NULL,
  quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.weekly_coverage_plan (
  plan_id STRING NOT NULL, as_of DATE NOT NULL, week_start DATE NOT NULL,
  policy_version STRING NOT NULL, selected_conversation_ids ARRAY<STRING> NOT NULL,
  solver_status STRING NOT NULL, objective_value DOUBLE NOT NULL,
  constraint_diagnostics VARIANT NOT NULL, scenario_snapshot_hash STRING NOT NULL,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  source_hash STRING NOT NULL, owner STRING NOT NULL, quality_status STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.features.weekly_coverage_scenario_draw (
  plan_id STRING NOT NULL, draw_id BIGINT NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, conversation_id STRING NOT NULL,
  need DOUBLE NOT NULL, client_value DOUBLE, bank_value DOUBLE, timing DOUBLE NOT NULL,
  relationship_value DOUBLE NOT NULL, strategic_value DOUBLE NOT NULL,
  risk DOUBLE NOT NULL, friction DOUBLE NOT NULL, feasibility DOUBLE NOT NULL,
  adjusted_benefit DOUBLE NOT NULL, random_seed BIGINT NOT NULL,
  policy_version STRING NOT NULL, source_hash STRING NOT NULL,
  available_date DATE NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.information_question (
  question_id STRING NOT NULL, conversation_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, variable_id STRING NOT NULL, stakeholder_role STRING NOT NULL,
  question_text STRING NOT NULL, answer_model VARIANT NOT NULL,
  can_change_decision BOOLEAN NOT NULL, status STRING NOT NULL,
  policy_version STRING NOT NULL, ingestion_time TIMESTAMP NOT NULL,
  available_date DATE NOT NULL, source_hash STRING NOT NULL, owner STRING NOT NULL,
  quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.features.voi_result (
  question_id STRING NOT NULL, as_of DATE NOT NULL, client_id STRING NOT NULL,
  gross_voi DECIMAL(38,9) NOT NULL, acquisition_cost DECIMAL(38,9) NOT NULL,
  delay_cost DECIMAL(38,9) NOT NULL, net_voi DECIMAL(38,9) NOT NULL,
  decision_effects ARRAY<STRING> NOT NULL, scenario_draw_count INT NOT NULL,
  random_seed BIGINT NOT NULL, policy_version STRING NOT NULL,
  source_hash STRING NOT NULL, available_date DATE NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.approved_client_answer (
  answer_id STRING NOT NULL, question_id STRING NOT NULL, as_of DATE NOT NULL,
  client_id STRING NOT NULL, response VARIANT NOT NULL, evidence_tier STRING NOT NULL,
  approval_status STRING NOT NULL, respondent_hash STRING NOT NULL, consent_reference STRING NOT NULL,
  scope STRING NOT NULL, valid_from TIMESTAMP NOT NULL, valid_to TIMESTAMP,
  reviewer_lineage VARIANT NOT NULL, ingestion_time TIMESTAMP NOT NULL,
  available_date DATE NOT NULL, source_hash STRING NOT NULL, owner STRING NOT NULL,
  quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.change_digest (
  digest_id STRING NOT NULL, client_id STRING NOT NULL, since DATE NOT NULL, as_of DATE NOT NULL,
  changes VARIANT NOT NULL, affected_problem_ids ARRAY<STRING> NOT NULL,
  affected_conversation_ids ARRAY<STRING> NOT NULL, source_hash STRING NOT NULL,
  transformation_version STRING NOT NULL, ingestion_time TIMESTAMP NOT NULL,
  available_date DATE NOT NULL, owner STRING NOT NULL, quality_status STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.curated.conversation_outcome (
  outcome_id STRING NOT NULL, conversation_id STRING NOT NULL, client_id STRING NOT NULL,
  as_of DATE NOT NULL, eligibility_recorded_at TIMESTAMP NOT NULL,
  exposure_at TIMESTAMP, action_at TIMESTAMP, outcome_at TIMESTAMP,
  assignment_probability DOUBLE, outcome_code STRING, censoring_state STRING NOT NULL,
  artifact_versions VARIANT NOT NULL, source_hash STRING NOT NULL,
  ingestion_time TIMESTAMP NOT NULL, available_date DATE NOT NULL,
  owner STRING NOT NULL, quality_status STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

-- V3.2 Promotion Readiness Twin analytical history.  The V3.1
-- registry.promotion_decision table above is retained as a compatibility
-- projection; these products are the authoritative append-only governance
-- surface.
CREATE TABLE IF NOT EXISTS wallet_twin.governance.promotion_gate_definition (
  gate_id STRING NOT NULL, catalogue_version STRING NOT NULL,
  transition_id STRING NOT NULL, target_state STRING NOT NULL,
  severity STRING NOT NULL, blocking BOOLEAN NOT NULL,
  definition VARIANT NOT NULL, source_hash STRING NOT NULL,
  generated_at TIMESTAMP NOT NULL, published_at TIMESTAMP NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.governance.promotion_verified_evidence (
  evidence_id STRING NOT NULL, gate_id STRING NOT NULL, track STRING NOT NULL,
  claimed_mode STRING NOT NULL, verified_mode STRING NOT NULL,
  artifact_uri STRING NOT NULL, content_hash STRING NOT NULL,
  envelope_hash STRING NOT NULL, signer_key_id STRING NOT NULL,
  trust_domain STRING NOT NULL, signature_status STRING NOT NULL,
  as_of DATE NOT NULL, generated_at TIMESTAMP NOT NULL,
  published_at TIMESTAMP NOT NULL, expires_at TIMESTAMP,
  simulation_clock TIMESTAMP, source_snapshot STRING NOT NULL,
  artifact_versions VARIANT NOT NULL, owner STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.governance.promotion_gate_evaluation (
  evaluation_id STRING NOT NULL, gate_id STRING NOT NULL,
  transition_id STRING NOT NULL, target_state STRING NOT NULL,
  track STRING NOT NULL, outcome STRING NOT NULL,
  evidence_ids ARRAY<STRING> NOT NULL, evidence_mode STRING,
  reason_codes ARRAY<STRING> NOT NULL,
  failure_injection_verified BOOLEAN NOT NULL,
  policy_version STRING NOT NULL, evaluated_at TIMESTAMP NOT NULL,
  as_of DATE NOT NULL, source_hash STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.governance.promotion_decision_v32 (
  decision_id STRING NOT NULL, as_of DATE NOT NULL,
  generated_at TIMESTAMP NOT NULL, published_at TIMESTAMP,
  real_state STRING NOT NULL, rehearsed_state STRING NOT NULL,
  bank_shadow_authorized BOOLEAN NOT NULL,
  promotion_machinery_readiness DOUBLE NOT NULL,
  bank_evidence_readiness DOUBLE NOT NULL,
  granted_capabilities ARRAY<STRING> NOT NULL,
  prohibited_capabilities VARIANT NOT NULL,
  gate_evaluations VARIANT NOT NULL, approval_ids ARRAY<STRING> NOT NULL,
  state_machine_version STRING NOT NULL, policy_version STRING NOT NULL,
  decision_hash STRING NOT NULL, signed_envelope VARIANT NOT NULL,
  signature_verified BOOLEAN NOT NULL, signer_key_id STRING NOT NULL,
  trust_domain STRING NOT NULL, entitlement_domain STRING NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true','wallet_entitled'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.governance.promotion_score_snapshot (
  score_id STRING NOT NULL, decision_id STRING NOT NULL,
  target_state STRING NOT NULL, as_of DATE NOT NULL,
  promotion_machinery_readiness DOUBLE NOT NULL,
  bank_evidence_readiness DOUBLE NOT NULL,
  rehearsal_weight_passed DOUBLE NOT NULL, real_weight_passed DOUBLE NOT NULL,
  total_weight DOUBLE NOT NULL, synthetic_weight_excluded DOUBLE NOT NULL,
  scoring_version STRING NOT NULL, source_hash STRING NOT NULL,
  generated_at TIMESTAMP NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.governance.promotion_rehearsal_result (
  run_id STRING NOT NULL, scenario_id STRING NOT NULL,
  as_of DATE NOT NULL, simulation_clock TIMESTAMP NOT NULL,
  virtual_days_elapsed INT NOT NULL, consecutive_clean_days INT NOT NULL,
  elapsed_bank_shadow_days INT NOT NULL, incident_count INT NOT NULL,
  daily_results VARIANT NOT NULL, terminal_status STRING NOT NULL,
  signer_key_id STRING NOT NULL, envelope_hash STRING NOT NULL,
  source_hash STRING NOT NULL, generated_at TIMESTAMP NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true');

CREATE TABLE IF NOT EXISTS wallet_twin.governance.e3_sample_size_plan (
  plan_id STRING NOT NULL, as_of DATE NOT NULL,
  sample_sizes ARRAY<INT> NOT NULL, replications_per_size INT NOT NULL,
  criteria VARIANT NOT NULL, results VARIANT NOT NULL,
  recommended_n STRING NOT NULL, recommendation_status STRING NOT NULL,
  monte_carlo_method STRING NOT NULL, evidence_mode STRING NOT NULL,
  source_hash STRING NOT NULL, transformation_version STRING NOT NULL,
  generated_at TIMESTAMP NOT NULL
) USING DELTA TBLPROPERTIES ('delta.enableChangeDataFeed'='true','delta.appendOnly'='true');

-- Governed tags must already exist with ASSIGN permission granted to the
-- deployment principal. These assignments are intentionally explicit so a
-- missing tag fails the migration instead of silently bypassing ABAC.
SET TAG ON TABLE wallet_twin.curated.client_product_activity wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.client_product_activity.client_id wallet_client_id;

SET TAG ON TABLE wallet_twin.training.multibank_calibration_observation wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.training.multibank_calibration_observation.client_id wallet_client_id;

SET TAG ON TABLE wallet_twin.curated.recommendation_event wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.recommendation_event.client_id wallet_client_id;

SET TAG ON TABLE wallet_twin.curated.effective_rate_card wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.effective_rate_card.gross_price_bps wallet_data_class = sensitive_economics;
SET TAG ON COLUMN wallet_twin.curated.effective_rate_card.ftp_bps wallet_data_class = sensitive_economics;
SET TAG ON COLUMN wallet_twin.curated.effective_rate_card.liquidity_bps wallet_data_class = sensitive_economics;
SET TAG ON COLUMN wallet_twin.curated.effective_rate_card.expected_loss_bps wallet_data_class = sensitive_economics;
SET TAG ON COLUMN wallet_twin.curated.effective_rate_card.capital_bps wallet_data_class = sensitive_economics;
SET TAG ON COLUMN wallet_twin.curated.effective_rate_card.total_cost_bps wallet_data_class = sensitive_economics;
SET TAG ON COLUMN wallet_twin.curated.effective_rate_card.hurdle_bps wallet_data_class = sensitive_economics;

SET TAG ON TABLE wallet_twin.features.shadow_wallet_draw wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.features.shadow_wallet_draw.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.features.shadow_wallet_edge wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.features.shadow_wallet_edge.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.features.product_need_estimate wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.features.product_need_estimate.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.features.change_point_state wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.features.change_point_state.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.monitoring.leakage_alarm wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.monitoring.leakage_alarm.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.features.treasury_graph_snapshot wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.features.treasury_graph_snapshot.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.curated.portfolio_selection wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.portfolio_selection.client_id wallet_client_id;
SET TAG ON COLUMN wallet_twin.curated.portfolio_selection.expected_value wallet_data_class = sensitive_economics;
SET TAG ON COLUMN wallet_twin.curated.portfolio_selection.value_at_risk wallet_data_class = sensitive_economics;
SET TAG ON COLUMN wallet_twin.curated.portfolio_selection.conditional_value_at_risk wallet_data_class = sensitive_economics;
SET TAG ON TABLE wallet_twin.curated.evidence_acquisition_plan wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.evidence_acquisition_plan.client_id wallet_client_id;

SET TAG ON TABLE wallet_twin.curated.business_twin_component wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.business_twin_component.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.curated.business_graph_node wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.business_graph_node.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.curated.business_graph_edge wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.business_graph_edge.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.curated.conversation_candidate wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.conversation_candidate.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.curated.weekly_coverage_plan wallet_entitled = true;
SET TAG ON TABLE wallet_twin.curated.client_value_component wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.client_value_component.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.curated.bank_value_component wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.bank_value_component.client_id wallet_client_id;
SET TAG ON COLUMN wallet_twin.curated.bank_value_component.direct_value_interval wallet_data_class = sensitive_economics;
