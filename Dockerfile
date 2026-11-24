FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 app
USER app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "training_mcp.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
