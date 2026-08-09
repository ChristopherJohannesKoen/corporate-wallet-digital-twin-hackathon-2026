from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .contracts import EventEnvelope


class PostgresTransactionalOutbox:
    """Write workflow state and its event atomically; publisher drains later."""

    def __init__(self, dsn: str, *, schema: str = "experiment") -> None:
        if not schema.replace("_", "").isalnum():
            raise ValueError("invalid schema name")
        self.dsn = dsn
        self.schema = schema

    def append(self, event: EventEnvelope) -> None:
        import psycopg

        payload = json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        with psycopg.connect(self.dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {self.schema}.event_outbox(event_id, event_type, payload, occurred_at, published_at)
                VALUES (%s, %s, %s::jsonb, %s, NULL)
                ON CONFLICT (event_id) DO NOTHING
                """,
                (event.event_id, event.event_type.value, payload, event.occurred_at),
            )

    def health(self) -> dict:
        import psycopg

        with psycopg.connect(self.dsn, connect_timeout=3) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            healthy = cursor.fetchone() == (1,)
        return {"component": "postgres", "healthy": healthy}


class KafkaEventPublisher:
    def __init__(self, brokers: str, *, client_id: str) -> None:
        from confluent_kafka import Producer

        self.producer = Producer({
            "bootstrap.servers": brokers,
            "client.id": client_id,
            "enable.idempotence": True,
            "acks": "all",
            "security.protocol": "SASL_SSL",
        })

    def publish(self, topic: str, events: Iterable[EventEnvelope]) -> int:
        published = 0
        for event in events:
            payload = json.dumps(event.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.producer.produce(topic, key=event.event_id.encode("utf-8"), value=payload)
            published += 1
        self.producer.flush(10)
        return published


class ImmutableS3DocumentStore:
    def __init__(self, bucket: str, kms_key_arn: str) -> None:
        import boto3

        self.bucket = bucket
        self.kms_key_arn = kms_key_arn
        self.client = boto3.client("s3")

    def put(self, content: bytes, *, source_name: str, retention_days: int = 2_555) -> dict:
        digest = hashlib.sha256(content).hexdigest()
        key = f"source-documents/sha256/{digest[:2]}/{digest}.bin"
        retention = datetime.now(timezone.utc) + timedelta(days=retention_days)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=self.kms_key_arn,
            ObjectLockMode="COMPLIANCE",
            ObjectLockRetainUntilDate=retention,
            Metadata={"sha256": digest, "source-name-sha256": hashlib.sha256(source_name.encode()).hexdigest()},
        )
        return {"bucket": self.bucket, "key": key, "sha256": digest, "retained_until": retention.isoformat()}


class KMSManifestSigner:
    """Asymmetric KMS signer for evidence and release manifests."""

    def __init__(self, key_arn: str) -> None:
        if not key_arn.startswith("arn:aws:kms:"):
            raise ValueError("KMS signing key ARN required")
        import boto3

        self.key_arn = key_arn
        self.client = boto3.client("kms")

    def sign(self, payload: bytes) -> dict:
        import base64

        digest = hashlib.sha256(payload).digest()
        response = self.client.sign(
            KeyId=self.key_arn,
            Message=digest,
            MessageType="DIGEST",
            SigningAlgorithm="RSASSA_PSS_SHA_256",
        )
        return {
            "key_id": response["KeyId"],
            "algorithm": response["SigningAlgorithm"],
            "signature_base64": base64.b64encode(response["Signature"]).decode("ascii"),
            "message_sha256": hashlib.sha256(payload).hexdigest(),
        }
