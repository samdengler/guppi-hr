"""The Strands agent behind one run.

Everything here is built per request: the MCP client carries the caller's bearer token to
the tools gateway, so it cannot outlive the request, and the AG-UI adapter caches one
Strands agent per thread, so a fresh adapter per request keeps the service stateless.
`build_strands_agent` is the seam the tests replace.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from ag_ui.core import BaseEvent, RunAgentInput
from ag_ui_strands.config import ToolBehavior, ToolResultContext

from hr_agent import conversation_log

log = logging.getLogger("hr_agent")

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_RETRIEVE_TOOL = "docs___Retrieve"
DEFAULT_REGION = "us-east-1"

MEMORY_SENTENCE = "Nothing is saved between page loads, and you cannot recall earlier sessions."
LOGGED_MEMORY_SENTENCE = (
    "Conversations are logged for troubleshooting; nothing is saved between page loads, "
    "and you cannot recall earlier sessions."
)

SYSTEM_PROMPT_TEMPLATE = """You are the HR Assistant, helping one signed-in employee.

You have no memory beyond the conversation on the current page. {memory}

You have a search over the HR policy documents. When a question concerns HR policy (pay,
benefits, travel privileges, leave, profile changes), search first and answer once from
what the search returns, saying so when the passages do not settle the question. Do not
narrate the search or revise an earlier draft.
{hr_tools}
Reply in concise plain text. The page renders no Markdown, so write no headings, bullet
markers, bold, code fences, or links; use short paragraphs and plain sentences instead, and
indent code by four spaces. In examples write server addresses as <server-url>, never as
localhost or a loopback address: the gateway in front of this page rejects any message
that contains one, which would end the conversation.
"""

HR_TOOLS_PARAGRAPH = """
You also have HR tools that act on this employee's own records: their profile and
emergency contact, direct deposit, pay statements, and tickets for the HR team. A change
always takes two turns. First call the matching propose tool, then tell the employee the
exact change it returned and ask them to confirm. Call commit_change with that
proposal_id only when their next message clearly says yes; if they decline or change the
details, do not commit. Never say a change is done unless commit_change succeeded. When
the employee asks for a person, or nothing you have answers the request, open a ticket
and give them its id.
"""


PENDING_PARAGRAPH = """
A change is waiting for the employee's confirmation from your previous reply: proposal_id
{proposal_id}, {field} from "{before}" to "{after}". If the employee's message clearly
confirms this change, call commit_change with this proposal_id. If they decline or alter
any detail, do not commit; propose again with the new details when needed.
"""

# AG-UI state key for the change awaiting confirmation (D6, D7). It lives for one turn:
# shown to the model on the next run, then dropped unless that run proposes again.
PENDING_KEY = "pendingAction"
PENDING_FIELDS = ("home_address", "emergency_contact", "direct_deposit")
PENDING_TEXT_LIMIT = 300


def _clean(value: object) -> str:
    return " ".join(str(value).split())[:PENDING_TEXT_LIMIT]


def pending_action_from(state: object) -> dict[str, str] | None:
    """The pending change the page sent back, or None when absent or malformed. The page
    controls this value, so it is only a hint to the model: the tools server still checks
    the proposal's owner, conversation, status, and expiry on commit."""
    if not isinstance(state, dict):
        return None
    pending = state.get(PENDING_KEY)
    if not isinstance(pending, dict):
        return None
    proposal_id = str(pending.get("proposalId", ""))
    field = pending.get("field")
    if len(proposal_id) != 32 or not proposal_id.isalnum() or field not in PENDING_FIELDS:
        return None
    return {
        "proposalId": proposal_id,
        "field": field,
        "from": _clean(pending.get("from", "")),
        "to": _clean(pending.get("to", "")),
    }


def system_prompt(hr_tools: bool = False, pending: dict[str, str] | None = None) -> str:
    """The prompt for one run. The claim about saving follows the logging switch, the HR
    tools paragraph appears only when the gateway offered those tools, and a pending change
    from the previous turn is spelled out so the model can commit it on a yes."""
    logged = conversation_log.enabled()
    prompt = SYSTEM_PROMPT_TEMPLATE.format(
        memory=LOGGED_MEMORY_SENTENCE if logged else MEMORY_SENTENCE,
        hr_tools=HR_TOOLS_PARAGRAPH if hr_tools else "",
    )
    if hr_tools and pending:
        prompt += PENDING_PARAGRAPH.format(
            proposal_id=pending["proposalId"],
            field=pending["field"].replace("_", " "),
            before=pending["from"],
            after=pending["to"],
        )
    return prompt


def _result_dict(result_data: object) -> dict | None:
    if isinstance(result_data, str):
        try:
            result_data = json.loads(result_data)
        except ValueError:
            return None
    return result_data if isinstance(result_data, dict) else None


def pending_from_proposal(context: ToolResultContext) -> dict | None:
    """state_from_result for the propose tools: the new pending change."""
    data = _result_dict(context.result_data)
    change = data.get("change") if data else None
    if not data or "proposal_id" not in data or not isinstance(change, dict):
        return None
    return {
        PENDING_KEY: {
            "proposalId": data["proposal_id"],
            "field": change.get("field"),
            "from": change.get("from", ""),
            "to": change.get("to", ""),
            "expiresAt": data.get("expires_at", ""),
        }
    }


