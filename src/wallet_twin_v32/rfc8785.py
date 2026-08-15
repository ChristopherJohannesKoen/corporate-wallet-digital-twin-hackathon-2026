"""RFC 8785 JSON Canonicalization Scheme — for signing, and only for signing.

**This module exists because ``wallet_twin_v2.canonical`` must never sign a
payload.** That module deliberately *rounds* floats to the published precision
(two decimals above 1000, eight below) and emits ``indent=2`` with a trailing
newline. Both behaviours are correct for their purpose — they remove BLAS and
platform noise so committed artifacts reproduce byte-identically across
machines — and both are disqualifying for a signature:

- Signing a rounded payload signs a **different number** than the one
  published. A verifier recomputing the digest from the published value gets a
  different answer, and the failure looks like tampering.
- RFC 8785 mandates no whitespace and forbids altering values.

So: ``canonical.py`` for reproducibility, ``rfc8785.py`` for signatures. They
are not interchangeable and neither should grow toward the other.

The hard part of JCS is number serialization. JSON numbers are IEEE 754
doubles, and the canonical form is ECMAScript's ``Number::toString`` — the
*shortest* representation that round-trips, with specific rules about when to
switch to exponential notation. Python's ``repr`` is also shortest-round-trip
but differs from ECMAScript in two ways that matter: it renders integral floats
as ``100.0`` where ECMAScript gives ``100``, and it switches to exponential at
1e16 where ECMAScript switches at 1e21. Both differences change the bytes, and
therefore the signature. :func:`serialize_number` implements the ECMAScript
algorithm rather than patching ``repr``.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Mapping, Sequence

JCS_VERSION = "rfc8785-jcs-1.0.0"

#: Beyond this, an integer is not exactly representable as an IEEE 754 double,
#: so a JavaScript verifier would read a different value than Python wrote.
#: Signing such a number would produce a signature that cannot be verified
#: interoperably, which is worse than refusing to sign it.
MAX_SAFE_INTEGER = 2**53 - 1

#: Short escapes mandated by JCS. Everything else below 0x20 uses \uXXXX.
_SHORT_ESCAPES = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


class CanonicalisationError(ValueError):
    """A value cannot be canonicalised without changing what it means."""


def serialize_number(value: float | int) -> str:
    """ECMAScript ``Number::toString`` for a JSON number.

    Implements the algorithm from ECMA-262 §6.1.6.1.20 directly. ``repr`` gives
    the shortest round-tripping digits; the rules below decide how to lay them
    out, which is where Python and ECMAScript disagree.
    """
    if isinstance(value, bool):
        # bool is an int subclass in Python. Reaching here means a caller tried
        # to serialize True as a number, which would silently become 1.
        raise CanonicalisationError("bool is not a JSON number")

    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise CanonicalisationError(
                f"integer {value} exceeds the IEEE 754 safe range; a JavaScript "
                "verifier would read a different value, so this payload cannot "
                "be signed interoperably"
            )
        return str(value)

    if not math.isfinite(value):
        raise CanonicalisationError(
            f"{value} has no JSON representation; NaN and Infinity cannot be "
            "signed"
        )

    if value == 0:
        # Covers -0.0, which ECMAScript renders as "0".
        return "0"

    sign = "-" if value < 0 else ""
    # normalize() strips the trailing zeros repr() leaves on integral floats,
    # so 100.0 yields digits (1,) exponent 2 rather than (1,0,0,0) exponent -1.
    decimal_value = Decimal(repr(abs(value))).normalize()
    _, digit_tuple, exponent = decimal_value.as_tuple()
    digits = "".join(str(digit) for digit in digit_tuple)
    k = len(digits)
    n = int(exponent) + k  # position of the decimal point

    if k <= n <= 21:
        return sign + digits + "0" * (n - k)
    if 0 < n <= 21:
        return sign + digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + digits
    # Exponential notation.
    exponent_part = n - 1
    exponent_sign = "+" if exponent_part >= 0 else "-"
    mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
    return f"{sign}{mantissa}e{exponent_sign}{abs(exponent_part)}"


def serialize_string(value: str) -> str:
    """JCS string form: minimal escaping, no \\u for non-ASCII.

    Output is UTF-8, so non-ASCII characters are emitted literally. Escaping
    them would still be valid JSON but would not be *canonical* JSON, and two
    implementations disagreeing on that produce two different signatures over
    the same data.
    """
    out = ['"']
    for character in value:
        code = ord(character)
        escape = _SHORT_ESCAPES.get(code)
        if escape is not None:
            out.append(escape)
        elif code < 0x20:
            out.append(f"\\u{code:04x}")
        else:
            out.append(character)
    out.append('"')
    return "".join(out)


def _utf16_sort_key(key: str) -> bytes:
    """Sort key ordering by UTF-16 code unit, as JCS requires.

    Python sorts strings by code point, which differs from UTF-16 code-unit
    order for characters above the BMP: a supplementary character encodes as a
    surrogate pair beginning 0xD800-0xDBFF, so it sorts *before* U+E000-U+FFFF
    under UTF-16 and *after* under code point. Encoding to UTF-16 big-endian
    and comparing bytes reproduces the required order exactly.
    """
    return key.encode("utf-16-be", errors="surrogatepass")


def canonicalise(value: Any) -> str:
    """Serialize a value to its RFC 8785 canonical JSON form.

    Values are never altered — no rounding, no coercion, no reordering of
    arrays. Only object keys are reordered, which JSON semantics permit.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return serialize_string(value)
    if isinstance(value, (int, float)):
        return serialize_number(value)
    if isinstance(value, Mapping):
        items = sorted(value.items(), key=lambda pair: _utf16_sort_key(str(pair[0])))
        rendered = ",".join(
            f"{serialize_string(str(key))}:{canonicalise(item)}" for key, item in items
        )
        return "{" + rendered + "}"
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "[" + ",".join(canonicalise(item) for item in value) + "]"
    if isinstance(value, Decimal):
        raise CanonicalisationError(
            "Decimal has no canonical JSON number form; convert to float or "
            "str at the boundary so the intended precision is explicit"
        )
    raise CanonicalisationError(
        f"{type(value).__name__} is not JSON; canonicalisation will not guess "
        "a representation for a value it does not understand"
    )


def canonical_bytes(value: Any) -> bytes:
    """UTF-8 bytes of the canonical form — what actually gets signed."""
    return canonicalise(value).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """SHA-256 over the canonical bytes."""
    import hashlib

    return hashlib.sha256(canonical_bytes(value)).hexdigest()


__all__ = [
    "JCS_VERSION",
    "MAX_SAFE_INTEGER",
    "CanonicalisationError",
    "canonical_bytes",
    "canonical_sha256",
    "canonicalise",
    "serialize_number",
    "serialize_string",
]
