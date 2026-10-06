"""The on-behalf-of exchanger (D47) against a fake AgentCore Identity client."""

from __future__ import annotations

import base64
import json

import pytest
from hr_agent.obo import ExchangeError, TokenExchanger


def fake_token(exp: float, n: int = 0) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"exp": exp, "n": n}).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJSUzI1NiJ9.{body}.sig"


class FakeIdentity:
    def __init__(self, clock, lifetime: float = 3600, fail: bool = False, message: str = "") -> None:
        self.calls: list[dict] = []
        self.jwt_calls: list[str] = []
        self.clock, self.lifetime, self.fail = clock, lifetime, fail
        self.message = message or "ValidationException: Token exchange failed with HTTP 400"

    def get_workload_access_token_for_jwt(self, workloadName, userToken):  # noqa: N803 - boto3's names
        self.jwt_calls.append(workloadName)
        return {"workloadAccessToken": f"wat-for-{workloadName}"}

    def get_resource_oauth2_token(self, **kwargs):
        if self.fail:
            raise RuntimeError(self.message)
        self.calls.append(kwargs)
        return {"accessToken": fake_token(self.clock[0] + self.lifetime, len(self.calls))}


@pytest.fixture
def clock():
    return [1_800_000_000.0]


def exchanger(clock, identity, **kwargs):
    return TokenExchanger(["hr.tools.policy", "hr.tools.pay.read"], provider="guppi-obo-hr-agent-pay",
                          workload="hr_super_agent_pay-obo", client_factory=lambda: identity,
                          clock=lambda: clock[0], **kwargs)


def test_an_exchange_asks_identity_for_the_providers_scopes(clock):
    identity = FakeIdentity(clock)
    token = exchanger(clock, identity).exchange("agents-token")
    assert token.startswith("eyJ")
    (call,) = identity.calls
    assert call["resourceCredentialProviderName"] == "guppi-obo-hr-agent-pay"
    assert call["oauth2Flow"] == "ON_BEHALF_OF_TOKEN_EXCHANGE"
    assert call["scopes"] == ["hr.tools.policy", "hr.tools.pay.read"]
    assert call["workloadIdentityToken"] == "wat-for-hr_super_agent_pay-obo"


def test_a_token_is_reused_until_a_minute_before_it_expires(clock):
    identity = FakeIdentity(clock, lifetime=600)
    obo = exchanger(clock, identity)
    first = obo.exchange("agents-token")
    clock[0] += 500
    assert obo.exchange("agents-token") == first and len(identity.calls) == 1
    clock[0] += 50  # 550 s in: inside the last minute
    assert obo.exchange("agents-token") != first and len(identity.calls) == 2


def test_each_subject_gets_its_own_token(clock):
    identity = FakeIdentity(clock)
    obo = exchanger(clock, identity)
    assert obo.exchange("employee-a") != obo.exchange("employee-b")


def test_a_failed_exchange_refuses_and_names_no_claim(clock):
    obo = exchanger(clock, FakeIdentity(clock, fail=True))
    with pytest.raises(ExchangeError) as raised:
        obo.exchange("agents-token")
    assert str(raised.value) == "RuntimeError"


def test_without_a_provider_the_exchange_fails_closed(clock, monkeypatch):
    # A missing setting must never pass the Okta token on as a hop token (finding 4).
    monkeypatch.delenv("OBO_PROVIDER", raising=False)
    monkeypatch.delenv("OBO", raising=False)
    obo = TokenExchanger(["hr.agents.pay"], client_factory=lambda: pytest.fail("no call expected"))
    with pytest.raises(ExchangeError):
        obo.exchange("okta-token")


def test_only_obo_off_passes_the_token_unchanged(clock, monkeypatch):
    monkeypatch.delenv("OBO_PROVIDER", raising=False)
    monkeypatch.setenv("OBO", "off")
    obo = TokenExchanger(["hr.agents.pay"], client_factory=lambda: pytest.fail("no call expected"))
    assert not obo.enabled and obo.exchange("okta-token") == "okta-token"


