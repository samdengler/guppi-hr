"""Writes the HR tools server's tool list as the tools gateway's inline MCP tool schema
(D47): infra/hr_super_agent_infra/hr_tools_schema.json. With an inline schema the gateway
never lists tools itself, so it never asks the issuer for a token without an employee in
it (aws-feedback A14). infra/tests checks the file matches the server.

    uv run -- python scripts/tools-schema.py
"""

import asyncio
import json
from pathlib import Path

from hr_agent.tools.server import build_server

OUT = Path(__file__).resolve().parents[1] / "infra" / "hr_super_agent_infra" / "hr_tools_schema.json"


def schema() -> dict:
    tools = asyncio.run(build_server().list_tools())
    return {"tools": [{"name": t.name, "description": t.description, "inputSchema": t.inputSchema}
                      for t in sorted(tools, key=lambda t: t.name)]}


if __name__ == "__main__":
    OUT.write_text(json.dumps(schema(), indent=2) + "\n")
    print(f"wrote {OUT} ({len(schema()['tools'])} tools)")
