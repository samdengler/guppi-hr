"""Who is calling a tool.

The tools gateway exchanges each caller's token through AgentCore Identity for one only
this runtime accepts (D47): issued by the on-behalf-of issuer for `api://hr-tools-runtime`
to the client `hr-tools-gateway`, naming the employee in `sub`, carrying the caller's
scopes, and recording who acted in a nested `act` claim. The runtime's JWT authorizer
checks it and passes `Authorization` through; this module verifies it again
(signature against the issuer's keys, issuer, audience, expiry, client), so the server does
not rely on the runtime's settings alone. Issuer, keys, clients and audience are
environment settings.

`X-Hr-User-Token`, the second copy of the user's token the gateway forwarded while it
signed its calls with SigV4 (D19), is gone.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import jwt

THREAD_HEADER = "x-hr-thread-id"
TRACE_HEADER = "traceparent"
FORWARDED_HEADERS = (THREAD_HEADER, TRACE_HEADER)


class IdentityError(Exception):
    """The request carries no usable user token."""


@dataclass(frozen=True)
class Caller:
    sub: str
    thread_id: str | None
    trace_id: str | None
    scopes: frozenset[str] = frozenset()
    acted_by: str = ""  # the clients that acted, nearest first: "hr-tools-gateway<hr-agent-pay<hr-bridge"


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
                options={"require": ["exp", "iat", "iss", "sub"], "verify_aud": bool(self._audience)},
                leeway=60,
            )
        except jwt.PyJWTError as exc:
            raise IdentityError(f"user token rejected: {exc}") from exc
        if self._token_use and claims.get("token_use") != self._token_use:
            raise IdentityError(f"user token rejected: token_use is not {self._token_use}")
        client = claims.get("client_id") or claims.get("cid")
        if self._allowed_clients and client not in self._allowed_clients:
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
            # Empty skips the check: Okta's access tokens carry no token_use claim.
            token_use=os.environ.get("TOKEN_USE", "access"),
            audience=os.environ.get("TOKEN_AUDIENCE") or None,
        )


def subject_of(claims: Mapping[str, Any]) -> str:
    """The caller's stable id: Okta's `uid` when present, else `sub` (D46)."""
    return str(claims.get("uid") or claims["sub"])


def trace_id_from(traceparent: str | None) -> str | None:
    """The 32 hex trace id of a W3C traceparent, or None when absent or malformed."""
    parts = (traceparent or "").split("-")
    if len(parts) == 4 and len(parts[1]) == 32:
        return parts[1]
    return None


def acted_by(claims: Mapping[str, Any]) -> str:
    """The `act` chain as one string, nearest actor first."""
    names, act = [], claims.get("act")
    while isinstance(act, Mapping) and len(names) < 8:
        names.append(str(act.get("sub", "?")))
        act = act.get("act")
    return "<".join(names)


def caller_from_headers(headers: Mapping[str, str], verifier: TokenVerifier) -> Caller:
    lowered = {key.lower(): value for key, value in headers.items()}
    scheme, _, token = lowered.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise IdentityError("no bearer token on the request")
    claims = verifier.verify(token.strip())
    return Caller(
        sub=subject_of(claims),
        thread_id=lowered.get(THREAD_HEADER) or None,
        trace_id=trace_id_from(lowered.get(TRACE_HEADER)),
        scopes=frozenset(str(claims.get("scope", "")).split()),
        acted_by=acted_by(claims),
    )
