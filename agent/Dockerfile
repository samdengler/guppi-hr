# AgentCore Runtime expects an arm64 image listening on 0.0.0.0:8080. The build context is
# this directory. The platform kit is a git dependency (kit-v0.2.0), so git is installed
# for the sync and the dependencies land in their own layer before the source.
FROM --platform=linux/arm64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --no-install-project

COPY src src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

EXPOSE 8080
# opentelemetry-instrument comes with the kit (aws-opentelemetry-distro), as in guppi-gpt.
CMD ["opentelemetry-instrument", "uvicorn", "connect_bridge.app:app", "--host", "0.0.0.0", "--port", "8080"]
