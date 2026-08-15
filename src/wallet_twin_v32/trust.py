"""The trust registry: which key may sign what, where, for whom, and until when.

This is the layer where the REAL/REHEARSAL separation stops being a type and
becomes cryptographic. :mod:`modes` refuses synthetic evidence on the real
track, and :mod:`contracts` refuses to construct the offending object — but
both live inside this process and both can be bypassed by anything that writes
an artifact directly. A signature cannot.

A registered key binds six things, all of which fail **closed**:

``allowed_modes``
    A rehearsal key signing ``REAL_BANK`` is rejected. This is the invariant the
    whole registry exists for.
``allowed_environments``
    A key valid in FIXTURE cannot sign in PRODUCTION.
``allowed_roles``
    Ties signing authority to an accountable function, not just to possession.
``not_before`` / ``not_after``
    A key outside its validity window fails, so a forgotten key expires rather
    than lingering.
``revoked_at``
    Revocation is checked against the *verification* time, not the signing
    time, so revoking a key invalidates future verifications of everything it
    signed.
``trust_domain``
    Keeps rehearsal and bank roots in separate namespaces, so a rehearsal root
    can never be presented as a bank root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from wallet_twin_v2.contracts import DeploymentEnvironment

from .modes import REAL_TRACK_MODES, DecisionTrack, PromotionEvidenceMode, admits_track

TRUST_REGISTRY_VERSION = "v32-trust-registry-1.0.0"

#: Trust domains are separate namespaces. A key in ``rehearsal`` is never a
#: candidate for a bank verification, even if its key id somehow matched.
REHEARSAL_DOMAIN = "rehearsal"
BANK_DOMAIN = "bank"
PUBLIC_DOMAIN = "public"


class TrustError(ValueError):
    """A key is not trusted for what it is being asked to do."""


@dataclass(frozen=True)
class TrustedKey:
    """A key and the exact authority it carries."""

    key_id: str
    algorithm: str
    trust_domain: str
    allowed_modes: FrozenSet[PromotionEvidenceMode]
    allowed_environments: FrozenSet[DeploymentEnvironment]
    allowed_roles: FrozenSet[str]
    not_before: datetime
    not_after: datetime
    #: Public key material, PEM-encoded. Absent for KMS and Sigstore keys,
    #: where verification is delegated.
    public_key_pem: Optional[str] = None
    revoked_at: Optional[datetime] = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.not_after <= self.not_before:
            raise TrustError(f"key {self.key_id}: validity window is empty")
        if not self.allowed_modes:
            raise TrustError(f"key {self.key_id}: no allowed modes; it can sign nothing")
        # A key trusted for real bank evidence must not live in the rehearsal
        # trust domain. This is the misconfiguration the registry most needs to
        # refuse, because it would silently make every other control ineffective.
        real_modes = set(self.allowed_modes) & set(REAL_TRACK_MODES)
        if real_modes and self.trust_domain == REHEARSAL_DOMAIN:
            raise TrustError(
                f"key {self.key_id}: authorised for {sorted(m.value for m in real_modes)} "
                f"while sitting in the '{REHEARSAL_DOMAIN}' trust domain; a "
                "rehearsal root cannot confer bank authority"
            )

    def is_valid_at(self, moment: datetime) -> bool:
        return self.not_before <= moment <= self.not_after

    def is_revoked_at(self, moment: datetime) -> bool:
        return self.revoked_at is not None and moment >= self.revoked_at


@dataclass
class TrustDecision:
    """Why a key was or was not trusted. Reasons are returned either way."""

    trusted: bool
    reason_codes: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.trusted


class TrustRegistry:
    """The set of keys the system will accept, and the rules binding them."""

    version = TRUST_REGISTRY_VERSION

    def __init__(self, keys: Optional[Sequence[TrustedKey]] = None) -> None:
        self._keys: Dict[str, TrustedKey] = {}
        for key in keys or ():
            self.register(key)

    def register(self, key: TrustedKey) -> None:
        if key.key_id in self._keys:
            raise TrustError(f"key {key.key_id} is already registered")
        self._keys[key.key_id] = key

    def get(self, key_id: str) -> Optional[TrustedKey]:
        return self._keys.get(key_id)

    def keys(self) -> Tuple[TrustedKey, ...]:
        return tuple(self._keys[key_id] for key_id in sorted(self._keys))

    def evaluate(
        self,
        key_id: str,
        *,
        mode: PromotionEvidenceMode,
        track: DecisionTrack,
        environment: DeploymentEnvironment,
        role: str,
        moment: Optional[datetime] = None,
    ) -> TrustDecision:
        """Decide whether this key may sign this, here, now.

        Every check is evaluated and every failure recorded rather than
        returning at the first one. A caller fixing a misconfiguration should
        see all of what is wrong, not discover it one round-trip at a time.
        """
        moment = moment or datetime.now(timezone.utc)
        reasons: List[str] = []

        key = self._keys.get(key_id)
        if key is None:
            return TrustDecision(False, [f"UNKNOWN_KEY:{key_id}"])

        if mode not in key.allowed_modes:
            reasons.append(
                f"KEY_NOT_AUTHORISED_FOR_MODE:{mode.value}"
            )
        if not admits_track(mode, track):
            reasons.append(f"MODE_NOT_ADMISSIBLE_ON_TRACK:{mode.value}/{track.value}")
        if environment not in key.allowed_environments:
            reasons.append(f"KEY_NOT_AUTHORISED_IN_ENVIRONMENT:{environment.value}")
        if role not in key.allowed_roles:
            reasons.append(f"ROLE_NOT_AUTHORISED:{role}")
        if not key.is_valid_at(moment):
            reasons.append("KEY_OUTSIDE_VALIDITY_WINDOW")
        if key.is_revoked_at(moment):
            reasons.append("KEY_REVOKED")
        # A fixture deployment must never carry a real trust root: it is the
        # environment least likely to be access-controlled.
        if (
            environment is DeploymentEnvironment.FIXTURE
            and key.trust_domain == BANK_DOMAIN
        ):
            reasons.append("BANK_TRUST_ROOT_REFUSED_IN_FIXTURE_ENVIRONMENT")

        if reasons:
            return TrustDecision(False, reasons)
        return TrustDecision(
            True,
            [f"TRUSTED:{key_id}", f"DOMAIN:{key.trust_domain}", f"MODE:{mode.value}"],
        )

    def assert_trusted(self, key_id: str, **kwargs: object) -> None:
        """Raise unless the key is trusted. For call sites that cannot proceed."""
        decision = self.evaluate(key_id, **kwargs)  # type: ignore[arg-type]
        if not decision.trusted:
            raise TrustError(
                f"key {key_id} is not trusted: {', '.join(decision.reason_codes)}"
            )

    def as_document(self) -> Dict[str, object]:
        """Publishable description. Public key material is included; private
        material never touches this class."""
        return {
            "registry_version": self.version,
            "keys": [
                {
                    "key_id": key.key_id,
                    "algorithm": key.algorithm,
                    "trust_domain": key.trust_domain,
                    "allowed_modes": sorted(mode.value for mode in key.allowed_modes),
                    "allowed_environments": sorted(
                        environment.value for environment in key.allowed_environments
                    ),
                    "allowed_roles": sorted(key.allowed_roles),
                    "not_before": key.not_before.isoformat(),
                    "not_after": key.not_after.isoformat(),
                    "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
                    "description": key.description,
                }
                for key in self.keys()
            ],
        }


def rehearsal_key(
    key_id: str,
    *,
    algorithm: str = "ecdsa-p256-sha256",
    not_before: datetime,
    not_after: datetime,
    public_key_pem: Optional[str] = None,
) -> TrustedKey:
    """A key that can sign rehearsal evidence and nothing else.

    Deliberately the only convenience constructor in this module. Building a
    key with real-bank authority should require stating every field explicitly,
    because that is a decision someone should have to make on purpose.
    """
    return TrustedKey(
        key_id=key_id,
        algorithm=algorithm,
        trust_domain=REHEARSAL_DOMAIN,
        allowed_modes=frozenset(
            {
                PromotionEvidenceMode.SYNTHETIC_REHEARSAL,
                PromotionEvidenceMode.SIMULATED_POLICY,
            }
        ),
        allowed_environments=frozenset(
            {
                DeploymentEnvironment.FIXTURE,
                DeploymentEnvironment.DEVELOPMENT,
                DeploymentEnvironment.CLIENT_DEMO,
            }
        ),
        allowed_roles=frozenset({"ENGINEERING", "REHEARSAL_OPERATOR"}),
        not_before=not_before,
        not_after=not_after,
        public_key_pem=public_key_pem,
        description="Local rehearsal signer. Cannot confer bank authority.",
    )


__all__ = [
    "BANK_DOMAIN",
    "PUBLIC_DOMAIN",
    "REHEARSAL_DOMAIN",
    "TRUST_REGISTRY_VERSION",
    "TrustDecision",
    "TrustError",
    "TrustRegistry",
    "TrustedKey",
    "rehearsal_key",
]
