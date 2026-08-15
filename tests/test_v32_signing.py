"""Canonicalisation, DSSE, trust and the three signers.

The acceptance criteria here are adversarial by design: a rehearsal key
signing real bank evidence is rejected, a tampered payload changes the digest,
expired and revoked keys fail, and a fixture environment refuses a bank trust
root. Each is proven by constructing the attack and asserting it fails, not by
asserting the honest path works.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import pytest

from wallet_twin_v2.contracts import DeploymentEnvironment
from wallet_twin_v32.dsse import (
    Envelope,
    SignatureError,
    pae,
    payload_digest,
    sign_payload,
    unsigned_envelope,
    verify_envelope,
)
from wallet_twin_v32.modes import DecisionTrack, PromotionEvidenceMode
from wallet_twin_v32.rfc8785 import (
    CanonicalisationError,
    canonical_bytes,
    canonical_sha256,
    canonicalise,
    serialize_number,
)
from wallet_twin_v32.signers import (
    EXECUTED,
    NOT_EXECUTED,
    KMSSigner,
    LocalECDSASigner,
    LocalECDSAVerifier,
    SigstoreSigner,
    signer_capability_report,
)
from wallet_twin_v32.trust import (
    BANK_DOMAIN,
    PUBLIC_DOMAIN,
    REHEARSAL_DOMAIN,
    TrustError,
    TrustRegistry,
    TrustedKey,
    rehearsal_key,
)

NOW = datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc)
SYNTHETIC = PromotionEvidenceMode.SYNTHETIC_REHEARSAL
PUBLIC = PromotionEvidenceMode.PUBLIC_PACKAGE
REAL_BANK = PromotionEvidenceMode.REAL_BANK
ATTESTED = PromotionEvidenceMode.BANK_ATTESTED

PAYLOAD = {
    "gate_id": "reconciliation-exact",
    "mode": "SYNTHETIC_REHEARSAL",
    "measured_value": 1.0,
    "as_of": "2026-06-30",
}


# --------------------------------------------------------------------------
# RFC 8785 — the number rules ECMAScript and Python disagree about
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (-0.0, "0"),
        (1, "1"),
        (1.0, "1"),
        (100.0, "100"),
        (1.5, "1.5"),
        (-1.5, "-1.5"),
        (0.1, "0.1"),
        (1e16, "10000000000000000"),
        (1e20, "100000000000000000000"),
        (1e21, "1e+21"),
        (1e-6, "0.000001"),
        (1e-7, "1e-7"),
        (333333333.33333329, "333333333.3333333"),
        (5e-324, "5e-324"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
    ],
)
def test_ecmascript_number_serialization(value: float, expected: str) -> None:
    assert serialize_number(value) == expected


def test_integral_floats_lose_their_decimal_point() -> None:
    """Python renders 100.0; ECMAScript renders 100. Signing the wrong one
    produces a signature a JavaScript verifier cannot reproduce."""
    assert repr(100.0) == "100.0"
    assert serialize_number(100.0) == "100"


def test_exponential_threshold_is_ecmascripts_not_pythons() -> None:
    """Python switches to exponential at 1e16; ECMAScript at 1e21."""
    assert repr(1e16) == "1e+16"
    assert serialize_number(1e16) == "10000000000000000"


def test_nan_and_infinity_cannot_be_signed() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalisationError, match="cannot be signed"):
            serialize_number(value)


def test_unsafe_integers_are_refused_rather_than_silently_narrowed() -> None:
    with pytest.raises(CanonicalisationError, match="exceeds the IEEE 754 safe range"):
        serialize_number(2**53 + 1)


def test_bool_is_not_a_number() -> None:
    with pytest.raises(CanonicalisationError, match="bool is not a JSON number"):
        serialize_number(True)
    assert canonicalise({"flag": True}) == '{"flag":true}'


def test_decimal_is_refused_rather_than_guessed() -> None:
    from decimal import Decimal

    with pytest.raises(CanonicalisationError, match="no canonical JSON number form"):
        canonicalise({"amount": Decimal("1.50")})


def test_object_keys_are_sorted_and_whitespace_is_absent() -> None:
    assert canonicalise({"b": 1, "a": 2, "C": 3}) == '{"C":3,"a":2,"b":1}'


def test_arrays_keep_their_order() -> None:
    """Only object keys may be reordered; array order carries meaning."""
    assert canonicalise([3, 1, 2]) == "[3,1,2]"


def test_keys_sort_by_utf16_code_unit_not_code_point() -> None:
    """A supplementary character encodes as a surrogate pair starting 0xD800,
    so it sorts before U+FB00 under UTF-16 and after under code point. Getting
    this wrong yields a signature two implementations disagree on."""
    payload = {"é": 1, "ﬀ": 2, "\U0001f600": 3}
    emitted = canonicalise(payload)
    assert emitted.index("é") < emitted.index("\U0001f600")
    assert emitted.index("\U0001f600") < emitted.index("ﬀ")
    assert sorted(payload) != ["é", "\U0001f600", "ﬀ"]


def test_control_characters_use_the_mandated_escapes() -> None:
    assert canonicalise("a\nb\tc\"d\\e") == '"a\\nb\\tc\\"d\\\\e"'
    assert canonicalise("\x01") == '"\\u0001"'


def test_non_ascii_is_emitted_literally() -> None:
    """JCS output is UTF-8; escaping non-ASCII would be valid JSON but not
    canonical JSON."""
    assert canonicalise("Ré") == '"Ré"'


def test_canonicalisation_does_not_round_unlike_the_reproducibility_canonicaliser() -> None:
    """The central reason this module exists separately from canonical.py."""
    from wallet_twin_v2.canonical import canonical_value

    value = 1234.56789
    assert canonical_value(value) == 1234.57
    assert serialize_number(value) == "1234.56789"


def test_unsupported_types_are_refused_rather_than_coerced() -> None:
    with pytest.raises(CanonicalisationError, match="will not guess"):
        canonicalise({"when": NOW})


# --------------------------------------------------------------------------
# DSSE
# --------------------------------------------------------------------------


def test_pae_binds_the_payload_type_to_the_body() -> None:
    assert pae("t", b"body") == b"DSSEv1 1 t 4 body"


def test_pae_length_prefixes_prevent_type_confusion() -> None:
    """Without length prefixes these two would encode identically."""
    assert pae("ab", b"c") != pae("a", b"bc")


def signer() -> LocalECDSASigner:
    return LocalECDSASigner.deterministic("local-rehearsal-p256", 42)


def test_a_signed_envelope_verifies() -> None:
    local = signer()
    envelope = sign_payload(PAYLOAD, local)
    verifier = LocalECDSAVerifier(local.key_id, local.public_key_pem())
    verified, reasons = verify_envelope(envelope, [verifier])
    assert verified
    assert reasons == ["SIGNATURE_VALID:local-rehearsal-p256"]


def test_a_tampered_payload_changes_the_digest_and_fails_verification() -> None:
    local = signer()
    envelope = sign_payload(PAYLOAD, local)
    tampered = Envelope(
        payload=base64.b64encode(
            canonical_bytes({**PAYLOAD, "measured_value": 0.5})
        ).decode("ascii"),
        payload_type=envelope.payload_type,
        signatures=envelope.signatures,
    )
    assert tampered.payload_sha256 != envelope.payload_sha256
    verifier = LocalECDSAVerifier(local.key_id, local.public_key_pem())
    verified, reasons = verify_envelope(tampered, [verifier])
    assert not verified
    assert "SIGNATURE_INVALID:local-rehearsal-p256" in reasons


def test_an_unknown_key_fails_closed() -> None:
    """Verification by absence would be the worst possible default."""
    envelope = sign_payload(PAYLOAD, signer())
    other = LocalECDSASigner.deterministic("some-other-key", 7)
    verifier = LocalECDSAVerifier(other.key_id, other.public_key_pem())
    verified, reasons = verify_envelope(envelope, [verifier])
    assert not verified
    assert "UNKNOWN_KEY:local-rehearsal-p256" in reasons


def test_an_envelope_with_no_signature_does_not_verify() -> None:
    verified, reasons = verify_envelope(unsigned_envelope(PAYLOAD), [])
    assert not verified
    assert reasons == ["NO_SIGNATURE_PRESENT"]


def test_payload_digests_are_stable_while_envelopes_differ() -> None:
    """ECDSA is randomised, so two signings of one payload give two envelopes.
    The digest is a property of the data; the envelope is a property of the
    signing event, and conflating them would make digests look unstable."""
    local = signer()
    first = sign_payload(PAYLOAD, local)
    second = sign_payload(PAYLOAD, local)
    assert first.payload_sha256 == second.payload_sha256 == payload_digest(PAYLOAD)
    assert first.signatures[0].sig != second.signatures[0].sig


def test_an_envelope_round_trips_through_its_dict_form() -> None:
    envelope = sign_payload(PAYLOAD, signer())
    assert Envelope.from_dict(envelope.as_dict()).payload_sha256 == envelope.payload_sha256


def test_key_ordering_does_not_change_the_digest() -> None:
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})


# --------------------------------------------------------------------------
# Trust registry — the invariant that matters
# --------------------------------------------------------------------------


def bank_key(**overrides) -> TrustedKey:
    payload = {
        "key_id": "aws-kms-bank",
        "algorithm": "ECDSA_SHA_256",
        "trust_domain": BANK_DOMAIN,
        "allowed_modes": frozenset({REAL_BANK, ATTESTED}),
        "allowed_environments": frozenset(
            {DeploymentEnvironment.SHADOW, DeploymentEnvironment.PRODUCTION}
        ),
        "allowed_roles": frozenset({"MODEL_RISK", "FINANCE_CONTROLLER"}),
        "not_before": NOW - timedelta(days=1),
        "not_after": NOW + timedelta(days=365),
    }
    payload.update(overrides)
    return TrustedKey(**payload)


def registry() -> TrustRegistry:
    return TrustRegistry(
        [
            rehearsal_key(
                "local-rehearsal-p256",
                not_before=NOW - timedelta(days=1),
                not_after=NOW + timedelta(days=90),
            ),
            bank_key(),
        ]
    )


def test_a_rehearsal_key_cannot_sign_real_bank_evidence() -> None:
    decision = registry().evaluate(
        "local-rehearsal-p256",
        mode=REAL_BANK,
        track=DecisionTrack.REAL,
        environment=DeploymentEnvironment.SHADOW,
        role="ENGINEERING",
        moment=NOW,
    )
    assert not decision
    assert "KEY_NOT_AUTHORISED_FOR_MODE:REAL_BANK" in decision.reason_codes


def test_a_rehearsal_key_signs_rehearsal_evidence() -> None:
    decision = registry().evaluate(
        "local-rehearsal-p256",
        mode=SYNTHETIC,
        track=DecisionTrack.REHEARSAL,
        environment=DeploymentEnvironment.FIXTURE,
        role="ENGINEERING",
        moment=NOW,
    )
    assert decision
    assert "TRUSTED:local-rehearsal-p256" in decision.reason_codes


def test_a_key_with_real_authority_cannot_sit_in_the_rehearsal_domain() -> None:
    """The misconfiguration that would make every other control ineffective."""
    with pytest.raises(TrustError, match="cannot confer bank authority"):
        bank_key(trust_domain=REHEARSAL_DOMAIN)


def test_synthetic_evidence_is_refused_on_the_real_track_even_with_a_valid_key() -> None:
    """Belt and braces: the mode algebra is checked independently of the key."""
    trust = TrustRegistry(
        [
            bank_key(
                key_id="over-broad",
                allowed_modes=frozenset({SYNTHETIC, REAL_BANK}),
                trust_domain=BANK_DOMAIN,
            )
        ]
    )
    decision = trust.evaluate(
        "over-broad",
        mode=SYNTHETIC,
        track=DecisionTrack.REAL,
        environment=DeploymentEnvironment.SHADOW,
        role="MODEL_RISK",
        moment=NOW,
    )
    assert not decision
    assert any(
        reason.startswith("MODE_NOT_ADMISSIBLE_ON_TRACK") for reason in decision.reason_codes
    )


def test_a_bank_trust_root_is_refused_in_a_fixture_environment() -> None:
    trust = TrustRegistry(
        [
            bank_key(
                allowed_environments=frozenset(
                    {DeploymentEnvironment.FIXTURE, DeploymentEnvironment.PRODUCTION}
                )
            )
        ]
    )
    decision = trust.evaluate(
        "aws-kms-bank",
        mode=REAL_BANK,
        track=DecisionTrack.REAL,
        environment=DeploymentEnvironment.FIXTURE,
        role="MODEL_RISK",
        moment=NOW,
    )
    assert not decision
    assert "BANK_TRUST_ROOT_REFUSED_IN_FIXTURE_ENVIRONMENT" in decision.reason_codes


def test_an_expired_key_fails() -> None:
    decision = registry().evaluate(
        "local-rehearsal-p256",
        mode=SYNTHETIC,
        track=DecisionTrack.REHEARSAL,
        environment=DeploymentEnvironment.FIXTURE,
        role="ENGINEERING",
        moment=NOW + timedelta(days=120),
    )
    assert not decision
    assert "KEY_OUTSIDE_VALIDITY_WINDOW" in decision.reason_codes


def test_a_key_used_before_its_validity_window_fails() -> None:
    decision = registry().evaluate(
        "local-rehearsal-p256",
        mode=SYNTHETIC,
        track=DecisionTrack.REHEARSAL,
        environment=DeploymentEnvironment.FIXTURE,
        role="ENGINEERING",
        moment=NOW - timedelta(days=30),
    )
    assert not decision
    assert "KEY_OUTSIDE_VALIDITY_WINDOW" in decision.reason_codes


def test_a_revoked_key_fails_from_the_moment_of_revocation() -> None:
    """Revocation is checked at verification time, so revoking invalidates
    future verifications of everything the key signed."""
    trust = TrustRegistry(
        [
            rehearsal_key(
                "revoked-key",
                not_before=NOW - timedelta(days=10),
                not_after=NOW + timedelta(days=90),
            )
        ]
    )
    revoked = TrustedKey(
        **{
            **trust.get("revoked-key").__dict__,
            "revoked_at": NOW,
        }
    )
    trust_with_revocation = TrustRegistry([revoked])
    args = dict(
        mode=SYNTHETIC,
        track=DecisionTrack.REHEARSAL,
        environment=DeploymentEnvironment.FIXTURE,
        role="ENGINEERING",
    )
    before = trust_with_revocation.evaluate(
        "revoked-key", moment=NOW - timedelta(hours=1), **args
    )
    after = trust_with_revocation.evaluate("revoked-key", moment=NOW, **args)
    assert before
    assert not after
    assert "KEY_REVOKED" in after.reason_codes


def test_an_unauthorised_role_cannot_sign() -> None:
    decision = registry().evaluate(
        "aws-kms-bank",
        mode=ATTESTED,
        track=DecisionTrack.REAL,
        environment=DeploymentEnvironment.PRODUCTION,
        role="ENGINEERING",
        moment=NOW,
    )
    assert not decision
    assert "ROLE_NOT_AUTHORISED:ENGINEERING" in decision.reason_codes


def test_all_failures_are_reported_together_not_one_at_a_time() -> None:
    decision = registry().evaluate(
        "local-rehearsal-p256",
        mode=REAL_BANK,
        track=DecisionTrack.REAL,
        environment=DeploymentEnvironment.PRODUCTION,
        role="CHIEF_RISK_OFFICER",
        moment=NOW + timedelta(days=200),
    )
    assert not decision
    assert len(decision.reason_codes) >= 4


def test_an_unknown_key_is_not_trusted() -> None:
    decision = registry().evaluate(
        "nonexistent",
        mode=SYNTHETIC,
        track=DecisionTrack.REHEARSAL,
        environment=DeploymentEnvironment.FIXTURE,
        role="ENGINEERING",
        moment=NOW,
    )
    assert not decision
    assert decision.reason_codes == ["UNKNOWN_KEY:nonexistent"]


def test_a_key_with_no_allowed_modes_is_refused_at_construction() -> None:
    with pytest.raises(TrustError, match="it can sign nothing"):
        bank_key(allowed_modes=frozenset())


def test_an_empty_validity_window_is_refused() -> None:
    with pytest.raises(TrustError, match="validity window is empty"):
        bank_key(not_after=NOW - timedelta(days=10))


def test_duplicate_registration_is_refused() -> None:
    trust = registry()
    with pytest.raises(TrustError, match="already registered"):
        trust.register(bank_key())


def test_assert_trusted_raises_with_the_reasons() -> None:
    with pytest.raises(TrustError, match="KEY_NOT_AUTHORISED_FOR_MODE"):
        registry().assert_trusted(
            "local-rehearsal-p256",
            mode=ATTESTED,
            track=DecisionTrack.REAL,
            environment=DeploymentEnvironment.PRODUCTION,
            role="MODEL_RISK",
            moment=NOW,
        )


def test_the_registry_document_publishes_no_private_material() -> None:
    document = registry().as_document()
    rendered = str(document)
    assert "PRIVATE KEY" not in rendered
    assert len(document["keys"]) == 2
    assert {item["trust_domain"] for item in document["keys"]} == {
        REHEARSAL_DOMAIN,
        BANK_DOMAIN,
    }


def test_a_public_domain_key_is_permitted_for_public_package_evidence() -> None:
    trust = TrustRegistry(
        [
            bank_key(
                key_id="sigstore-github-oidc",
                trust_domain=PUBLIC_DOMAIN,
                allowed_modes=frozenset({PUBLIC}),
                allowed_roles=frozenset({"ENGINEERING"}),
                allowed_environments=frozenset({DeploymentEnvironment.DEVELOPMENT}),
            )
        ]
    )
    assert trust.evaluate(
        "sigstore-github-oidc",
        mode=PUBLIC,
        track=DecisionTrack.REAL,
        environment=DeploymentEnvironment.DEVELOPMENT,
        role="ENGINEERING",
        moment=NOW,
    )


# --------------------------------------------------------------------------
# Signer capability is reported, never assumed
# --------------------------------------------------------------------------


def test_the_local_signer_is_the_only_one_executed_here() -> None:
    report = signer_capability_report()
    assert report["executed"] == ["LocalECDSASigner"]
    assert set(report["not_executed"]) == {"SigstoreSigner", "KMSSigner"}


def test_no_real_bank_signing_capability_exists_on_this_machine() -> None:
    """The honest headline: nothing here can sign real bank evidence."""
    assert signer_capability_report()["real_bank_signing_available"] is False


def test_sigstore_refuses_to_sign_rather_than_returning_plausible_bytes() -> None:
    with pytest.raises(SignatureError, match="must not be reported as if it had"):
        SigstoreSigner().sign(b"payload")


def test_kms_refuses_to_sign_without_a_configured_key() -> None:
    with pytest.raises(SignatureError, match="most dangerous shortcut"):
        KMSSigner().sign(b"payload")


def test_kms_reports_why_it_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROMOTION_KMS_KEY_ARN", raising=False)
    report = KMSSigner().capability_report()
    assert report["status"] == NOT_EXECUTED
    assert report["reason"] == "NO_KMS_KEY_ARN_CONFIGURED"


def test_the_local_signer_reports_it_cannot_satisfy_a_real_gate() -> None:
    report = LocalECDSASigner().capability_report()
    assert report["status"] == EXECUTED
    assert report["modes"] == ["SIMULATED_POLICY", "SYNTHETIC_REHEARSAL"]


def test_signer_allowed_modes_match_the_trust_model() -> None:
    """A signer's declared modes and the registry must not disagree."""
    assert LocalECDSASigner.allowed_modes == frozenset(
        {SYNTHETIC, PromotionEvidenceMode.SIMULATED_POLICY}
    )
    assert REAL_BANK not in SigstoreSigner.allowed_modes
    assert ATTESTED in KMSSigner.allowed_modes
