"""Who is calling a tool.

The tools gateway signs its calls to this runtime with its own role (D19), so the
runtime's own authorizer says nothing about the user. The caller sends the user's access
token a second time in `X-Hr-User-Token`, the gateway target forwards it, and this module
verifies it independently: signature against the issuer's keys, issuer, expiry, token use,
and client. Nothing here trusts the gateway for identity. Issuer, keys, clients, and the
optional audience are environment settings, so an exchanged on-behalf-of token (D20)
needs configuration, not code.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import jwt

USER_TOKEN_HEADER = "x-hr-user-token"
THREAD_HEADER = "x-hr-thread-id"
TRACE_HEADER = "traceparent"
FORWARDED_HEADERS = (USER_TOKEN_HEADER, THREAD_HEADER, TRACE_HEADER)


class IdentityError(Exception):
    """The request carries no usable user token."""


@dataclass(frozen=True)
class Caller:
    sub: str
    thread_id: str | None
    trace_id: str | None


KeyResolver = Callable[[str], Any]


class TokenVerifier:
    def __init__(
        self,
        issuer: str,
        allowed_clients: frozenset[str],
        key_for: KeyResolver,
        token_use: str = "access",
        audience: str | None = None,
    ) -> None:
        if not allowed_clients and not audience:
            raise ValueError("a token verifier needs allowed clients or an audience")
        self._issuer = issuer
        self._allowed_clients = allowed_clients
        self._key_for = key_for
        self._token_use = token_use
        self._audience = audience

    def verify(self, token: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(
                token,
                self._key_for(token),
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iss", "sub"], "verify_aud": bool(self._audience)},
            )
        except jwt.PyJWTError as exc:
            raise IdentityError(f"user token rejected: {exc}") from exc
        if claims.get("token_use") != self._token_use:
            raise IdentityError(f"user token rejected: token_use is not {self._token_use}")
        if self._allowed_clients and claims.get("client_id") not in self._allowed_clients:
            raise IdentityError("user token rejected: client not allowed")
        return claims

    @classmethod
    def from_environment(cls) -> TokenVerifier:
        issuer = os.environ["TOKEN_ISSUER"]
        jwks = jwt.PyJWKClient(
            os.environ.get("TOKEN_JWKS_URL") or f"{issuer}/.well-known/jwks.json"
        )
        clients = frozenset(c for c in os.environ.get("TOKEN_ALLOWED_CLIENTS", "").split(",") if c)
        return cls(
            issuer,
            clients,
            lambda token: jwks.get_signing_key_from_jwt(token).key,
            token_use=os.environ.get("TOKEN_USE", "access"),
            audience=os.environ.get("TOKEN_AUDIENCE") or None,
        )


def trace_id_from(traceparent: str | None) -> str | None:
    """The 32 hex trace id of a W3C traceparent, or None when absent or malformed."""
    parts = (traceparent or "").split("-")
    if len(parts) == 4 and len(parts[1]) == 32:
        return parts[1]
    return None


def caller_from_headers(headers: Mapping[str, str], verifier: TokenVerifier) -> Caller:
    lowered = {key.lower(): value for key, value in headers.items()}
    token = lowered.get(USER_TOKEN_HEADER)
    if not token:
        raise IdentityError("no user token on the request")
    claims = verifier.verify(token)
    return Caller(
        sub=claims["sub"],
        thread_id=lowered.get(THREAD_HEADER) or None,
        trace_id=trace_id_from(lowered.get(TRACE_HEADER)),
    )
