# sandbox: 1 イメージで MCP サーバ / A2A エージェントの両方を動かす
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# どの役割で動くかは SERVICE_KIND / SERVICE_NAME 環境変数で決まる
CMD ["uvicorn", "sandbox.main:app", "--host", "0.0.0.0", "--port", "8000"]
