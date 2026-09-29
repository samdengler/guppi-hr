"""The system prompt, settings, and pending change round trip that phase 2 added (D6, D7,
D22)."""

import json
from types import SimpleNamespace

from ag_ui.core import RunAgentInput, UserMessage
from hr_agent import agent as agent_module


def test_the_hr_tools_paragraph_appears_only_with_hr_tools():
    assert "commit_change" not in agent_module.system_prompt()
    prompt = agent_module.system_prompt(hr_tools=True)
    assert "commit_change with that" in prompt
    assert "proposal_id only when their next message clearly says yes" in prompt


def test_hr_tool_prefix_defaults_to_none(monkeypatch):
    monkeypatch.delenv("HR_TOOL_PREFIX", raising=False)
    assert agent_module.Settings().hr_tool_prefix == ""
    monkeypatch.setenv("HR_TOOL_PREFIX", "hr___")
    assert agent_module.Settings().hr_tool_prefix == "hr___"


# ---- pending change round trip (D6, D7) ----------------------------------------------

PROPOSAL_ID = "5fa4fa460a624723902ee08c116caf0e"
PENDING = {
    "proposalId": PROPOSAL_ID,
    "field": "home_address",
    "from": "1200 Peachtree St NE, Atlanta, GA 30309",
    "to": "419 Glendale Ave, Decatur, GA 30030",
}


def run_input(state):
    return RunAgentInput(
        thread_id="t",
        run_id="r",
        state=state,
        messages=[UserMessage(id="1", role="user", content="yes")],
        tools=[],
        context=[],
        forwarded_props={},
    )


def test_a_well_formed_pending_change_is_read_from_state():
    assert agent_module.pending_action_from({"pendingAction": PENDING}) == PENDING


def test_pending_text_is_flattened_and_capped():
    noisy = {**PENDING, "to": "line one\nline two " + "x" * 1000}
    parsed = agent_module.pending_action_from({"pendingAction": noisy})
    assert "\n" not in parsed["to"] and len(parsed["to"]) == agent_module.PENDING_TEXT_LIMIT


def test_malformed_pending_changes_are_ignored():
    for state in (
        None,
        [],
        {},
        {"pendingAction": "x"},
        {"pendingAction": {**PENDING, "proposalId": "short"}},
        {"pendingAction": {**PENDING, "proposalId": "../" + "a" * 29}},
        {"pendingAction": {**PENDING, "field": "salary"}},
    ):
        assert agent_module.pending_action_from(state) is None


def test_the_adapter_starts_each_run_without_the_old_pending_change():
    prepared = agent_module.without_pending(run_input({"pendingAction": PENDING, "other": 1}))
    assert prepared.state == {"pendingAction": None, "other": 1}
    assert agent_module.without_pending(run_input(None)).state == {"pendingAction": None}


def test_the_prompt_spells_out_the_pending_change_only_with_hr_tools():
    prompt = agent_module.system_prompt(hr_tools=True, pending=PENDING)
    assert PROPOSAL_ID in prompt and "419 Glendale Ave, Decatur, GA 30030" in prompt
    assert "home address from" in prompt
    assert PROPOSAL_ID not in agent_module.system_prompt(hr_tools=False, pending=PENDING)


def result(data):
    return SimpleNamespace(result_data=data)


def test_a_proposal_result_becomes_the_pending_change():
    data = {
        "proposal_id": PROPOSAL_ID,
        "change": {"field": "home_address", "from": PENDING["from"], "to": PENDING["to"]},
        "expires_at": "2026-09-29T01:54:19+00:00",
    }
    for shape in (data, json.dumps(data)):
        state = agent_module.pending_from_proposal(result(shape))
        assert state["pendingAction"]["proposalId"] == PROPOSAL_ID
        assert state["pendingAction"]["to"] == PENDING["to"]


def test_an_error_result_leaves_state_alone():
    assert agent_module.pending_from_proposal(result("Error executing tool: Not proposed")) is None
    assert agent_module.pending_cleared_by_commit(result("Error executing tool: Refused")) is None


def test_a_successful_commit_clears_the_pending_change():
    assert agent_module.pending_cleared_by_commit(result({"committed": True})) == {
        "pendingAction": None
    }
    assert agent_module.pending_cleared_by_commit(result({"committed": False})) is None


def test_only_the_propose_and_commit_tools_touch_state():
    names = [
        "docs___Retrieve",
        "hr___get_profile",
        "hr___propose_address_change",
        "hr___propose_direct_deposit_change",
        "hr___commit_change",
        "hr___open_ticket",
    ]
    behaviors = agent_module.tool_behaviors(names, "hr___")
    assert set(behaviors) == {
        "hr___propose_address_change",
        "hr___propose_direct_deposit_change",
        "hr___commit_change",
    }
    assert agent_module.tool_behaviors(names, "") == {}
