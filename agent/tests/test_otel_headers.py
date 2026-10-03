"""The launcher that takes the Dynatrace token from Secrets Manager (D35)."""

from __future__ import annotations

import pytest

from hr_agent import otel_headers
from hr_agent.otel_headers import HEADERS_ENV, SECRET_ENV, environment


def never(arn: str) -> str:
    raise AssertionError("the secret must not be read")


def test_the_header_comes_from_the_secret_the_runtime_names():
    seen = []

    def fetch(arn: str) -> str:
        seen.append(arn)
        return "dt0c01.example\n"

    env = environment({SECRET_ENV: "arn:secret", "KEEP": "1"}, fetch)
    assert seen == ["arn:secret"]
    assert env[HEADERS_ENV] == "Authorization=Api-Token dt0c01.example"
    assert env["KEEP"] == "1"


def test_without_the_arn_the_environment_is_unchanged():
    assert environment({"KEEP": "1"}, never) == {"KEEP": "1"}


def test_a_header_already_set_is_kept():
    env = {SECRET_ENV: "arn:secret", HEADERS_ENV: "Authorization=Api-Token set"}
    assert environment(env, never) == env


def test_a_secret_that_cannot_be_read_still_starts_the_command(capsys):
    def fetch(arn: str) -> str:
        raise RuntimeError("AccessDenied dt0c01.never-printed")

    env = environment({SECRET_ENV: "arn:secret"}, fetch)
    assert HEADERS_ENV not in env
    err = capsys.readouterr().err
    assert "RuntimeError" in err
    assert "dt0c01" not in err


def test_main_runs_the_command_with_the_new_environment(monkeypatch):
    calls = []
    monkeypatch.setattr(otel_headers, "fetch_secret", lambda arn: "tok")
    monkeypatch.setattr(otel_headers.os, "environ", {SECRET_ENV: "arn:secret"})
    monkeypatch.setattr(
        otel_headers.os, "execvpe", lambda file, args, env: calls.append((file, args, env))
    )
    otel_headers.main(["opentelemetry-instrument", "python", "-m", "hr_agent"])
    file, args, env = calls[0]
    assert file == "opentelemetry-instrument"
    assert args == ["opentelemetry-instrument", "python", "-m", "hr_agent"]
    assert env[HEADERS_ENV] == "Authorization=Api-Token tok"


def test_main_needs_a_command():
    with pytest.raises(SystemExit):
        otel_headers.main([])
