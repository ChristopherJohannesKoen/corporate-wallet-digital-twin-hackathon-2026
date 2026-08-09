-- Requires Databricks Runtime 16.4+ or serverless compute and SCIM-provisioned
-- account groups. Account administrators create the governed tags before this
-- migration. The migration fails closed if groups or tags are absent.

CREATE SCHEMA IF NOT EXISTS wallet_twin.governance;

CREATE OR REPLACE FUNCTION wallet_twin.governance.client_entitled(client_id STRING)
RETURNS BOOLEAN
RETURN
  is_account_group_member('wallet_platform_admin')
  OR is_account_group_member('wallet_model_risk')
  OR is_account_group_member(concat('wallet_client_', lower(client_id)));

CREATE OR REPLACE FUNCTION wallet_twin.governance.mask_sensitive_decimal(value DECIMAL(38,9))
RETURNS DECIMAL(38,9)
RETURN CASE
  WHEN is_account_group_member('wallet_platform_admin')
    OR is_account_group_member('wallet_product_finance')
    OR is_account_group_member('wallet_treasury')
    OR is_account_group_member('wallet_risk')
  THEN value
  ELSE CAST(NULL AS DECIMAL(38,9))
END;

CREATE OR REPLACE POLICY wallet_client_rows
ON CATALOG wallet_twin
COMMENT 'Deny-by-default client row entitlement for governed wallet data products'
ROW FILTER wallet_twin.governance.client_entitled
TO `account users`
EXCEPT `wallet_etl_service_principals`
FOR TABLES
WHEN has_tag_value('wallet_entitled', 'true')
MATCH COLUMNS has_tag('wallet_client_id') AS client_id
USING COLUMNS (client_id);

CREATE OR REPLACE POLICY wallet_sensitive_economics
ON CATALOG wallet_twin
COMMENT 'Mask commercial values outside Product Finance, Treasury, Risk and platform administration'
COLUMN MASK wallet_twin.governance.mask_sensitive_decimal
TO `account users`
EXCEPT `wallet_etl_service_principals`
FOR TABLES
WHEN has_tag_value('wallet_entitled', 'true')
MATCH COLUMNS has_tag_value('wallet_data_class', 'sensitive_economics') AS amount
ON COLUMN amount;

SHOW EFFECTIVE POLICIES ON CATALOG wallet_twin;

