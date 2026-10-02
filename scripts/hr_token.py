# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3"]
# ///
"""Mint an hr-super-agent access token from a refresh token, for real sub-agent tests.

Reads ~/.config/guppi-connect/hr_refresh_token (copied by Sam from a signed-in
hr.dengler.io session) and writes a fresh access token to
~/.config/guppi-connect/hr_access_token, both mode 600. The pool rotates refresh tokens,
so each run also stores the new refresh token, and the browser's copy stops working. The client id is the HR page's
public Cognito client from hr-super-agent's cdk-outputs.json; the gateways accept only
that client's tokens. Neither token is printed.

    uv run scripts/hr_token.py
    uv run scripts/chat.py --flow production --token-file ~/.config/guppi-connect/hr_access_token "..."
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path.home() / ".config" / "guppi-connect"


def write_private(path: Path, value: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(value)


def main() -> None:
    outputs = next(iter(json.loads((ROOT.parent / "hr-super-agent" / "cdk-outputs.json").read_text()).values()))
    refresh = (CONFIG / "hr_refresh_token").read_text().strip()
    # The HR pool rotates refresh tokens, which InitiateAuth refuses
    # ("This API does not support refresh token rotation"); GetTokensFromRefreshToken
    # returns a new refresh token as well, which replaces the old one in the file.
    result = boto3.client("cognito-idp", region_name="us-east-1").get_tokens_from_refresh_token(
        RefreshToken=refresh,
        ClientId=outputs["UserPoolClientId"],
    )["AuthenticationResult"]
    write_private(CONFIG / "hr_access_token", result["AccessToken"])
    if result.get("RefreshToken"):
        write_private(CONFIG / "hr_refresh_token", result["RefreshToken"])
    target = CONFIG / "hr_access_token"
    print(f"wrote {target} ({len(result['AccessToken'])} chars, expires in {result['ExpiresIn']} s)")


if __name__ == "__main__":
    main()
