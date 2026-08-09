package wallet.entitlements

import rego.v1

default allow := false

valid_environment if input.environment in {"SHADOW", "PILOT", "PRODUCTION"}

active_identity if {
  input.user_id != ""
  input.mfa_authenticated == true
  input.workload_identity_age_seconds <= 3600
}

owns_client if input.client_id in input.allowed_client_ids
owns_region if input.client_region in input.allowed_regions
owns_product if input.product in input.allowed_products

allow if {
  valid_environment
  active_identity
  owns_client
  owns_region
  owns_product
  input.action == "read"
}

allow if {
  valid_environment
  active_identity
  owns_client
  input.action == "approve_evidence"
  "EVIDENCE_REVIEWER" in input.roles
}

allow if {
  valid_environment
  active_identity
  owns_client
  owns_product
  input.action == "read_sensitive_economics"
  input.roles[_] in {"PRODUCT_FINANCE", "TREASURY", "RISK", "PLATFORM_ADMIN"}
}

deny_reasons contains "IDENTITY_INVALID" if not active_identity
deny_reasons contains "ENVIRONMENT_INVALID" if not valid_environment
deny_reasons contains "CLIENT_NOT_ENTITLED" if not owns_client
deny_reasons contains "REGION_NOT_ENTITLED" if not owns_region
deny_reasons contains "PRODUCT_NOT_ENTITLED" if not owns_product