def test_a_provider_without_a_workload_is_a_configuration_error(clock):
    obo = TokenExchanger(["hr.agents"], provider="guppi-obo-hr-bridge", workload="",
                         client_factory=lambda: FakeIdentity(clock))
    with pytest.raises(ExchangeError):
        obo.exchange("okta-token")


RUNTIME_TOKEN = "runtime-workload-token-7f3a"


def test_a_runtime_workload_token_skips_the_jwt_call(clock):
    # R1 (D60): the Runtime already called GetWorkloadAccessTokenForJWT for this request.
    identity = FakeIdentity(clock)
    exchanger(clock, identity).exchange("agents-token", workload_token=RUNTIME_TOKEN)
    (call,) = identity.calls
    assert call["workloadIdentityToken"] == RUNTIME_TOKEN
    assert identity.jwt_calls == []


def test_the_runtime_token_needs_no_obo_workload(clock):
    # R1, R5: a sub-agent without OBO_WORKLOAD still exchanges when the Runtime gave a token.
    identity = FakeIdentity(clock)
    obo = TokenExchanger(["hr.tools.policy"], provider="guppi-obo-hr-agent-travel", workload="",
                         client_factory=lambda: identity, clock=lambda: clock[0])
    assert obo.exchange("agents-token", workload_token=RUNTIME_TOKEN).startswith("eyJ")
    assert identity.jwt_calls == [] and identity.calls[0]["workloadIdentityToken"] == RUNTIME_TOKEN


def test_without_a_runtime_token_the_own_workload_is_used(clock):
    # R4: commit A keeps today's path when the request brings no workload token.
    identity = FakeIdentity(clock)
    exchanger(clock, identity).exchange("agents-token")
    assert identity.jwt_calls == ["hr_super_agent_pay-obo"]
    assert identity.calls[0]["workloadIdentityToken"] == "wat-for-hr_super_agent_pay-obo"


def test_without_either_workload_the_exchange_fails_closed(clock):
    # R5: no Runtime token and no OBO_WORKLOAD: refuse, and call nothing.
    obo = TokenExchanger(["hr.tools.policy"], provider="guppi-obo-hr-agent-travel", workload="",
                         client_factory=lambda: pytest.fail("no call expected"), clock=lambda: clock[0])
    with pytest.raises(ExchangeError):
        obo.exchange("agents-token", workload_token=None)


def test_a_cached_token_ignores_the_workload_token(clock):
    # R3: the cache is keyed on the subject; the workload token neither busts nor bypasses it.
    identity = FakeIdentity(clock)
    obo = TokenExchanger(["hr.tools.policy"], provider="guppi-obo-hr-agent-travel", workload="",
                         client_factory=lambda: identity, clock=lambda: clock[0])
    first = obo.exchange("agents-token", workload_token=RUNTIME_TOKEN)
    assert obo.exchange("agents-token", workload_token="another-runtime-token") == first
    assert obo.exchange("agents-token") == first  # no token and no OBO_WORKLOAD, but cached
    assert len(identity.calls) == 1


def test_a_failed_exchange_logs_neither_claim_nor_workload_token(clock, caplog):
    # R6, R7: the error class only, whatever Identity's message quotes.
    identity = FakeIdentity(clock, fail=True, message=f"ValidationException: bad token {RUNTIME_TOKEN} sub=emp-42")
    with caplog.at_level("DEBUG", logger="hr_agent.obo"), pytest.raises(ExchangeError) as raised:
        exchanger(clock, identity).exchange("agents-token", workload_token=RUNTIME_TOKEN)
    assert str(raised.value) == "RuntimeError"
    assert raised.value.__suppress_context__  # a logged traceback cannot chain Identity's message
    for text in (caplog.text, str(raised.value)):
        assert RUNTIME_TOKEN not in text and "emp-42" not in text and "agents-token" not in text


