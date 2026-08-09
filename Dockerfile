FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:$PATH" \
    WALLET_DEPLOYMENT_MODE=CLIENT_DEMO \
    WALLET_SERVICE_APP=workbench_bff_app

RUN groupadd --gid 10001 wallet && useradd --uid 10001 --gid wallet --no-create-home wallet
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir uv==0.9.2 \
    && uv sync --frozen --no-dev --extra genai --extra production \
    && uv cache clean

USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"

CMD ["sh", "-c", "uvicorn wallet_twin_v2.service_apps:${WALLET_SERVICE_APP} --host 0.0.0.0 --port 8080 --proxy-headers --no-server-header"]
