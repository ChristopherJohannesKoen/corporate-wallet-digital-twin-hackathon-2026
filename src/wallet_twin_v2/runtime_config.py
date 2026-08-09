from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

from .contracts import DeploymentEnvironment


@dataclass(frozen=True)
class RuntimeConfig:
    environment: DeploymentEnvironment
    aws_region: str
    kms_key_arn: str
    immutable_document_bucket: str
    msk_brokers: str
    postgres_dsn: str
    opa_url: str
    oidc_issuer: str
    oidc_audience: str
    otel_endpoint: str
    mlflow_registry_uri: str
    unity_catalog: str
    genai_provider: str

    @classmethod
    def from_env(cls, environ: Dict[str, str] | None = None) -> "RuntimeConfig":
        values = environ if environ is not None else os.environ
        mode = values.get("WALLET_DEPLOYMENT_MODE", "FIXTURE").upper()
        try:
            environment = DeploymentEnvironment(mode)
        except ValueError as exc:
            raise ValueError(f"unsupported WALLET_DEPLOYMENT_MODE: {mode}") from exc
        return cls(
            environment=environment,
            aws_region=values.get("AWS_REGION", ""),
            kms_key_arn=values.get("WALLET_KMS_KEY_ARN", ""),
            immutable_document_bucket=values.get("WALLET_IMMUTABLE_BUCKET", ""),
            msk_brokers=values.get("WALLET_MSK_BROKERS", ""),
            postgres_dsn=values.get("WALLET_POSTGRES_DSN", ""),
            opa_url=values.get("WALLET_OPA_URL", ""),
            oidc_issuer=values.get("WALLET_OIDC_ISSUER", ""),
            oidc_audience=values.get("WALLET_OIDC_AUDIENCE", ""),
            otel_endpoint=values.get("OTEL_EXPORTER_OTLP_ENDPOINT", ""),
            mlflow_registry_uri=values.get("WALLET_MLFLOW_REGISTRY_URI", ""),
            unity_catalog=values.get("WALLET_UNITY_CATALOG", ""),
            genai_provider=values.get("GENAI_PROVIDER", "deterministic").lower(),
        )

    def validate(self) -> dict:
        controlled = self.environment in {
            DeploymentEnvironment.SHADOW,
            DeploymentEnvironment.PILOT,
            DeploymentEnvironment.PRODUCTION,
        }
        required = {
            "aws_region": self.aws_region,
            "kms_key_arn": self.kms_key_arn,
            "immutable_document_bucket": self.immutable_document_bucket,
            "msk_brokers": self.msk_brokers,
            "postgres_dsn": self.postgres_dsn,
            "opa_url": self.opa_url,
            "oidc_issuer": self.oidc_issuer,
            "oidc_audience": self.oidc_audience,
            "otel_endpoint": self.otel_endpoint,
            "mlflow_registry_uri": self.mlflow_registry_uri,
            "unity_catalog": self.unity_catalog,
        }
        errors: List[str] = []
        if controlled:
            errors.extend(f"MISSING_REQUIRED_CONFIG:{name}" for name, value in required.items() if not value)
            if self.postgres_dsn and not self.postgres_dsn.startswith(("postgresql://", "postgresql+")):
                errors.append("INVALID_POSTGRES_DSN")
            if self.opa_url and not self.opa_url.startswith("https://"):
                errors.append("OPA_TLS_REQUIRED")
            if self.oidc_issuer and not self.oidc_issuer.startswith("https://"):
                errors.append("OIDC_TLS_REQUIRED")
        if self.genai_provider not in {"deterministic", "openai", "anthropic", "google"}:
            errors.append("UNSUPPORTED_GENAI_PROVIDER")
        client_demo = self.environment == DeploymentEnvironment.CLIENT_DEMO
        return {
            "environment": self.environment.value,
            "valid": not errors,
            "errors": errors,
            "fail_closed": (controlled and bool(errors)) or (client_demo and "UNSUPPORTED_GENAI_PROVIDER" in errors),
            "secrets_exposed": False,
            "configured_components": {name: bool(value) for name, value in required.items()},
            "genai_provider": self.genai_provider,
            "claim_profile": (
                "CLIENT_DEMO_SIMULATED_REPRESENTATIVE"
                if client_demo
                else "BANK_CONTROLLED" if controlled else "LOCAL_DEVELOPMENT"
            ),
            "bank_production_claims_allowed": False if client_demo else None,
        }

    def assert_startable(self) -> None:
        report = self.validate()
        if report["fail_closed"]:
            raise RuntimeError("CONTROLLED_RUNTIME_CONFIGURATION_INVALID:" + ";".join(report["errors"]))


class OIDCVerifier:
    """Bank OIDC token verifier with remote JWKS signature validation."""

    def __init__(self, issuer: str, audience: str) -> None:
        if not issuer.startswith("https://") or not audience:
            raise ValueError("OIDC verifier requires HTTPS issuer and audience")
        self.issuer = issuer.rstrip("/")
        self.audience = audience

    def verify(self, token: str) -> dict:
        if not token or token.count(".") != 2:
            raise ValueError("invalid bearer token")
        import jwt

        jwks = jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json")
        signing_key = jwks.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=self.audience,
            issuer=self.issuer,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
