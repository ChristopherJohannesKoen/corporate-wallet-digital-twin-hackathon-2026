"""DSSE envelopes over RFC 8785 payloads.

DSSE (Dead Simple Signing Envelope) signs a *pre-authentication encoding* that
binds the payload type to the payload bytes::

    PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body

The length prefixes are what make it worth using: without them, a signature
over one payload type could be replayed as a signature over a different type
whose bytes happen to concatenate the same way. The bank cares about this
because the same signing key covers several artifact kinds.

Payload bytes come from :mod:`rfc8785`, never from ``canonical.py`` — see that
module's docstring for why signing a rounded payload is a defect rather than a
detail.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol, Sequence, Tuple

from .rfc8785 import canonical_bytes, canonical_sha256

DSSE_VERSION = "dsse-v1"
PAYLOAD_TYPE = "application/vnd.wallet-twin.promotion-evidence+json"


class SignatureError(ValueError):
    """A signature could not be produced or could not be trusted."""


def pae(payload_type: str, body: bytes) -> bytes:
    """DSSE pre-authentication encoding."""
    type_bytes = payload_type.encode("utf-8")
    return b" ".join(
        [
            b"DSSEv1",
            str(len(type_bytes)).encode("ascii"),
            type_bytes,
            str(len(body)).encode("ascii"),
            body,
        ]
    )


class Signer(Protocol):
    """Extension point matching ``wallet_twin_v2.evidence.ManifestSigner``.

    ``key_id`` and ``algorithm`` are surfaced so an envelope records which key
    signed it without the caller having to track that separately.
    """

    key_id: str
    algorithm: str

    def sign(self, payload: bytes) -> bytes: ...


class Verifier(Protocol):
    key_id: str

    def verify(self, payload: bytes, signature: bytes) -> bool: ...


@dataclass(frozen=True)
class Signature:
    keyid: str
    sig: str
    algorithm: str

    def as_dict(self) -> Dict[str, str]:
        return {"keyid": self.keyid, "sig": self.sig, "algorithm": self.algorithm}


@dataclass(frozen=True)
class Envelope:
    """A DSSE envelope. ``payload`` is base64 of the RFC 8785 canonical bytes.

    Two envelopes over the same payload differ (different keys, different
    nonces inside ECDSA) while ``payload_sha256`` stays identical. Tests assert
    exactly that: the digest is a property of the data, the envelope is a
    property of the signing event.
    """

    payload: str
    payload_type: str
    signatures: List[Signature] = field(default_factory=list)

    @property
    def payload_bytes(self) -> bytes:
        return base64.b64decode(self.payload)

    @property
    def payload_sha256(self) -> str:
        import hashlib

        return hashlib.sha256(self.payload_bytes).hexdigest()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "payload": self.payload,
            "payloadType": self.payload_type,
            "signatures": [item.as_dict() for item in self.signatures],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Envelope":
        return cls(
            payload=data["payload"],
            payload_type=data["payloadType"],
            signatures=[
                Signature(
                    keyid=item["keyid"],
                    sig=item["sig"],
                    algorithm=item.get("algorithm", "unknown"),
                )
                for item in data.get("signatures", [])
            ],
        )


def sign_payload(
    value: Any,
    signer: Signer,
    *,
    payload_type: str = PAYLOAD_TYPE,
) -> Envelope:
    """Canonicalise, wrap in PAE, sign, and return the envelope."""
    body = canonical_bytes(value)
    signature = signer.sign(pae(payload_type, body))
    return Envelope(
        payload=base64.b64encode(body).decode("ascii"),
        payload_type=payload_type,
        signatures=[
            Signature(
                keyid=signer.key_id,
                sig=base64.b64encode(signature).decode("ascii"),
                algorithm=signer.algorithm,
            )
        ],
    )


def verify_envelope(
    envelope: Envelope,
    verifiers: Sequence[Verifier],
) -> Tuple[bool, List[str]]:
    """Verify an envelope against a set of verifiers.

    Returns ``(verified, reason_codes)``. Verification fails closed: an
    envelope whose key is unknown to every verifier is *not verified*, rather
    than being treated as verified-by-absence. Reason codes are returned in all
    cases so a caller can report why, which matters more than the boolean when
    the answer is no.
    """
    reasons: List[str] = []
    if not envelope.signatures:
        return False, ["NO_SIGNATURE_PRESENT"]

    by_key = {verifier.key_id: verifier for verifier in verifiers}
    body = pae(envelope.payload_type, envelope.payload_bytes)
    verified = False

    for signature in envelope.signatures:
        verifier = by_key.get(signature.keyid)
        if verifier is None:
            reasons.append(f"UNKNOWN_KEY:{signature.keyid}")
            continue
        try:
            ok = verifier.verify(body, base64.b64decode(signature.sig))
        except Exception:  # noqa: BLE001 - any failure is a verification failure
            reasons.append(f"SIGNATURE_INVALID:{signature.keyid}")
            continue
        if ok:
            verified = True
            reasons.append(f"SIGNATURE_VALID:{signature.keyid}")
        else:
            reasons.append(f"SIGNATURE_INVALID:{signature.keyid}")

    if not verified:
        reasons.append("ENVELOPE_NOT_VERIFIED")
    return verified, reasons


def payload_digest(value: Any) -> str:
    """SHA-256 of the canonical payload, independent of any envelope."""
    return canonical_sha256(value)


def unsigned_envelope(value: Any, *, payload_type: str = PAYLOAD_TYPE) -> Envelope:
    """An envelope with no signature.

    Following ``evidence.signed_manifest``, unsigned is a reported state rather
    than an error: the artifact still exists and still has a digest, and saying
    so plainly is better than pretending a signer was available.
    """
    return Envelope(
        payload=base64.b64encode(canonical_bytes(value)).decode("ascii"),
        payload_type=payload_type,
        signatures=[],
    )


__all__ = [
    "DSSE_VERSION",
    "PAYLOAD_TYPE",
    "Envelope",
    "Signature",
    "SignatureError",
    "Signer",
    "Verifier",
    "pae",
    "payload_digest",
    "sign_payload",
    "unsigned_envelope",
    "verify_envelope",
]
