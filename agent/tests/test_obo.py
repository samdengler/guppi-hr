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
    def __init__(self, clock, lifetime: float = 3600, fail: bool = False) -> None:
        self.calls: list[dict] = []
        self.clock, self.lifetime, self.fail = clock, lifetime, fail

    def get_workload_access_token_for_jwt(self, workloadName, userToken):  # noqa: N803 - boto3's names
        return {"workloadAccessToken": f"wat-for-{workloadName}"}

    def get_resource_oauth2_token(self, **kwargs):
        if self.fail:
            raise RuntimeError("ValidationException: Token exchange failed with HTTP 400")
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
