"""Three signer implementations, with honest capability reporting.

============================  ========================  =========================
Signer                        Signs                     Verifiable here?
============================  ========================  =========================
``LocalECDSASigner``          rehearsal only            yes — fully, in CI
``SigstoreSigner``            rehearsal, public         no — needs GitHub OIDC
``KMSSigner``                 real bank, attested       no — needs live AWS
============================  ========================  =========================

Only the first can be exercised on a build machine. The other two ship as
adapters with interface tests and report ``NOT_EXECUTED`` rather than claiming
a capability that has not been demonstrated. That distinction is the same one
the promotion twin makes everywhere else: an adapter that compiles is not a
signature that verified.

Each signer exposes ``capability_report()`` so the submission can state exactly
what was and was not exercised, rather than listing three signers and letting a
reader assume all three ran.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .dsse import SignatureError
from .modes import PromotionEvidenceMode

SIGNERS_VERSION = "v32-signers-1.0.0"

#: Reported when an adapter exists but its backing service was unavailable.
NOT_EXECUTED = "NOT_EXECUTED"
EXECUTED = "EXECUTED"


# ---------------------------------------------------------------------------
# Local ECDSA P-256 — rehearsal only, fully testable
# ---------------------------------------------------------------------------


class LocalECDSASigner:
    """ECDSA P-256 over SHA-256, using a locally held key.

    Rehearsal only. The trust registry refuses to place a key with real-bank
    authority in the rehearsal domain, so this signer's key cannot be promoted
    into one that satisfies a real gate by editing a config file.

    Keys are generated in memory by default. A production-shaped deployment
    would load one, but a rehearsal signer that leaves no private key on disk
    is the safer default for a repository that will be published.
    """

    algorithm = "ecdsa-p256-sha256"
    allowed_modes = frozenset(
        {
            PromotionEvidenceMode.SYNTHETIC_REHEARSAL,
            PromotionEvidenceMode.SIMULATED_POLICY,
        }
    )

    def __init__(self, key_id: str = "local-rehearsal-p256", *, private_key: Any = None):
        from cryptography.hazmat.primitives.asymmetric import ec

        self.key_id = key_id
        self._private_key = private_key or ec.generate_private_key(ec.SECP256R1())
        self._public_key = self._private_key.public_key()

    @classmethod
    def from_pem(cls, key_id: str, pem: bytes, password: Optional[bytes] = None) -> "LocalECDSASigner":
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        return cls(key_id, private_key=load_pem_private_key(pem, password=password))

    @classmethod
    def deterministic(cls, key_id: str, seed: int) -> "LocalECDSASigner":
        """A reproducible key, for tests that must not vary run to run.

        ECDSA *signatures* remain non-deterministic (RFC 6979 is not used by
        this backend), which is correct and is asserted in the tests: two
        envelopes over one payload differ while the payload digest does not.
        """
        from cryptography.hazmat.primitives.asymmetric import ec

        # A fixed scalar in the valid range for SECP256R1.
        order = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551
        scalar = (seed % (order - 1)) + 1
        return cls(key_id, private_key=ec.derive_private_key(scalar, ec.SECP256R1()))

    def sign(self, payload: bytes) -> bytes:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        return self._private_key.sign(payload, ec.ECDSA(hashes.SHA256()))

    def verify(self, payload: bytes, signature: bytes) -> bool:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        try:
            self._public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
        except InvalidSignature:
            return False
        return True

    def public_key_pem(self) -> str:
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            PublicFormat,
        )

        return self._public_key.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode("ascii")

    def capability_report(self) -> Dict[str, Any]:
        return {
            "signer": "LocalECDSASigner",
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "status": EXECUTED,
            "modes": sorted(mode.value for mode in self.allowed_modes),
            "verifiable_in_ci": True,
            "note": "Rehearsal only. Cannot satisfy a real-track gate.",
        }


class LocalECDSAVerifier:
    """Verifier holding only public key material."""

    def __init__(self, key_id: str, public_key_pem: str) -> None:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        self.key_id = key_id
        self._public_key = load_pem_public_key(public_key_pem.encode("ascii"))

    def verify(self, payload: bytes, signature: bytes) -> bool:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec

        try:
            self._public_key.verify(signature, payload, ec.ECDSA(hashes.SHA256()))
        except InvalidSignature:
            return False
        return True


# ---------------------------------------------------------------------------
# Sigstore — keyless, GitHub OIDC. Exercised only inside Actions.
# ---------------------------------------------------------------------------


@dataclass
class SigstoreSigner:
    """Keyless signing via Sigstore and a GitHub OIDC identity.

    Cannot run on a build machine: it needs an ambient OIDC token that only CI
    issues. ``sigstore`` is also not installed here. Rather than stub something
    that returns bytes and lets the caller believe a signature happened, this
    raises on ``sign()`` when unavailable and reports ``NOT_EXECUTED``.
    """

    key_id: str = "sigstore-github-oidc"
    algorithm: str = "sigstore-ecdsa-p256-sha256"
    identity: Optional[str] = None
    allowed_modes = frozenset(
        {
            PromotionEvidenceMode.SYNTHETIC_REHEARSAL,
            PromotionEvidenceMode.SIMULATED_POLICY,
            PromotionEvidenceMode.PUBLIC_PACKAGE,
        }
    )

    @staticmethod
    def availability() -> Tuple[bool, str]:
        try:
            import sigstore  # noqa: F401
        except ImportError:
            return False, "SIGSTORE_LIBRARY_NOT_INSTALLED"
        if not os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL"):
            return False, "NO_AMBIENT_OIDC_TOKEN"
        return True, "AVAILABLE"

    def sign(self, payload: bytes) -> bytes:
        available, reason = self.availability()
        if not available:
            raise SignatureError(
                f"Sigstore signing unavailable: {reason}. The adapter exists and "
                "is interface-tested; it has not signed anything here and must "
                "not be reported as if it had."
            )
        from sigstore.oidc import detect_credential  # type: ignore[import-not-found]
        from sigstore.sign import SigningContext  # type: ignore[import-not-found]

        context = SigningContext.production()
        with context.signer(detect_credential()) as signer:
            return signer.sign(payload).signature  # pragma: no cover - needs CI

    def capability_report(self) -> Dict[str, Any]:
        available, reason = self.availability()
        return {
            "signer": "SigstoreSigner",
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "status": EXECUTED if available else NOT_EXECUTED,
            "reason": reason,
            "modes": sorted(mode.value for mode in self.allowed_modes),
            "verifiable_in_ci": True,
            "note": (
                "Keyless signing requires an ambient GitHub OIDC token. Runs "
                "inside Actions only; reported NOT_EXECUTED elsewhere."
            ),
        }


# ---------------------------------------------------------------------------
# AWS KMS — the only signer permitted to sign real bank evidence.
# ---------------------------------------------------------------------------


@dataclass
class KMSSigner:
    """AWS KMS asymmetric signing, for potentially-real modes.

    Two things to know about the existing infrastructure:

    - The Terraform key at ``infra/terraform/security_observability.tf`` is
      **RSA-3072**, not the ``ECDSA_SHA_256`` this signer defaults to. A second
      key resource is required; the default here names the intended algorithm
      rather than silently matching the wrong existing key.
    - ``production_adapters.KMSManifestSigner`` has ``sign()`` but no
      ``verify()``. Verification via ``kms:Verify`` is new here, and it is the
      half that matters: signing without verifying proves only that a call
      succeeded.
    """

    key_id: str = "aws-kms-promotion-signer"
    algorithm: str = "ECDSA_SHA_256"
    key_arn: Optional[str] = None
    region: Optional[str] = None
    allowed_modes = frozenset(
        {
            PromotionEvidenceMode.PUBLIC_PACKAGE,
            PromotionEvidenceMode.PUBLIC_APPROVED,
            PromotionEvidenceMode.REAL_BANK,
            PromotionEvidenceMode.BANK_ATTESTED,
        }
    )

    def availability(self) -> Tuple[bool, str]:
        arn = self.key_arn or os.getenv("PROMOTION_KMS_KEY_ARN")
        if not arn:
            return False, "NO_KMS_KEY_ARN_CONFIGURED"
        try:
            import boto3  # noqa: F401
        except ImportError:
            return False, "BOTO3_NOT_INSTALLED"
        if not (
            os.getenv("AWS_ACCESS_KEY_ID")
            or os.getenv("AWS_PROFILE")
            or os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE")
        ):
            return False, "NO_AWS_CREDENTIALS_AVAILABLE"
        return True, "AVAILABLE"

    def _client(self):  # pragma: no cover - needs live AWS
        import boto3

        return boto3.client("kms", region_name=self.region or os.getenv("AWS_REGION"))

    def sign(self, payload: bytes) -> bytes:
        available, reason = self.availability()
        if not available:
            raise SignatureError(
                f"KMS signing unavailable: {reason}. This signer holds the only "
                "authority to sign real bank evidence, so a stub that returned "
                "plausible bytes would be the single most dangerous shortcut in "
                "this codebase."
            )
        response = self._client().sign(  # pragma: no cover - needs live AWS
            KeyId=self.key_arn or os.environ["PROMOTION_KMS_KEY_ARN"],
            Message=payload,
            MessageType="RAW",
            SigningAlgorithm=self.algorithm,
        )
        return response["Signature"]  # pragma: no cover - needs live AWS

    def verify(self, payload: bytes, signature: bytes) -> bool:
        available, reason = self.availability()
        if not available:
            raise SignatureError(f"KMS verification unavailable: {reason}")
        response = self._client().verify(  # pragma: no cover - needs live AWS
            KeyId=self.key_arn or os.environ["PROMOTION_KMS_KEY_ARN"],
            Message=payload,
            MessageType="RAW",
            Signature=signature,
            SigningAlgorithm=self.algorithm,
        )
        return bool(response["SignatureValid"])  # pragma: no cover - needs live AWS

    def capability_report(self) -> Dict[str, Any]:
        available, reason = self.availability()
        return {
            "signer": "KMSSigner",
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "status": EXECUTED if available else NOT_EXECUTED,
            "reason": reason,
            "modes": sorted(mode.value for mode in self.allowed_modes),
            "verifiable_in_ci": False,
            "note": (
                "Requires a live AWS account and a new ECDSA_SHA_256 KMS key; "
                "the existing Terraform key is RSA-3072. Reported NOT_EXECUTED "
                "until both exist."
            ),
        }


def signer_capability_report() -> Dict[str, Any]:
    """What each signer can actually do here, for publication.

    Listing three signers without saying which of them ran would let a reader
    assume all three were exercised. This is the artifact that prevents that
    reading.
    """
    reports = [
        LocalECDSASigner().capability_report(),
        SigstoreSigner().capability_report(),
        KMSSigner().capability_report(),
    ]
    return {
        "signers_version": SIGNERS_VERSION,
        "signers": reports,
        "executed": [item["signer"] for item in reports if item["status"] == EXECUTED],
        "not_executed": [
            item["signer"] for item in reports if item["status"] == NOT_EXECUTED
        ],
        "real_bank_signing_available": any(
            item["status"] == EXECUTED and "REAL_BANK" in item["modes"]
            for item in reports
        ),
    }


__all__ = [
    "EXECUTED",
    "NOT_EXECUTED",
    "SIGNERS_VERSION",
    "KMSSigner",
    "LocalECDSASigner",
    "LocalECDSAVerifier",
    "SigstoreSigner",
    "signer_capability_report",
]
