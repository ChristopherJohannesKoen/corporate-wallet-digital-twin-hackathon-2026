from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable
from .canonical import artifact_timestamp


ROOT = Path(__file__).resolve().parents[2]


CONTROL_EXPECTATIONS: Dict[str, tuple[str, tuple[str, ...]]] = {
    "private_eks": ("infra/terraform/main.tf", ("endpoint_public_access     = false", "endpoint_private_access    = true")),
    "eks_audit_logs": ("infra/terraform/main.tf", ("enabled_log_types", '"audit"')),
    "object_locked_evidence": ("infra/terraform/main.tf", ("object_lock_enabled = true", 'mode = "COMPLIANCE"')),
    "immutable_audit_archive": ("infra/terraform/security_observability.tf", ("aws_s3_bucket_object_lock_configuration", 'mode = "COMPLIANCE"')),
    "cloudtrail_integrity": ("infra/terraform/security_observability.tf", ("enable_log_file_validation    = true", "is_multi_region_trail")),
    "vpc_flow_logs": ("infra/terraform/security_observability.tf", ("aws_flow_log", 'traffic_type             = "ALL"')),
    "private_service_endpoints": ("infra/terraform/security_observability.tf", ("aws_vpc_endpoint", "private_dns_enabled = true")),
    "provider_secrets": ("infra/terraform/security_observability.tf", ("aws_secretsmanager_secret", "genai_provider")),
    "iam_authenticated_msk": ("infra/terraform/main.tf", ("sasl { iam = true }", 'client_broker = "TLS"')),
    "iam_authenticated_postgres": ("infra/terraform/main.tf", ("iam_database_authentication_enabled = true", "storage_encrypted")),
    "service_specific_irsa": ("infra/helm/wallet-twin/values.yaml", ("REQUIRED_INGESTION_ROLE", "REQUIRED_WORKBENCH_ROLE")),
    "non_root_digest_pinned_image_contract": ("infra/helm/wallet-twin/templates/workloads.yaml", ("runAsNonRoot: true", "image: \"{{ $.Values.image.repository }}@{{ $.Values.image.digest }}\"")),
    "network_default_deny": ("infra/helm/wallet-twin/templates/networkpolicy.yaml", ("wallet-default-deny", "policyTypes: [Ingress, Egress]")),
    "opa_deny_by_default": ("infra/policy/client_entitlements.rego", ("default allow := false", "owns_client")),
    "otel_redaction_and_export": ("infra/otel/collector.yaml", ("attributes/redact", "otlphttp/approved_observability")),
    "unity_catalog_data_products": ("infra/databricks/data_products.sql", ("multibank_calibration_observation", "recommendation_event", "promotion_decision")),
    "unity_catalog_abac": ("infra/databricks/unity_catalog_controls.sql", ("CREATE OR REPLACE POLICY wallet_client_rows", "MATCH COLUMNS has_tag('wallet_client_id')")),
    "mlflow_promotion_policy": ("config/mlflow_promotion_policy.json", ("OFFLINE_CANDIDATE__TO__SHADOW_READY", "SCALE_READY__TO__CAUSAL_CHAMPION", '"automatic_promotion": false', '"accountable_approval_required": true')),
    "asymmetric_manifest_signing": ("infra/terraform/security_observability.tf", ("aws_kms_key\" \"manifest_signing", 'key_usage                = "SIGN_VERIFY"')),
    "event_topic_contract": ("infra/msk/topics.yaml", ("wallet.eligibility-recorded.v1", "wallet.outcome-recorded.v1", "wallet.access-decision-logged.v1")),
    "supply_chain_ci": (".github/workflows/ci.yml", ("anchore/sbom-action", "aquasecurity/trivy-action", "gitleaks/gitleaks-action")),
}


def _check_file(relative: str, needles: Iterable[str]) -> dict:
    path = ROOT / relative
    if not path.exists():
        return {"passed": False, "evidence": relative, "missing": ["FILE"]}
    content = path.read_text(encoding="utf-8")
    # Terraform and Helm formatters are free to change horizontal/newline
    # spacing. Compare canonical whitespace so the control audit verifies the
    # actual declarations instead of a formatter-specific layout.
    normalized_content = " ".join(content.split())
    missing = [
        needle
        for needle in needles
        if " ".join(needle.split()) not in normalized_content
    ]
    return {"passed": not missing, "evidence": relative, "missing": missing}


def validate_production_target() -> dict:
    controls = {
        control: _check_file(relative, needles)
        for control, (relative, needles) in CONTROL_EXPECTATIONS.items()
    }
    definitions_ready = all(item["passed"] for item in controls.values())
    return {
        "version": "production-target-validation-1.0.0",
        "generated_at": artifact_timestamp(),
        "target": "AWS + Databricks / private EKS / Delta + Unity Catalog / MLflow / MSK / OPA / OpenTelemetry",
        "implementation_definitions_ready": definitions_ready,
        "controls_passed": sum(item["passed"] for item in controls.values()),
        "controls_total": len(controls),
        "controls": controls,
        "environment_state": {
            "aws_account_provisioned": False,
            "databricks_workspace_provisioned": False,
            "bank_sso_federated": False,
            "unity_catalog_policies_applied": False,
            "siem_destination_connected": False,
            "production_feeds_connected": False,
        },
        "apply_allowed": False,
        "apply_blockers": [
            "bank-owned AWS accounts, VPCs, subnets, DNS and deployment role",
            "bank-owned Databricks account, workspaces, metastore and SCIM groups",
            "approved SIEM destination and telemetry credentials",
            "architecture, privacy, third-party, security and model-risk approvals",
            "explicit cost and production-change authority",
        ],
        "bank_production_release_allowed": False,
    }


def write_production_target_report(path: Path | None = None) -> dict:
    result = validate_production_target()
    destination = path or (ROOT / "outputs" / "v2_validation" / "production_target_validation.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result
