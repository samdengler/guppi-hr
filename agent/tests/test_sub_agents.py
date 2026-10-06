"""The sub-agents over their A2A HTTP surface, with the Bedrock run replaced (phase 3)."""

from __future__ import annotations

import pytest
from hr_agent import __main__ as entrypoint
from hr_agent.agents import server
from hr_agent.agents.domains import DOMAINS, PAY, PROFILE, RETRIEVE_TOOL, TRAVEL
from hr_agent.pending import pending_after_messages
from starlette.testclient import TestClient

PROPOSAL_ID = "5fa4fa460a624723902ee08c116caf0e"
PENDING = {
    "proposalId": PROPOSAL_ID,
    "field": "home_address",
    "from": "88 Lake Shore Dr, Chicago, IL 60611",
    "to": "419 Glendale Ave, Decatur, GA 30030",
}


class FakeRunner:
    def __init__(self, result=None, error=None):
        self.calls = []
        self.result = result or server.DomainResult(reply="Done.", pending=None, tool_calls=1)
        self.error = error

    async def __call__(self, domain, token, thread_id, history, text, pending, workload_token=None):
        self.calls.append(
            {
                "domain": domain.name,
                "token": token,
                "thread": thread_id,
                "history": history,
                "text": text,
                "pending": pending,
                "workload_token": workload_token,
            }
        )
        if self.error:
            raise self.error
        return self.result


