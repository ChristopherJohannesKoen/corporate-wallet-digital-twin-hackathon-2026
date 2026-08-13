"""Published precision and reproducible stamping for committed artifacts.

Canonicalisation is not build tooling — it *defines the precision at which the
system publishes a number*, so it lives in ``src`` beside the models rather than
in ``scripts``, and it is unit-testable and importable from anywhere.

Two policies are kept deliberately separate:

``CANONICALISATION_VERSION``
    The published-artifact precision. Currency at cent precision, ratios and
    probabilities at eight decimals. This removes platform/BLAS noise without
    changing any decision-relevant value.

``DIGEST_PRECISION_VERSION``
    The coarser precision used for regression-boundary digests. Hashing at full
    binary precision would make the frozen boundary fail after a harmless NumPy
    upgrade.

Collapsing the two would either make the V3.0 boundary hypersensitive to
eighth-decimal noise or make the published fixture lossy for probabilities.

Reproducible stamping
---------------------
A committed artifact must not embed the wall-clock time at which it was built —
otherwise it can never be reproduced byte-identically, and a
``git diff --exit-code`` reproducibility gate becomes unsatisfiable. These are
point-in-time artifacts, so they are stamped with the model ``as_of`` instant.
Real build time belongs in the submission manifest, which is not a diffed
artifact.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import date, datetime, time, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

CANONICALISATION_VERSION = "v1-published-precision"
DIGEST_PRECISION_VERSION = "v1-boundary-2dp"

#: The governed point-in-time date of the demonstration. Committed artifacts are
#: stamped at this instant so a rebuild is byte-identical.
ARTIFACT_AS_OF = date(2026, 6, 30)

#: Escape hatch for reproducible-build tooling, mirroring SOURCE_DATE_EPOCH.
BUILD_STAMP_ENV = "WALLET_ARTIFACT_TIMESTAMP"

LONG_DECIMAL = re.compile(r"^-?\d+\.\d{9,}$")


def artifact_timestamp() -> str:
    """The deterministic stamp committed artifacts carry.

    Overridable via ``WALLET_ARTIFACT_TIMESTAMP`` for tooling that needs to pin a
    different instant; otherwise it is midnight UTC on the model ``as_of``.
    """
    override = os.getenv(BUILD_STAMP_ENV)
    if override:
        return override
    return datetime.combine(ARTIFACT_AS_OF, time.min, tzinfo=timezone.utc).isoformat()


#: Fields that record *when a run happened* rather than *what it contained*.
#: A reproducibility digest must exclude them: an event legitimately occurs at a
#: wall-clock instant, but a content hash that changes every run cannot detect
#: content drift, which is the only thing it exists to do.
VOLATILE_FIELDS = frozenset(
    {"occurred_at", "recorded_at", "ingestion_time", "evaluated_at", "generated_at", "received_at"}
)


#: Per-run identifiers. A freshly minted UUID carries no business meaning, so a
#: content digest over an event stream must exclude it as well as the emission
#: instant — otherwise the digest is a random number.
RUN_IDENTIFIER_FIELDS = frozenset({"event_id", "correlation_id", "idempotency_key"})

#: The exclusion set for hashing an emitted event stream.
EVENT_STREAM_VOLATILE_FIELDS = VOLATILE_FIELDS | RUN_IDENTIFIER_FIELDS


def strip_volatile(value: Any, fields: frozenset[str] = VOLATILE_FIELDS) -> Any:
    """Remove run-time-only fields so a payload can be content-hashed."""
    if isinstance(value, dict):
        return {
            key: strip_volatile(item, fields)
            for key, item in value.items()
            if key not in fields
        }
    if isinstance(value, list):
        return [strip_volatile(item, fields) for item in value]
    return value


#: Fields holding a measured wall-clock duration on the build machine. They are
#: real measurements and belong in the validation reports, but they must not be
#: embedded in a committed fixture: the fixture is reproducibility-gated, and a
#: machine timing can never reproduce byte-identically on another host.
MACHINE_MEASUREMENT_FIELDS = frozenset(
    {
        "latency_ms",
        "local_p95_latency_ms",
        "duration_ms",
        "elapsed_ms",
        "throughput_requests_per_second",
    }
)

MEASUREMENT_REDACTED = "MEASURED_AT_BUILD_TIME_SEE_VALIDATION_REPORT"


def redact_machine_measurements(
    value: Any, fields: frozenset[str] = MACHINE_MEASUREMENT_FIELDS
) -> Any:
    """Replace measured host timings with a stable marker.

    The governed *verdict* (did the p95 meet its budget?) stays in the payload;
    only the host-specific number is redacted, and the full measurement remains
    in ``outputs/v2_validation/``.
    """
    if isinstance(value, dict):
        return {
            key: (MEASUREMENT_REDACTED if key in fields else redact_machine_measurements(item, fields))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_machine_measurements(item, fields) for item in value]
    return value


def content_digest(payload: Any, fields: frozenset[str] = VOLATILE_FIELDS) -> str:
    """Stable SHA-256 over the business content of a payload."""
    import hashlib

    canonical = json.dumps(
        strip_volatile(canonical_value(payload), fields),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_value(value: Any) -> Any:
    """Round a payload to the published precision of the artifact.

    Portfolio currency values are displayed at cent precision; ratios and
    probabilities retain eight decimals. This removes BLAS/platform noise
    without changing any decision-relevant value.
    """
    if isinstance(value, dict):
        return {key: canonical_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [canonical_value(item) for item in value]
    if isinstance(value, float) and math.isfinite(value):
        if abs(value) < 0.0000001:
            return 0.0
        return round(value, 2 if abs(value) >= 1_000 else 8)
    if isinstance(value, str) and LONG_DECIMAL.fullmatch(value):
        rounded = Decimal(value).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)
        return format(rounded, "f")
    return value


def digest_value(value: Any) -> Any:
    """Coarser canonicalisation used for regression-boundary digests."""
    if isinstance(value, dict):
        return {key: digest_value(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [digest_value(item) for item in value]
    if isinstance(value, float):
        return round(value, 2)
    return value


def canonical_json(payload: Any) -> str:
    """Serialise at published precision, deterministically."""
    return json.dumps(canonical_value(payload), indent=2, sort_keys=True) + "\n"


def write_canonical_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(payload), encoding="utf-8")


def is_canonical(payload: Any) -> bool:
    """True when a parsed artifact is already at published precision."""
    return canonical_value(payload) == payload
