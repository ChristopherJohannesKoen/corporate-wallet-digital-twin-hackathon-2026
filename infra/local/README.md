# Local production-equivalent control harness

This Compose stack exercises service contracts and operational controls without claiming equivalence to a bank environment. It provides pinned PostgreSQL, Redpanda, MinIO, OPA, OpenTelemetry and local identity/CRM doubles. Spark is optional through the `delta` profile.

```powershell
docker compose -f infra/local/docker-compose.yml config
docker compose -f infra/local/docker-compose.yml up -d --wait
python scripts/run_shadow_replay.py
docker compose -f infra/local/docker-compose.yml down
```

All ports bind to loopback. Credentials are local fixture values only. GenAI defaults to deterministic mode. The stack does not satisfy bank SSO, Unity Catalog, SIEM, penetration-test, resiliency or independent-approval gates.
