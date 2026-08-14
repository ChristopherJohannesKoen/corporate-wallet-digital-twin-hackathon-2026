#!/bin/sh
# MinIO bucket bootstrap with object lock.
#
# Before V3.2 there was no bucket creation step at all, so every "immutable
# evidence" claim rested on a bucket nobody had created with a retention mode
# nobody had set.
#
# Object lock can only be enabled AT BUCKET CREATION. There is no command to
# turn it on afterwards, and a bucket created without it looks identical in
# every listing to one created with it. That asymmetry is why this belongs in
# an automated bootstrap rather than a runbook step: the failure is silent, and
# it is discovered when someone tries to prove an object could not have been
# altered and finds they cannot.
#
# The verification block at the end is the point of the script. Creating the
# bucket is easy; proving the lock took effect is what makes the claim
# defensible.

set -eu

ENDPOINT="${MINIO_ENDPOINT:-http://minio:9000}"
RETENTION_DAYS="${EVIDENCE_RETENTION_DAYS:-2555}"

# Buckets that hold evidence a regulator may later ask about. COMPLIANCE mode
# rather than GOVERNANCE: GOVERNANCE retention can be bypassed by a user with
# the right permission, which makes it an operational safeguard rather than an
# immutability guarantee.
LOCKED_BUCKETS="wallet-twin-evidence wallet-twin-promotion-evidence wallet-twin-audit"

# Buckets holding regenerable working data. Locking these would make ordinary
# operation impossible without adding any assurance, and over-applying
# immutability is how teams end up disabling it entirely.
UNLOCKED_BUCKETS="wallet-twin-mlflow wallet-twin-scratch"

echo "==> configuring mc alias"
mc alias set local "$ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null

echo "==> creating locked buckets (object lock, COMPLIANCE, ${RETENTION_DAYS}d)"
for bucket in $LOCKED_BUCKETS; do
  if mc ls "local/$bucket" >/dev/null 2>&1; then
    echo "    $bucket already exists"
  else
    # --with-lock is only honoured at creation.
    mc mb --with-lock "local/$bucket"
    echo "    created $bucket with object lock"
  fi
  mc retention set --default COMPLIANCE "${RETENTION_DAYS}d" "local/$bucket"
  mc version enable "local/$bucket" >/dev/null 2>&1 || true
done

echo "==> creating unlocked working buckets"
for bucket in $UNLOCKED_BUCKETS; do
  mc mb --ignore-existing "local/$bucket" >/dev/null
  echo "    $bucket ready"
done

# ---------------------------------------------------------------------------
# Verification. A bootstrap that only creates things cannot detect the case it
# exists to prevent.
#
# The minio/mc image ships almost no userland — no grep, sed or awk, only cat
# and tr — so matching is done with POSIX `case`. That is a constraint worth
# stating: a verification step written against tools the image lacks fails in a
# way that looks like the thing it was checking had failed.
# ---------------------------------------------------------------------------
echo "==> verifying object lock actually took effect"
failed=0

for bucket in $LOCKED_BUCKETS; do
  info="$(mc retention info "local/$bucket" 2>&1 || true)"
  case "$info" in
    *COMPLIANCE*) echo "    ok: $bucket COMPLIANCE retention set" ;;
    *)
      echo "    FAIL: $bucket has no COMPLIANCE retention"
      echo "          mc reported: $info"
      failed=1
      ;;
  esac
done

# The decisive test: write an object, then try to remove it permanently.
#
# A plain `mc rm` is NOT the right probe. With versioning enabled it writes a
# delete marker and returns success — correct S3 behaviour, and it says nothing
# about retention, because the underlying version is still there and still
# retained. Using it would report a failure on a correctly locked bucket.
#
# `mc rm --versions --force` attempts to remove every version, which is exactly
# what COMPLIANCE retention must refuse.
probe_object="bootstrap-immutability-probe.txt"
probe="local/wallet-twin-evidence/$probe_object"

if ! echo "immutability probe written by minio_object_lock.sh" | mc pipe "$probe" >/dev/null 2>&1; then
  echo "    FAIL: could not write the probe object; the check below would be vacuous"
  failed=1
else
  removal="$(mc rm --versions --force "$probe" 2>&1 || true)"
  # A refusal mentions the retention/WORM protection; a success prints "Removed".
  case "$removal" in
    *Removed*|*removed*)
      echo "    FAIL: every version of a retained object was deleted"
      echo "          mc reported: $removal"
      failed=1
      ;;
    *)
      echo "    ok: permanent deletion of a retained object was refused"
      ;;
  esac
fi

if [ "$failed" -ne 0 ]; then
  echo "==> MinIO object-lock bootstrap FAILED"
  echo "    Object lock cannot be enabled on an existing bucket. If these"
  echo "    buckets were created without --with-lock, they must be recreated:"
  echo "    docker compose down -v && docker compose up -d"
  exit 1
fi

echo "==> MinIO object-lock bootstrap complete"
echo "    locked:   $LOCKED_BUCKETS"
echo "    unlocked: $UNLOCKED_BUCKETS"
