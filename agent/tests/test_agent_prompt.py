"""The general (knowledge base) agent's prompt and settings, and the shared pending-change
parsing (D6, D7, D23)."""

import json

from ag_ui.core import RunAgentInput, UserMessage
from hr_agent import agent as agent_module
from hr_agent import pending as pending_module

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


def test_the_ticket_paragraph_appears_only_with_the_ticket_tool():
    assert "open a ticket" not in agent_module.system_prompt()
    assert "open a ticket right away" in agent_module.system_prompt(ticket_tool=True)
    assert "commit_change" not in agent_module.system_prompt(ticket_tool=True)


def test_extra_tools_come_from_the_environment(monkeypatch):
    monkeypatch.delenv("ORCHESTRATOR_EXTRA_TOOLS", raising=False)
    assert agent_module.Settings().extra_tools == []
    monkeypatch.setenv("ORCHESTRATOR_EXTRA_TOOLS", "hr___open_ticket,")
    assert agent_module.Settings().extra_tools == ["hr___open_ticket"]


def test_a_general_run_drops_the_pending_change_and_keeps_the_rest():
    prepared = agent_module.without_pending(
        run_input({"pendingAction": PENDING, "activeDomain": "profile"})
    )
    assert prepared.state == {"pendingAction": None, "activeDomain": "profile"}
    assert agent_module.without_pending(run_input(None)).state == {"pendingAction": None}


def test_a_well_formed_pending_change_is_read_from_state():
    assert pending_module.pending_action_from({"pendingAction": PENDING}) == PENDING


def test_pending_text_is_flattened_and_capped():
    noisy = {**PENDING, "to": "line one\nline two " + "x" * 1000}
    parsed = pending_module.parse_pending(noisy)
    assert "\n" not in parsed["to"] and len(parsed["to"]) == pending_module.PENDING_TEXT_LIMIT


def test_malformed_pending_changes_are_ignored():
    for value in (
        None,
        [],
        "x",
        {**PENDING, "proposalId": "short"},
        {**PENDING, "proposalId": "../" + "a" * 29},
        {**PENDING, "field": "salary"},
    ):
        assert pending_module.parse_pending(value) is None


def test_the_pending_paragraph_spells_out_the_change():
    paragraph = pending_module.pending_paragraph(PENDING)
    assert PROPOSAL_ID in paragraph and "home address from" in paragraph
    assert pending_module.pending_paragraph(None) == ""


def test_a_proposal_result_becomes_a_pending_change():
    data = {
        "proposal_id": PROPOSAL_ID,
        "change": {"field": "home_address", "from": PENDING["from"], "to": PENDING["to"]},
        "expires_at": "2026-09-29T01:54:19+00:00",
    }
    for shape in (data, json.dumps(data)):
        assert pending_module.pending_from_result(shape)["to"] == PENDING["to"]
    assert pending_module.pending_from_result("Error executing tool: Not proposed") is None
    assert pending_module.committed({"committed": True})
    assert not pending_module.committed("Error executing tool: Refused")
