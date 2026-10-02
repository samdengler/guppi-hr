"""HR Super Agent orchestrator on the AgentCore Runtime AG-UI contract.

The HTTP surface (POST /invocations streaming AG-UI events as server-sent events, GET
/ping, bearer token, validation and trimming, keepalive pings, the per-run log record and
the conversation log) is the platform kit's `create_app` from guppi-gpt
(`docs/proposals/platform.md` there). What is HR's own is the agent built per request:
the orchestrator in orchestrator.py, returned by `agent.build_strands_agent`.
"""

from __future__ import annotations

from guppi_agent import create_app

from hr_agent import agent as agent_module


def build_strands_agent(token: str):
    """The orchestrator for one request, looked up at call time so tests can replace
    `hr_agent.agent.build_strands_agent`."""
    return agent_module.build_strands_agent(token)


app = create_app(build_strands_agent)
