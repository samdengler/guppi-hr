# AgentCore Runtime expects an arm64 image. One image serves every runtime (D11):
# AGENT_ROLE picks the orchestrator (AG-UI on 8080), the tools server (MCP on 8000), or a
# sub-agent (A2A on 9000).
# Build context is the repository root (see the CDK stack and .dockerignore) so the
# workspace lockfile is visible: dependencies install from it in their own layer, which
# Docker reuses until uv.lock or a pyproject changes, and the source lands in a small
# layer of its own afterwards.
FROM --platform=linux/arm64 python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
# git, because the platform kit (guppi-agent) is a git dependency in uv.lock, and uv fetches
# git sources with the git executable (D29).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Workspace metadata only: the root project, the lockfile, and each member's pyproject
# (uv refuses to resolve a workspace with a member missing).
COPY pyproject.toml uv.lock ./
COPY agent/pyproject.toml agent/README.md agent/
COPY infra/pyproject.toml infra/
# The cache mount keeps uv's downloads on the build host, outside the image, so a
# lockfile change fetches only what changed (needs BuildKit, which docker-buildx provides).
# guppi-gpt is a private repository: the build secret github_token (the stack passes it from
# HR_GITHUB_TOKEN, which scripts/deploy.sh sets from `gh auth token`) reaches git only
# through environment configuration for this one command, so it is in no layer, file or
# cache entry (D29). Without the secret the fetch fails as it would for any private repo.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=github_token,required=false \
    if [ -s /run/secrets/github_token ]; then \
        export GIT_CONFIG_COUNT=1 \
            GIT_CONFIG_KEY_0="url.https://x-access-token:$(cat /run/secrets/github_token)@github.com/.insteadOf" \
            GIT_CONFIG_VALUE_0="https://github.com/"; \
    fi; \
    uv sync --frozen --package hr-agent --no-dev --no-editable --no-install-workspace

# The agent itself. Only this layer and the sync below rerun on a source change.
COPY agent/src agent/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package hr-agent --no-dev --no-editable

EXPOSE 8080 8000 9000
# Prime each server before it listens, so AgentCore Runtime V2's snapshot holds the
# imports and clients (hr_agent/prime.py).
ENV HR_PRIME=1
# opentelemetry-instrument (from aws-opentelemetry-distro, a hr-agent dependency) is
# the documented AgentCore entrypoint wrapper: it installs the ADOT tracer provider and
# the FastAPI, httpx, MCP, and botocore instrumentation before the app is imported,
# so one trace covers the request, the Strands run, the tools gateway call, and the
# Bedrock call. The runtime supplies the exporter settings as environment variables
# (AGENT_OBSERVABILITY_ENABLED and OTEL_*). Local development starts uvicorn directly
# (AGENTS.md) and needs none of this. See docs/proposals/traceability.md.
# hr_agent.otel_headers puts the Dynatrace trace header in place from Secrets Manager
# first, when the runtime names the secret, then execs the command (D35).
CMD ["python", "-m", "hr_agent.otel_headers", "opentelemetry-instrument", "python", "-m", "hr_agent"]