def pending_cleared_by_commit(context: ToolResultContext) -> dict | None:
    """state_from_result for commit_change: a successful commit clears the pending change."""
    data = _result_dict(context.result_data)
    return {PENDING_KEY: None} if data and data.get("committed") is True else None


def tool_behaviors(tool_names: list[str], prefix: str) -> dict[str, ToolBehavior]:
    """Which tools write the pending change into AG-UI state."""
    behaviors: dict[str, ToolBehavior] = {}
    if not prefix:
        return behaviors
    for name in tool_names:
        if name.startswith(f"{prefix}propose_"):
            behaviors[name] = ToolBehavior(state_from_result=pending_from_proposal)
        elif name == f"{prefix}commit_change":
            behaviors[name] = ToolBehavior(state_from_result=pending_cleared_by_commit)
    return behaviors


def without_pending(run_input: RunAgentInput) -> RunAgentInput:
    """The run as the adapter sees it: the old pending change is dropped from state, so the
    final STATE_SNAPSHOT carries one only if this run proposed again."""
    state = dict(run_input.state) if isinstance(run_input.state, dict) else {}
    state[PENDING_KEY] = None
    return run_input.model_copy(update={"state": state})


class Settings:
    """Environment settings read once per request so tests can change them."""

    def __init__(self) -> None:
        self.tools_gateway_url = os.environ.get("TOOLS_GATEWAY_URL", "")
        self.model_id = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
        self.retrieve_tool = os.environ.get("RETRIEVE_TOOL", DEFAULT_RETRIEVE_TOOL)
        # Phase 2 hands the hr___ tools to this agent so they can be checked in the
        # browser (D22); phase 4 moves them to the sub-agents. Empty means none.
        self.hr_tool_prefix = os.environ.get("HR_TOOL_PREFIX", "")
        self.region = os.environ.get("AWS_REGION", DEFAULT_REGION)


class StrandsRun:
    """One run: an MCP client with the user's token, a Strands agent, the AG-UI adapter."""

    def __init__(self, token: str, settings: Settings) -> None:
        if not settings.tools_gateway_url:
            raise RuntimeError("TOOLS_GATEWAY_URL is not set")
        self._token = token
        self._settings = settings
        self._agents_by_thread: dict[str, Any] = {}

    async def run(self, run_input: RunAgentInput) -> AsyncIterator[BaseEvent]:
        from ag_ui_strands import StrandsAgent, StrandsAgentConfig
        from strands import Agent
        from strands.models import BedrockModel
        from strands.tools.mcp import MCPClient

        settings = self._settings
        pending = pending_action_from(run_input.state)
        run_input = without_pending(run_input)
        # The tools gateway checks Authorization; it cannot forward that header to the HR
        # tools server, so the same token rides again in X-Hr-User-Token, which the server
        # verifies itself (D19). The thread id binds a proposal to its conversation.
        client = MCPClient(
            url=settings.tools_gateway_url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "X-Hr-User-Token": self._token,
                "X-Hr-Thread-Id": run_input.thread_id,
            },
        )
        # The client runs its own thread and event loop; start and stop block, so they are
        # kept off the loop that streams the response.
        await asyncio.to_thread(client.start)
        try:
            listed = await asyncio.to_thread(client.list_tools_sync)
            tools = [
                tool
                for tool in listed
                if tool.tool_name == settings.retrieve_tool
                or (settings.hr_tool_prefix and tool.tool_name.startswith(settings.hr_tool_prefix))
            ]
            offered = [tool.tool_name for tool in listed]
            log.info("tools offered by the gateway: %s", offered)
            if not any(tool.tool_name == settings.retrieve_tool for tool in tools):
                log.warning(
                    "tool %s not offered by the gateway (offered: %s)",
                    settings.retrieve_tool,
                    offered,
                )
            hr_tools = any(tool.tool_name != settings.retrieve_tool for tool in tools)
            template = Agent(
                model=BedrockModel(
                    model_id=settings.model_id,
                    region_name=settings.region,
                    streaming=True,
                    max_tokens=1024,
                    temperature=0.7,
                ),
                system_prompt=system_prompt(hr_tools, pending),
                tools=tools,
                callback_handler=None,
            )
            adapter = StrandsAgent(
                template,
                name="hr-assistant",
                config=StrandsAgentConfig(
                    emit_messages_snapshot=False,
                    tool_behaviors=tool_behaviors(
                        [tool.tool_name for tool in tools], settings.hr_tool_prefix
                    ),
                ),
                agents_by_thread=self._agents_by_thread,
            )
            async for event in adapter.run(run_input):
                yield event
        finally:
            await asyncio.to_thread(client.stop, None, None, None)

    def usage(self) -> dict[str, int]:
        """Input and output token counts from the Strands agent, if a run happened."""
        for agent in self._agents_by_thread.values():
            metrics = getattr(agent, "event_loop_metrics", None)
            accumulated = getattr(metrics, "accumulated_usage", None) or {}
            return {
                "input_tokens": int(accumulated.get("inputTokens", 0)),
                "output_tokens": int(accumulated.get("outputTokens", 0)),
            }
        return {}


def build_strands_agent(token: str) -> StrandsRun:
    """Build the object that runs one request. Tests monkeypatch this name in app.py."""
    return StrandsRun(token, Settings())