def send(client, text="What's my address?", metadata=None, headers=None, context="thread-1"):
    message = {
        "role": "user",
        "parts": [{"kind": "text", "text": text}],
        "messageId": "m-1",
        "contextId": context,
    }
    if metadata is not None:
        message["metadata"] = metadata
    body = {"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {"message": message}}
    sent = {"authorization": "Bearer user-token"} if headers is None else headers
    response = client.post("/", json=body, headers=sent)
    assert response.status_code == 200, response.text
    return response.json()["result"]


def parts(result):
    text = [p["text"] for p in result["parts"] if p["kind"] == "text"]
    data = [p["data"] for p in result["parts"] if p["kind"] == "data"]
    return text[0], data[0]


@pytest.fixture
def runner():
    return FakeRunner()


@pytest.fixture
def client(runner):
    return TestClient(server.build_app("profile", runner))


def test_the_caller_token_thread_history_and_pending_change_reach_the_run(client, runner):
    history = [
        {"role": "user", "content": "Change my address to 419 Glendale Ave, Decatur GA 30030"},
        {"role": "assistant", "content": "Confirm the change?"},
    ]
    result = send(client, "yes", metadata={"history": history, "pendingAction": PENDING})
    (call,) = runner.calls
    assert call["token"] == "user-token"
    assert call["thread"] == "thread-1"
    assert call["text"] == "yes"
    assert call["pending"] == PENDING
    assert [m["role"] for m in call["history"]] == ["user", "assistant"]
    assert result["kind"] == "message" and result["contextId"] == "thread-1"


def test_the_reply_carries_the_text_and_the_pending_change(runner):
    runner.result = server.DomainResult(reply="Confirm?", pending={**PENDING, "expiresAt": "x"})
    with TestClient(server.build_app("profile", runner)) as client:
        text, data = parts(send(client))
    assert text == "Confirm?"
    assert data["domain"] == "profile"
    assert data["pendingAction"]["proposalId"] == PROPOSAL_ID


def test_a_request_without_a_bearer_token_is_not_run(client, runner):
    text, data = parts(send(client, headers={}))
    assert runner.calls == []
    assert data["error"] == "agent_failed" and "could not complete" in text


def test_a_failed_run_answers_with_an_error_part():
    runner = FakeRunner(error=RuntimeError("bedrock down"))
    with TestClient(server.build_app("pay", runner)) as client:
        text, data = parts(send(client))
    assert text == "The Pay agent could not complete the request."
    assert data == {"domain": "pay", "error": "agent_failed"}


def test_a_malformed_pending_change_is_not_passed_on(client, runner):
    send(client, "yes", metadata={"pendingAction": {**PENDING, "proposalId": "nope"}})
    assert runner.calls[0]["pending"] is None


def test_the_agent_card_and_ping(monkeypatch):
    url = "https://example.gateway.bedrock-agentcore.us-east-1.amazonaws.com/travel/invocations/"
    monkeypatch.setenv("AGENTCORE_RUNTIME_URL", url)
    with TestClient(server.build_app("travel", FakeRunner())) as client:
        card = client.get("/.well-known/agent-card.json").json()
        assert client.get("/ping").status_code == 200
    assert card["name"] == "Travel agent"
    assert card["url"] == url
    assert card["skills"][0]["examples"][0] == "How many buddy passes do I get?"


def test_card_descriptions_are_distinct_and_name_their_own_subject():
    descriptions = {name: domain.description for name, domain in DOMAINS.items()}
    assert len(set(descriptions.values())) == 3
    assert "home address" in descriptions["profile"]
    assert "direct deposit" in descriptions["pay"]
    assert "buddy passes" in descriptions["travel"]


def test_each_domain_holds_only_its_own_tools():
    assert PROFILE.tool_names("hr___") >= {"hr___propose_address_change", RETRIEVE_TOOL}
    assert "hr___propose_direct_deposit_change" not in PROFILE.tool_names("hr___")
    assert "hr___propose_address_change" not in PAY.tool_names("hr___")
    assert TRAVEL.tool_names("hr___") == {RETRIEVE_TOOL, "hr___open_ticket"}


def test_writer_prompts_show_what_is_on_file_first():
    assert "say what is on file before" in server.system_prompt(PROFILE)
    assert "say what is on file before" not in server.system_prompt(TRAVEL)


def test_travel_is_read_only_in_its_prompt():
    assert "commit_change" not in server.system_prompt(TRAVEL, PENDING)
    assert "commit_change" not in server.turn_context(TRAVEL, PENDING, None, None)
    assert PROPOSAL_ID in server.turn_context(PROFILE, PENDING, None, None)


def test_nothing_about_the_employee_reaches_the_system_prompt():
    # Strands copies the system prompt into an unredacted span attribute (A8).
    prompt = server.system_prompt(PROFILE, PENDING)
    assert PROPOSAL_ID not in prompt and PENDING["to"] not in prompt
    context = server.turn_context(PROFILE, PENDING, "get_profile: {...}", None)
    assert PENDING["to"] in context and "<record>" in context


def test_history_is_trimmed_to_alternating_turns_ending_on_the_assistant():
    history = [
        {"role": "assistant", "content": "stray greeting"},
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
        {"role": "assistant", "content": "c"},
        {"role": "tool", "content": "ignored"},
        {"role": "user", "content": "trailing user turn"},
    ]
    messages = server.history_messages(history)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"][0]["text"] == "a\n\nb"
    assert server.history_messages("not a list") == []


def tool_use(use_id, name):
    return {"role": "assistant", "content": [{"toolUse": {"toolUseId": use_id, "name": name}}]}


def tool_result(use_id, text, status="success"):
    return {
        "role": "user",
        "content": [{"toolResult": {"toolUseId": use_id, "status": status, "content": [text]}}],
    }


PROPOSAL = {
    "proposal_id": PROPOSAL_ID,
    "change": {"field": "home_address", "from": PENDING["from"], "to": PENDING["to"]},
    "expires_at": "2026-09-29T02:00:00+00:00",
}


def test_a_proposal_leaves_a_pending_change():
    import json

    messages = [
        tool_use("1", "hr___propose_address_change"),
        tool_result("1", {"text": json.dumps(PROPOSAL)}),
    ]
    assert pending_after_messages(messages, "hr___")["proposalId"] == PROPOSAL_ID


def test_a_commit_after_the_proposal_clears_it():
    messages = [
        tool_use("1", "hr___propose_address_change"),
        tool_result("1", {"json": PROPOSAL}),
        tool_use("2", "hr___commit_change"),
        tool_result("2", {"json": {"committed": True}}),
    ]
    assert pending_after_messages(messages, "hr___") is None


def test_failed_tool_calls_leave_nothing_pending():
    messages = [
        tool_use("1", "hr___propose_address_change"),
        tool_result("1", {"text": "Not proposed: bad ZIP"}, status="error"),
    ]
    assert pending_after_messages(messages, "hr___") is None


def test_each_sub_agent_role_starts_its_a2a_server(monkeypatch):
    served = []
    monkeypatch.setattr(server, "serve", served.append)
    for role in ("profile", "pay", "travel"):
        monkeypatch.setenv("AGENT_ROLE", role)
        entrypoint.main()
    assert served == ["profile", "pay", "travel"]


class FakeWarmer:
    def __init__(self):
        self.calls = []

    async def __call__(self, token, thread_id, domain, workload_token=None):
        self.calls.append((token, thread_id, domain, workload_token))


def test_a_warm_message_opens_the_session_without_a_model_run(runner):
    warmer = FakeWarmer()
    with TestClient(server.build_app("profile", runner, warmer)) as client:
        result = send(client, "warm", metadata={"warm": True}, context="contact-1")
    assert warmer.calls == [("user-token", "contact-1", "profile", None)]
    assert runner.calls == []
    assert [p["kind"] for p in result["parts"]] == ["data"]
    assert result["parts"][0]["data"] == {"domain": "profile", "warm": True}


def test_a_warm_message_without_a_token_does_nothing(runner):
    warmer = FakeWarmer()
    with TestClient(server.build_app("profile", runner, warmer)) as client:
        result = send(client, "warm", metadata={"warm": True}, headers={})
    assert warmer.calls == []
    assert parts(result)[1]["error"] == "agent_failed"


async def test_warm_domain_leases_the_threads_session(monkeypatch):
    opened = []

    def open_session(key):
        opened.append(key)
        return object(), []

    monkeypatch.setattr(server, "SESSIONS", server.McpSessions(open_session))
    await server.warm_domain("tok", "contact-1")
    await server.warm_domain("tok", "contact-1")
    assert opened == [("tok", "contact-1")]


class ToolClient:
    """An MCP client whose tool calls answer from a table and are counted."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []

    def call_tool_sync(self, tool_use_id, name, arguments=None):
        self.calls.append((name, arguments))
        text = self.answers.get(name)
        if text is None:
            return {"status": "error", "toolUseId": tool_use_id, "content": [{"text": "no"}]}
        return {"status": "success", "toolUseId": tool_use_id, "content": [{"text": text}]}


async def test_the_warm_start_reads_the_record_once_for_the_thread(monkeypatch):
    client = ToolClient({"hr___get_profile": '{"home_address": "25 Ponce de Leon Ave"}'})
    monkeypatch.setattr(server, "SESSIONS", server.McpSessions(lambda key: (client, [])))
    monkeypatch.setattr(server, "SNAPSHOTS", server.Snapshots())
    await server.warm_domain("tok", "contact-1", "profile")
    await server.warm_domain("tok", "contact-1", "profile")
    assert client.calls == [("hr___get_profile", {})]
    assert "25 Ponce" in server.SNAPSHOTS.get(("tok", "contact-1", "profile"))


def test_a_failed_read_leaves_the_model_to_read_it_itself():
    from hr_agent.agents.snapshot import read_record

    client = ToolClient({"hr___get_direct_deposit": "{}"})  # list_pay_statements fails
    assert read_record(client, "pay", "hr___") is None
    assert read_record(client, "travel", "hr___") is None


def test_the_record_and_passages_reach_the_prompt():
    from hr_agent.agents.snapshot import prompt_paragraph

    text = prompt_paragraph("get_profile: {...}", "Buddy passes: 8 per year")
    assert "<record>" in text and "get_profile: {...}" in text
    assert "<passages>" in text and "8 per year" in text
    assert prompt_paragraph(None, None) == ""


def test_a_snapshot_expires_and_can_be_dropped():
    from hr_agent.agents.snapshot import SNAPSHOT_SECONDS, Snapshots

    now = [0.0]
    snapshots = Snapshots(clock=lambda: now[0])
    snapshots.put(("t", "c", "profile"), "record")
    assert snapshots.get(("t", "c", "profile")) == "record"
    now[0] += SNAPSHOT_SECONDS + 1
    assert snapshots.get(("t", "c", "profile")) is None
    snapshots.put(("t", "c", "profile"), "record")
    snapshots.drop(("t", "c", "profile"))
    assert snapshots.get(("t", "c", "profile")) is None



async def test_the_warm_start_caches_a_broad_travel_search(monkeypatch):
    client = ToolClient({"docs___Retrieve": "Buddy passes: 8 per calendar year."})
    monkeypatch.setattr(server, "SESSIONS", server.McpSessions(lambda key: (client, [])))
    monkeypatch.setattr(server, "SNAPSHOTS", server.Snapshots())
    await server.warm_domain("tok", "contact-1", "travel")
    assert [name for name, _ in client.calls] == ["docs___Retrieve"]
    assert "8 per calendar year" in server.SNAPSHOTS.get(("tok", "contact-1", "travel"))


# D60: the sub-agent exchanges on the workload token the Runtime fetched for the request,
# which the SDK's A2A app copies from the WorkloadAccessToken header into the call state.
RUNTIME_TOKEN = "runtime-workload-token-7f3a"
WITH_RUNTIME_TOKEN = {"authorization": "Bearer user-token", "WorkloadAccessToken": RUNTIME_TOKEN}


def test_the_executor_passes_the_runtime_workload_token_to_the_runner(client, runner):
    # R1
    send(client, headers=WITH_RUNTIME_TOKEN)
    (call,) = runner.calls
    assert call["token"] == "user-token" and call["workload_token"] == RUNTIME_TOKEN


def test_the_warm_up_passes_the_runtime_workload_token(runner):
    # R2
    warmer = FakeWarmer()
    with TestClient(server.build_app("profile", runner, warmer)) as client:
        send(client, "warm", metadata={"warm": True}, headers=WITH_RUNTIME_TOKEN, context="contact-1")
    assert warmer.calls == [("user-token", "contact-1", "profile", RUNTIME_TOKEN)]


class NoIdentity:
    def __call__(self):
        raise AssertionError("Identity must not be called")


def test_no_workload_token_replies_exchange_failed(monkeypatch, caplog):
    # R5, R7: no Runtime token and no OBO_WORKLOAD: refused before any tools gateway call.
    from hr_agent.obo import TokenExchanger

    monkeypatch.setattr(server, "TOOLS_TOKENS", TokenExchanger(
        ["hr.tools.policy"], provider="guppi-obo-hr-agent-profile", workload="", client_factory=NoIdentity()))
    monkeypatch.setattr(server, "SESSIONS", server.McpSessions(lambda key: pytest.fail("no tools gateway call")))
    with TestClient(server.build_app("profile")) as client:
        result = send(client)
    text, data = parts(result)
    assert data["error"] == "exchange_failed" and "could not complete" in text


def test_a_failed_runtime_exchange_replies_exchange_failed_without_the_token(monkeypatch, caplog):
    # R6, R7: Identity refuses; the reply and the logs name neither token.
    from hr_agent.obo import TokenExchanger

    class Refusing:
        def get_resource_oauth2_token(self, **kwargs):
            raise RuntimeError(f"AccessDeniedException: {kwargs['workloadIdentityToken']}")

    monkeypatch.setattr(server, "TOOLS_TOKENS", TokenExchanger(
        ["hr.tools.policy"], provider="guppi-obo-hr-agent-profile", workload="", client_factory=Refusing))
    monkeypatch.setattr(server, "SESSIONS", server.McpSessions(lambda key: pytest.fail("no tools gateway call")))
    with caplog.at_level("DEBUG"), TestClient(server.build_app("profile")) as client:
        result = send(client, headers=WITH_RUNTIME_TOKEN)
    assert parts(result)[1]["error"] == "exchange_failed"
    assert RUNTIME_TOKEN not in str(result) and RUNTIME_TOKEN not in caplog.text
