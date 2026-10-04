"""On-behalf-of token exchange through AgentCore Identity (D20, D47).

Each hop trades the token it received for the next hop's, still naming the employee:

- the `/p/hr-diy/` orchestrator trades the employee's Okta token for an agents token
  (`hr.agents`) to call the agents gateway, and for a tools token (`hr.tools.policy`) for
  its general agent's policy search and tickets;
- each sub-agent trades the agents token for its own domain's tools token.

A caller names its credential provider and workload identity in the environment
(OBO_PROVIDER, OBO_WORKLOAD); Identity holds the client secret and calls the issuer. A
token is cached per subject token until a minute before it expires, so a conversation's
turns reuse it; AgentCore Identity does not cache exchanged tokens itself (aws-feedback A14).
Without OBO_PROVIDER an exchange fails, so a missing setting can never pass the Okta token
on in place of a hop token (critique of the build, finding 4). Only OBO=off, set by hand for
a local run, returns the subject token unchanged.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
MARGIN_SECONDS = 60
MAX_CACHED = 256


class ExchangeError(Exception):
    """The exchange failed; the caller refuses the request rather than send the old token."""


def expires_at(token: str) -> float:
    """The token's `exp`, read without verification (the issuer verified it), or now."""
    try:
        part = token.split(".")[1]
        return float(json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))["exp"])
    except Exception:  # noqa: BLE001
        return time.time()


_CLIENT: Any = None
_CLIENT_LOCK = threading.Lock()


def _identity_client() -> Any:
    """One client for every exchanger in the process, built once under a lock from its own
    session: two exchanges start at once on the bridge, and building clients concurrently
    from the default session is not thread-safe."""
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is None:
            import boto3
            from botocore.config import Config

            _CLIENT = boto3.session.Session().client(
                "bedrock-agentcore",
                region_name=os.environ.get("AWS_REGION", "us-east-1"),
                config=Config(connect_timeout=2, read_timeout=5, retries={"max_attempts": 2, "mode": "standard"}),
            )
        return _CLIENT


class TokenExchanger:
    def __init__(
        self,
        scopes: list[str],
        provider: str | None = None,
        workload: str | None = None,
        client_factory: Callable[[], Any] = _identity_client,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.scopes = scopes
        self.provider = provider if provider is not None else os.environ.get("OBO_PROVIDER", "")
        self.workload = workload if workload is not None else os.environ.get("OBO_WORKLOAD", "")
        self._client_factory = client_factory
        self._clock = clock
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        """False only when exchange is switched off by hand (OBO=off) for a local run."""
        return bool(self.provider) or os.environ.get("OBO") != "off"

    def _key(self, subject: str) -> str:
        return hashlib.sha256(subject.encode()).hexdigest()

    def _cached(self, key: str) -> str | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry and self._clock() < entry[1] - MARGIN_SECONDS:
                return entry[0]
            return None

    def exchange(self, subject: str) -> str:
        """The next hop's token for `subject`, from the cache or from Identity."""
        if not self.enabled:
            return subject
        key = self._key(subject)
        cached = self._cached(key)
        if cached:
            return cached
        if not self.provider or not self.workload:
            raise ExchangeError("OBO_PROVIDER or OBO_WORKLOAD is not set")
        try:
            client = self._client_factory()
            workload_token = client.get_workload_access_token_for_jwt(
                workloadName=self.workload, userToken=subject
            )["workloadAccessToken"]
            token = client.get_resource_oauth2_token(
                workloadIdentityToken=workload_token,
                resourceCredentialProviderName=self.provider,
                oauth2Flow="ON_BEHALF_OF_TOKEN_EXCHANGE",
                scopes=self.scopes,
                customParameters={"subject_token_type": ACCESS_TOKEN_TYPE},
            )["accessToken"]
        except Exception as exc:  # noqa: BLE001 - every failure refuses the same way
            # The message names the error class only; Identity's messages can quote claims.
            log.warning("token exchange through %s failed: %s", self.provider, type(exc).__name__)
            raise ExchangeError(type(exc).__name__) from exc
        with self._lock:
            now = self._clock()
            for stale in [k for k, (_, exp) in self._cache.items() if exp - MARGIN_SECONDS <= now]:
                del self._cache[stale]
            while len(self._cache) >= MAX_CACHED:
                del self._cache[next(iter(self._cache))]
            self._cache[key] = (token, expires_at(token))
        return token

    async def aexchange(self, subject: str) -> str:
        if not self.enabled:
            return subject
        key = self._key(subject)
        return self._cached(key) or await asyncio.to_thread(self.exchange, subject)
