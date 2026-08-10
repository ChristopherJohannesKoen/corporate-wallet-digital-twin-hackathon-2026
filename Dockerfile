FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:$PATH" \
    WALLET_DEPLOYMENT_MODE=CLIENT_DEMO \
    WALLET_SERVICE_APP=workbench_bff_app

RUN apt-get update \
    && apt-get upgrade --yes \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 wallet \
    && useradd --uid 10001 --gid wallet --no-create-home wallet
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir uv==0.9.2 \
    && uv sync --frozen --no-dev --extra genai --extra production \
    && uv cache clean

# The runtime fixture is aggregate, public/representative judging data only.
# Raw Syn Bank rows and downloaded issuer documents are deliberately excluded.
COPY data/public_facts.csv ./data/public_facts.csv
COPY data/v2/benchmark_rate_cards.json data/v2/external_dataset_registry.json data/v2/public_facts_expanded.csv data/v2/public_sources.json data/v2/representative_trade_finance_summary.json ./data/v2/
COPY data/v2/golden_set/cases.jsonl ./data/v2/golden_set/cases.jsonl
COPY data/v3/public_sensor_registry.json ./data/v3/public_sensor_registry.json
COPY legacy/v1/fixtures/portfolio.json ./legacy/v1/fixtures/portfolio.json

USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"

CMD ["sh", "-c", "uvicorn wallet_twin_v2.service_apps:${WALLET_SERVICE_APP} --host 0.0.0.0 --port 8080 --proxy-headers --no-server-header"]
