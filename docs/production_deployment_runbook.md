# Bank-production deployment runbook

The production target is implemented as deployable definitions. Applying it
requires bank-owned accounts, identities, networks, destinations, approvals and
change authority.

## 1. Account and identity bootstrap

- Create separate development, validation, shadow and production AWS accounts
  and Databricks workspaces.
- Federate the corporate IdP through IAM Identity Center and SCIM-provision the
  standard wallet groups used by OPA and Unity Catalog.
- Create short-lived CI and workload roles. No individual IAM user or static
  production credential is accepted.
- Allocate the VPC, three private subnets, private route tables, inspected egress,
  DNS and approved ingress/WAF attachment.

## 2. AWS apply

- Configure the remote S3/DynamoDB state backend in the bank deployment job.
- Supply the VPC, subnet, route-table and federated administrator-role variables.
- Review the plan through Architecture and Cybersecurity, then apply with the
  bank deployment role.
- Verify private EKS, RDS IAM authentication, IAM/TLS MSK, immutable evidence and
  audit buckets, CloudTrail digest delivery, VPC flow logs, private endpoints,
  provider-secret containers and the asymmetric KMS signing key.
- Enable EKS audit log ingestion into Security Lake or the approved SIEM at the
  organisation layer.

## 3. Databricks apply

- Attach the workspace to the bank Unity Catalog metastore and approved S3
  storage credential/external location.
- Run `curated_tables.sql`, `data_products.sql`, then
  `unity_catalog_controls.sql` using a controlled migration principal.
- Create and delegate the governed tags referenced by the migrations before the
  final policy step. Missing tags or SCIM groups must fail the migration.
- Confirm effective ABAC policies, negative cross-client tests, workspace
  bindings and audit-system-table delivery.
- Configure MLflow with the policy in `config/mlflow_promotion_policy.json`;
  promotion is always approval-driven and retains a rollback alias.

## 4. Application and event plane

- Build, scan, sign and attest the container; use its immutable digest in Helm.
- Resolve a distinct IRSA role for each of the ten services.
- Create the existing runtime secret through the bank secret controller; the
  chart never creates secret values.
- Create the MSK topics in `infra/msk/topics.yaml`, deploy OPA and OpenTelemetry,
  then deploy the Helm release privately.
- Verify gateway, service, PostgreSQL, Unity Catalog and UI authorization using
  cross-client, cross-region, product and sensitive-economics negative tests.

## 5. Data, models and GenAI

- Connect real bank feeds through the ingestion contracts and reconcile source
  totals before any model snapshot is eligible.
- Load maker-checker-approved economics; synthetic rate cards remain blocked.
- Collect a consented E3 panel and independently refit/reproduce the five models.
- Rotate previously exposed provider credentials, populate only the approved
  provider secret, pin the approved model snapshot and run the public-only canary
  before the independently adjudicated sealed evaluation.
- Sign evidence and release manifests through the asymmetric KMS key.

## 6. Operational promotion

- Complete penetration, restore, failover, rollback and load tests in the bank
  environment.
- Run at least 30 elapsed clean shadow days. Simulated calendar days do not count.
- Complete the supervised RM pilot, remediate findings and then run the powered,
  pre-registered randomized trial.
- Promote only when the machine gates and accountable human approvals are both
  complete. Null causal results are valid outcomes and do not become uplift.
