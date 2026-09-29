"""The Strands agent behind one run.

Everything here is built per request: the MCP client carries the caller's bearer token to
the tools gateway, so it cannot outlive the request, and the AG-UI adapter caches one
Strands agent per thread, so a fresh adapter per request keeps the service stateless.
`build_strands_agent` is the seam the tests replace.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from typing import Any

from ag_ui.core import BaseEvent, RunAgentInput

from hr_agent import conversation_log
from hr_agent.pending import PENDING_KEY

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

TICKET_PARAGRAPH = """
You can also open a ticket for the HR team. When the employee asks to talk to a person, or
nothing you have answers the request, open a ticket right away with a one-line summary of
the conversation and give them its id.
"""


def system_prompt(ticket_tool: bool = False) -> str:
    """The prompt for a general run (questions outside the three sub-agents' areas). The
    claim about saving follows the logging switch; the ticket paragraph appears only when
    the gateway offered open_ticket."""
    logged = conversation_log.enabled()
    return SYSTEM_PROMPT_TEMPLATE.format(
        memory=LOGGED_MEMORY_SENTENCE if logged else MEMORY_SENTENCE,
        hr_tools=TICKET_PARAGRAPH if ticket_tool else "",
    )


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
        # Tools beyond the policy search, by full gateway name; in phase 4 only
        # hr___open_ticket, for escalation when no area fits (D14, D22 ended).
        self.extra_tools = [
            name for name in os.environ.get("ORCHESTRATOR_EXTRA_TOOLS", "").split(",") if name
        ]
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
            wanted = {settings.retrieve_tool, *settings.extra_tools}
            tools = [tool for tool in listed if tool.tool_name in wanted]
            offered = [tool.tool_name for tool in listed]
            log.info("tools offered by the gateway: %s", offered)
            if not any(tool.tool_name == settings.retrieve_tool for tool in tools):
                log.warning(
                    "tool %s not offered by the gateway (offered: %s)",
                    settings.retrieve_tool,
                    offered,
                )
            ticket_tool = any(tool.tool_name.endswith("open_ticket") for tool in tools)
            template = Agent(
                model=BedrockModel(
                    model_id=settings.model_id,
                    region_name=settings.region,
                    streaming=True,
                    max_tokens=1024,
                    temperature=0.7,
                ),
                system_prompt=system_prompt(ticket_tool),
                tools=tools,
                callback_handler=None,
            )
            adapter = StrandsAgent(
                template,
                name="hr-assistant",
                config=StrandsAgentConfig(emit_messages_snapshot=False),
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


def build_general_agent(token: str) -> StrandsRun:
    """The knowledge base agent for questions outside the sub-agents' areas."""
    return StrandsRun(token, Settings())


def build_strands_agent(token: str):
    """Build the object that runs one request. Tests monkeypatch this name in app.py."""
    from hr_agent.orchestrator import Orchestrator

    return Orchestrator(token, general_factory=build_general_agent)
