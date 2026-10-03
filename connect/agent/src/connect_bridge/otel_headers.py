"""Puts the Dynatrace trace export header in place from Secrets Manager, then runs the command.

The bridge reports to the platform's Dynatrace tenant with the platform's token: its
environment carries the endpoint and the secret's ARN from the platform's
/guppi/platform/dynatrace-* parameters, and this launcher reads the token just before
`opentelemetry-instrument` reads `OTEL_EXPORTER_OTLP_TRACES_HEADERS` (guppi-hr D35, D36).
The endpoint parameter says "none" while the platform has no Dynatrace tenant; then the
endpoint is dropped and AgentCore's own exporter settings apply. A token that cannot be
read is reported on stderr and the command still starts.

    python -m connect_bridge.otel_headers opentelemetry-instrument uvicorn connect_bridge.app:app ...
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping

SECRET_ENV = "DYNATRACE_TOKEN_SECRET_ARN"
HEADERS_ENV = "OTEL_EXPORTER_OTLP_TRACES_HEADERS"
ENDPOINT_ENV = "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"


def headers(token: str) -> str:
    """The OTLP header value Dynatrace's ingest expects for an API token."""
    return f"Authorization=Api-Token {token.strip()}"


def environment(env: Mapping[str, str], fetch: Callable[[str], str]) -> dict[str, str]:
    """`env` with the trace export header from the secret `env` names, if any. The header
    replaces any value already set: AgentCore injects OTEL_* settings of its own, and the
    runtime variable this replaces used to override them the same way."""
    env = dict(env)
    if env.get(ENDPOINT_ENV) == "none":
        del env[ENDPOINT_ENV]
        env.pop(SECRET_ENV, None)
    arn = env.get(SECRET_ENV)
    if not arn:
        return env
    try:
        token = fetch(arn)
    except Exception as exc:  # noqa: BLE001 - any failure leaves the agent starting
        print(
            f"otel_headers: could not read {SECRET_ENV} ({type(exc).__name__}); "
            "trace export starts without its header",
            file=sys.stderr,
        )
        return env
    return {**env, HEADERS_ENV: headers(token)}


def fetch_secret(arn: str) -> str:
    import boto3

    return boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]


def main(argv: list[str] | None = None) -> None:
    command = list(sys.argv[1:] if argv is None else argv)
    if not command:
        raise SystemExit("usage: python -m connect_bridge.otel_headers <command> [args...]")
    os.execvpe(command[0], command, environment(os.environ, fetch_secret))


if __name__ == "__main__":
    main()
