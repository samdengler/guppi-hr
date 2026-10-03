"""Puts the Dynatrace trace export header in place from Secrets Manager, then runs the command.

The runtime's environment carries only `DYNATRACE_TOKEN_SECRET_ARN`; the API token stays in
Secrets Manager and enters this process's environment just before `opentelemetry-instrument`
reads `OTEL_EXPORTER_OTLP_TRACES_HEADERS` (D35). Without the ARN, as on the tools server and
the sub-agents, the command runs with the environment unchanged. A token that cannot be read
is reported on stderr and the command still starts: trace export then fails, the agent does
not.

    python -m hr_agent.otel_headers opentelemetry-instrument python -m hr_agent
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping

SECRET_ENV = "DYNATRACE_TOKEN_SECRET_ARN"
HEADERS_ENV = "OTEL_EXPORTER_OTLP_TRACES_HEADERS"


def headers(token: str) -> str:
    """The OTLP header value Dynatrace's ingest expects for an API token."""
    return f"Authorization=Api-Token {token.strip()}"


def environment(env: Mapping[str, str], fetch: Callable[[str], str]) -> dict[str, str]:
    """`env` with the trace export header added from the secret `env` names, if any."""
    arn = env.get(SECRET_ENV)
    if not arn or env.get(HEADERS_ENV):
        return dict(env)
    try:
        token = fetch(arn)
    except Exception as exc:  # noqa: BLE001 - any failure leaves the agent starting
        print(
            f"otel_headers: could not read {SECRET_ENV} ({type(exc).__name__}); "
            "trace export starts without its header",
            file=sys.stderr,
        )
        return dict(env)
    return {**env, HEADERS_ENV: headers(token)}


def fetch_secret(arn: str) -> str:
    import boto3

    return boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]


def main(argv: list[str] | None = None) -> None:
    command = list(sys.argv[1:] if argv is None else argv)
    if not command:
        raise SystemExit("usage: python -m hr_agent.otel_headers <command> [args...]")
    os.execvpe(command[0], command, environment(os.environ, fetch_secret))


if __name__ == "__main__":
    main()
