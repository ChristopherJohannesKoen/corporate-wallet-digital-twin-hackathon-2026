CREATE SCHEMA IF NOT EXISTS wallet_twin.raw;
CREATE SCHEMA IF NOT EXISTS wallet_twin.conformed;
CREATE SCHEMA IF NOT EXISTS wallet_twin.training;
CREATE SCHEMA IF NOT EXISTS wallet_twin.registry;

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
