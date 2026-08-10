CREATE SCHEMA IF NOT EXISTS wallet_twin.raw;
CREATE SCHEMA IF NOT EXISTS wallet_twin.conformed;
CREATE SCHEMA IF NOT EXISTS wallet_twin.training;
CREATE SCHEMA IF NOT EXISTS wallet_twin.registry;

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
