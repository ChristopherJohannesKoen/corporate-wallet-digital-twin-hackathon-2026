package wallet.entitlements

import rego.v1

default allow := false

valid_environment if input.environment in {"SHADOW", "PILOT", "PRODUCTION"}

active_identity if {
  input.user_id != ""
  input.mfa_authenticated == true
  input.workload_identity_age_seconds <= 3600
}

# Wildcard grants. The in-process ABAC in wallet_twin_v2.entitlements has always
# treated "*" as "every value", and this policy did not — so an administrator
# entitled to client_ids ["*"] was allowed in-process and denied by OPA. Nothing
# detected that until V3.2 put OPA in the request path and compared the two
# answers, because the policy engine had never actually been consulted.
#
# Written as separate rule bodies rather than one `or`, because Rego evaluates
# same-named rules as a disjunction and the separate form states each grant
# explicitly.
owns_client if "*" in input.allowed_client_ids
owns_client if input.client_id in input.allowed_client_ids

# A request that names no client is not a client-scoped request, so there is
# nothing to own. This matches the in-process rule, which only applies the check
# `if client_id`.
owns_client if input.client_id == ""

owns_region if "*" in input.allowed_regions
owns_region if input.client_region in input.allowed_regions
owns_region if input.client_region == ""

owns_product if "*" in input.allowed_products
owns_product if input.product in input.allowed_products
owns_product if input.product == ""

# An empty entitlement list means "unrestricted on this dimension", matching the
# in-process rule's `and context.products` guard. This is deliberately NOT
# extended to client_ids: an empty client entitlement must deny, because a
# principal with no clients should reach no client's data.
owns_product if count(input.allowed_products) == 0

allow if {
  valid_environment
  active_identity
  owns_client
  owns_region
  owns_product
  input.action == "read"
}

# Evidence approval carries the same client, region and product scoping as a
# read. It previously required only `owns_client`, which meant a reviewer could
# approve a fact about a product or a region they were not entitled to see —
# approving evidence you cannot look at is not a coherent control. A
# combinatorial sweep of 4,860 principal/request pairs found 96 cases where this
# rule allowed what the in-process policy refused.
allow if {
  valid_environment
  active_identity
  owns_client
  owns_region
  owns_product
  input.action == "approve_evidence"
  "EVIDENCE_REVIEWER" in input.roles
}

allow if {
  valid_environment
  active_identity
  owns_client
  owns_region
  owns_product
  input.action == "read_sensitive_economics"
  input.roles[_] in {"PRODUCT_FINANCE", "TREASURY", "RISK", "PLATFORM_ADMIN"}
}

deny_reasons contains "IDENTITY_INVALID" if not active_identity
deny_reasons contains "ENVIRONMENT_INVALID" if not valid_environment
deny_reasons contains "CLIENT_NOT_ENTITLED" if not owns_client
deny_reasons contains "REGION_NOT_ENTITLED" if not owns_region
deny_reasons contains "PRODUCT_NOT_ENTITLED" if not owns_product