def test_each_identity_exchange_logs_which_workload_token_it_used(clock, caplog):
    # The rollout (d60.sh) counts these lines per sub-agent; neither names a token.
    identity = FakeIdentity(clock)
    obo = exchanger(clock, identity)
    with caplog.at_level("INFO", logger="hr_agent.obo"):
        obo.exchange("employee-a", workload_token=RUNTIME_TOKEN)
        obo.exchange("employee-b")
        obo.exchange("employee-a", workload_token=RUNTIME_TOKEN)  # cached: no line
    lines = [r.getMessage() for r in caplog.records if "workload token" in r.getMessage()]
    assert lines == [
        "token exchange through guppi-obo-hr-agent-pay with the Runtime workload token",
        "token exchange through guppi-obo-hr-agent-pay with its own workload token (hr_super_agent_pay-obo)",
    ]
    assert RUNTIME_TOKEN not in caplog.text and "wat-for" not in caplog.text


async def test_the_async_path_passes_the_runtime_token(clock):
    identity = FakeIdentity(clock)
    obo = exchanger(clock, identity)
    await obo.aexchange("agents-token", RUNTIME_TOKEN)
    assert identity.jwt_calls == [] and identity.calls[0]["workloadIdentityToken"] == RUNTIME_TOKEN


async def test_the_async_path_uses_the_cache(clock):
    identity = FakeIdentity(clock)
    obo = exchanger(clock, identity)
    first = await obo.aexchange("agents-token")
    assert await obo.aexchange("agents-token") == first and len(identity.calls) == 1


class Failing:
    enabled = True

    async def aexchange(self, subject: str) -> str:
        raise ExchangeError("ValidationException")


async def test_hr_diy_says_so_when_the_agents_exchange_fails(monkeypatch):
    from hr_agent import orchestrator

    monkeypatch.setattr(orchestrator, "AGENTS_TOKENS", {d: Failing() for d in orchestrator.DOMAINS})
    reply = await orchestrator.send_to_sub_agent("pay", "okta-token", "t1", "hi", [], None, orchestrator.Settings())
    assert reply.signin and reply.error and reply.text == ""


async def test_hr_diy_general_answer_says_so_when_the_tools_exchange_fails(monkeypatch):
    from ag_ui.core import RunAgentInput
    from hr_agent import agent

    monkeypatch.setattr(agent, "TOOLS_TOKENS", Failing())
    monkeypatch.setenv("TOOLS_GATEWAY_URL", "https://tools.example")
    run_input = RunAgentInput(thread_id="t", run_id="r", state={}, messages=[], tools=[], context=[], forwarded_props={})
    events = [e async for e in agent.StrandsRun("okta-token", agent.Settings()).run(run_input)]
    text = "".join(getattr(e, "delta", "") for e in events)
    assert text == "HR could not confirm the sign-in. Try again in a minute."
    assert events[-1].type == "RUN_FINISHED"


async def test_hr_diy_sends_each_sub_agent_its_own_agents_token(monkeypatch):
    import httpx
    from hr_agent import orchestrator

    class Named:
        enabled = True

        def __init__(self, domain: str) -> None:
            self.domain = domain

        async def aexchange(self, subject: str) -> str:
            return f"{self.domain}-agents-token"

    sent: list[tuple[str, str]] = []

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc) -> None:
            return None

        async def post(self, url, json=None, headers=None):
            sent.append((url, headers["Authorization"]))
            return httpx.Response(200, json={"result": {"parts": [{"kind": "text", "text": "ok"}]}})

    monkeypatch.setattr(orchestrator, "AGENTS_TOKENS", {d: Named(d) for d in orchestrator.DOMAINS})
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    settings = orchestrator.Settings()
    settings.agents_gateway_url = "https://agents.example"
    for domain in orchestrator.DOMAINS:
        await orchestrator.send_to_sub_agent(domain, "okta-token", "t1", "hi", [], None, settings)
    assert sent == [(f"https://agents.example/{d}/invocations", f"Bearer {d}-agents-token") for d in orchestrator.DOMAINS]
