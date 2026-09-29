"""The system prompt and settings that phase 2 added (D22)."""

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
