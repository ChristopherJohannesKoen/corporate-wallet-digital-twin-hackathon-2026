-- Parameterize catalog names through the bank deployment pipeline.
CREATE CATALOG IF NOT EXISTS wallet_twin;
CREATE SCHEMA IF NOT EXISTS wallet_twin.curated;
CREATE SCHEMA IF NOT EXISTS wallet_twin.features;
CREATE SCHEMA IF NOT EXISTS wallet_twin.monitoring;

CREATE TABLE IF NOT EXISTS wallet_twin.curated.evidence_fact (
  business_key STRING NOT NULL,
  source_system_key STRING NOT NULL,
  client_id STRING NOT NULL,
  product STRING,
  evidence_tier STRING NOT NULL,
  claim_class STRING NOT NULL,
  value DECIMAL(38,9),
  currency STRING,
  source_unit STRING,
  page INT,
  bounding_box ARRAY<DOUBLE>,
  reporting_period STRING,
  source_date DATE,
  available_date DATE NOT NULL,
  source_hash STRING NOT NULL,
  event_time TIMESTAMP NOT NULL,
  valid_from TIMESTAMP NOT NULL,
  valid_to TIMESTAMP,
  ingestion_time TIMESTAMP NOT NULL,
  transformation_version STRING NOT NULL,
  quality_status STRING NOT NULL,
  owner STRING NOT NULL,
  entitlement_domain STRING NOT NULL,
  restates_business_key STRING
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

CREATE TABLE IF NOT EXISTS wallet_twin.features.wallet_snapshot (
  snapshot_id STRING NOT NULL,
  as_of TIMESTAMP NOT NULL,
  client_id STRING NOT NULL,
  product STRING NOT NULL,
  feature_payload VARIANT NOT NULL,
  source_hashes ARRAY<STRING> NOT NULL,
  transformation_version STRING NOT NULL,
  dataset_version STRING NOT NULL,
  entitlement_domain STRING NOT NULL
) USING DELTA
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true', 'delta.appendOnly' = 'true');

CREATE TABLE IF NOT EXISTS wallet_twin.monitoring.release_gate_result (
  release_id STRING NOT NULL,
  evaluated_at TIMESTAMP NOT NULL,
  gate_id STRING NOT NULL,
  passed BOOLEAN NOT NULL,
  measured_value DOUBLE,
  threshold STRING NOT NULL,
  evidence ARRAY<STRING> NOT NULL
) USING DELTA;

SET TAG ON TABLE wallet_twin.curated.evidence_fact wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.curated.evidence_fact.client_id wallet_client_id;
SET TAG ON TABLE wallet_twin.features.wallet_snapshot wallet_entitled = true;
SET TAG ON COLUMN wallet_twin.features.wallet_snapshot.client_id wallet_client_id;
