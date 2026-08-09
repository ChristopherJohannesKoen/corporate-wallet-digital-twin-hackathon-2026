# AWS reference stack

This Terraform root provisions the private platform primitives required by V2:
KMS, an asymmetric manifest-signing key, compliance-mode S3 Object Lock,
private EKS with control-plane logs, IAM-authenticated MSK and Aurora PostgreSQL,
CloudTrail integrity validation, object-locked audit storage, VPC flow logs,
private AWS endpoints and empty provider-secret containers. State configuration
is provided by the bank pipeline at `terraform init`; credentials, secret values
and backend names are never committed.

It intentionally consumes a bank-managed VPC and private subnets so inspection,
DNS, egress, transit routing and security services remain under platform control.
Databricks data-product and ABAC migrations, MLflow promotion policy, EKS Helm,
OPA, MSK topic contracts and OpenTelemetry are included in `infra/`. The
Databricks account/workspace, Unity Catalog metastore attachment, corporate SSO,
approved SIEM destination and application WAF/ingress attachment remain bank
platform operations because their account IDs, groups, network boundaries and
destinations are institution-owned.

Before apply: replace all example Helm values, run `terraform validate`, obtain
architecture/security approval, and execute through the bank's policy-gated CI
identity. Production deletion protection is mandatory.
