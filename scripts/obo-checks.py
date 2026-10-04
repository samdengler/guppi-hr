# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3", "httpx>=0.27"]
# ///
"""Checks the on-behalf-of switch (D47) against the deployed stacks: each hop accepts its
own token and refuses the others, and Gateway Policy allows each tool only for its scope.

Tokens are minted the way the hops mint them, through AgentCore Identity with the
production credential providers, under the workload identity hr-obo-checks (created on
first use; only an administrator's credentials may call Identity for it). The test session's Okta token comes
from guppi-gpt's scripts/test-token.sh. Prints statuses and verdicts only, never a token
or a record.

    uv run scripts/obo-checks.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.parse
import uuid
from pathlib import Path

import boto3
import httpx

REGION = "us-east-1"
ROOT = Path(__file__).resolve().parents[1]
GUPPI_GPT = ROOT.parent / "guppi-gpt"
WORKLOAD = "hr-obo-checks"
ACCESS = "urn:ietf:params:oauth:token-type:access_token"
CANVAS = ["hr.tools.policy", "hr.tools.profile.read", "hr.tools.pay.statements.read"]
DOMAIN = {
    "profile": ["hr.tools.policy", "hr.tools.profile.read", "hr.tools.profile.write"],
    "pay": ["hr.tools.policy", "hr.tools.pay.statements.read", "hr.tools.pay.read", "hr.tools.pay.write"],
    "travel": ["hr.tools.policy"],
}
THREAD = f"obo-checks-{int(time.time())}"

identity = boto3.client("bedrock-agentcore", region_name=REGION)
control = boto3.client("bedrock-agentcore-control", region_name=REGION)
ssm = boto3.client("ssm", region_name=REGION)
failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{f'  ({detail})' if detail else ''}")
    if not ok:
        failures.append(label)


def provider(client: str) -> str:
    return ssm.get_parameter(Name=f"/guppi/obo/{client}/provider-name")["Parameter"]["Value"]


def exchange(client: str, subject: str, scopes: list[str]) -> str | None:
    try:
        wat = identity.get_workload_access_token_for_jwt(workloadName=WORKLOAD, userToken=subject)["workloadAccessToken"]
        return identity.get_resource_oauth2_token(
            workloadIdentityToken=wat, resourceCredentialProviderName=provider(client),
            oauth2Flow="ON_BEHALF_OF_TOKEN_EXCHANGE", scopes=scopes,
            customParameters={"subject_token_type": ACCESS})["accessToken"]
    except Exception:  # noqa: BLE001 - a refusal is the expected outcome for some checks
        return None


def a2a(url: str, token: str | None, session: str) -> int:
    body = {"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {"message": {
        "role": "user", "messageId": uuid.uuid4().hex, "contextId": session,
        "parts": [{"kind": "text", "text": "warm"}], "metadata": {"warm": True}}}}
    headers = {"Content-Type": "application/json", "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.post(url, json=body, headers=headers, timeout=90).status_code


class Mcp:
    def __init__(self, url: str, token: str | None) -> None:
        self.url, self.token, self.n = url, token, 0

    def send(self, method: str, params: dict | None = None) -> tuple[int, dict]:
        self.n += 1
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "X-Hr-Thread-Id": THREAD}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        response = httpx.post(self.url, json={"jsonrpc": "2.0", "id": self.n, "method": method,
                                              **({"params": params} if params else {})}, headers=headers, timeout=60)
        text = response.text
        if text.lstrip().startswith(("event:", "data:")):
            text = "\n".join(line[5:] for line in text.splitlines() if line.startswith("data:"))
        try:
            return response.status_code, json.loads(text) if text.strip() else {}
        except json.JSONDecodeError:
            return response.status_code, {}

    def tools(self) -> set[str]:
        return {t["name"] for t in self.send("tools/list")[1].get("result", {}).get("tools", [])}

    def call(self, tool: str, arguments: dict | None = None) -> str:
        """allowed, denied (by Policy), refused (by the tools server), or error."""
        return self.call_with_text(tool, arguments)[0]

    def call_with_text(self, tool: str, arguments: dict | None = None) -> tuple[str, str]:
        status, body = self.send("tools/call", {"name": tool, "arguments": arguments or {}})
        if status != 200:
            return f"http {status}", ""
        if "error" in body:
            return ("denied" if "policy" in json.dumps(body["error"]).lower() else "error"), ""
        result = body.get("result", {})
        text = ((result.get("content") or [{}])[0]).get("text", "")
        if result.get("isError"):
            return ("refused" if "Refused" in text or "not allowed" in text else "error"), text
        return "allowed", text


def main() -> None:
    if WORKLOAD not in {w["name"] for w in control.list_workload_identities().get("workloadIdentities", [])}:
        control.create_workload_identity(name=WORKLOAD)
    t0 = subprocess.run([str(GUPPI_GPT / "scripts" / "test-token.sh")], capture_output=True, text=True, check=True).stdout.strip()
    print("minting hop tokens through Identity")
    t1 = {d: exchange("hr-bridge", t0, [f"hr.agents.{d}"]) for d in DOMAIN}
    t1p = exchange("hr-bridge", t0, CANVAS)
    t2 = {d: exchange(f"hr-agent-{d}", t1[d], s) for d, s in DOMAIN.items()} if all(t1.values()) else {}
    t3 = exchange("hr-tools-gateway", t2.get("profile") or "", ["hr.tools.policy"])
    check("bridge gets an agents token per sub-agent and a canvas token", all(t1.values()) and bool(t1p))
    check("each sub-agent gets its domain's tools token", len([t for t in t2.values() if t]) == 3)
    check("the tools gateway's client gets a runtime token", bool(t3))
    if not (all(t1.values()) and t1p and len(t2) == 3 and t3):
        sys.exit("cannot continue without the hop tokens")

    print("issuer rules")
    check("travel cannot get pay scopes", exchange("hr-agent-travel", t1["travel"], ["hr.tools.pay.read"]) is None)
    check("the Travel agents token cannot become a Pay tools token", exchange("hr-agent-pay", t1["travel"], DOMAIN["pay"]) is None)
    check("the canvas token cannot see bank details", exchange("hr-bridge", t0, ["hr.tools.pay.read"]) is None)
    check("a canvas token cannot become an agents token", exchange("hr-bridge", t1p, ["hr.agents.pay"]) is None)
    check("a tools token cannot be exchanged by a sub-agent", exchange("hr-agent-pay", t2["pay"], DOMAIN["pay"]) is None)
    check("a runtime token cannot be exchanged again", exchange("hr-tools-gateway", t3, ["hr.tools.policy"]) is None)

    agents_url = ssm.get_parameter(Name="/guppi-hr/agents-gateway-url")["Parameter"]["Value"].rstrip("/")
    session = f"obo-checks-{uuid.uuid4().hex}"
    print("agents gateway")
    check("the Travel agents token reaches Travel", a2a(f"{agents_url}/travel/invocations", t1["travel"], session) == 200)
    status = a2a(f"{agents_url}/pay/invocations", t1["travel"], session)
    check("the Travel agents token cannot drive Pay", status != 200, f"HTTP {status}")
    for label, token in (("the Okta token", t0), ("the canvas token", t1p), ("a sub-agent's tools token", t2["pay"]), ("no token", None)):
        status = a2a(f"{agents_url}/travel/invocations", token, session)
        check(f"{label} is refused", status in (401, 403), f"HTTP {status}")

    runtimes = {r["agentRuntimeName"]: r for r in control.list_agent_runtimes()["agentRuntimes"]}

    def runtime_url(name: str) -> str:
        arn = control.get_agent_runtime(agentRuntimeId=runtimes[name]["agentRuntimeId"])["agentRuntimeArn"]
        return f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{urllib.parse.quote(arn, safe='')}/invocations?qualifier=DEFAULT"

    print("sub-agent runtime, called directly")
    travel = runtime_url("hr_super_agent_travel")
    for label, token in (("the Okta token", t0), ("the canvas token", t1p), ("a tools token", t2["travel"]),
                         ("the Pay agents token", t1["pay"])):
        status = a2a(travel, token, session)
        check(f"{label} is refused", status in (401, 403), f"HTTP {status}")

    tools_url = next(g for g in control.list_gateways()["items"] if g["name"] == "hr-super-agent-tools")
    tools_url = control.get_gateway(gatewayIdentifier=tools_url["gatewayId"])["gatewayUrl"]
    print("tools gateway and Gateway Policy")
    for label, token in (("the Okta token", t0), ("an agents token", t1["pay"]), ("the runtime token", t3)):
        status = Mcp(tools_url, token).send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                                           "clientInfo": {"name": "obo-checks", "version": "0"}})[0]
        check(f"{label} is refused", status in (401, 403), f"HTTP {status}")
    expected_lists = {
        "travel": {"docs___Retrieve", "hr___open_ticket"},
        "pay": {"docs___Retrieve", "hr___open_ticket", "hr___get_direct_deposit",
                "hr___list_pay_statements", "hr___propose_direct_deposit_change", "hr___commit_change"},
        "profile": {"docs___Retrieve", "hr___open_ticket", "hr___get_profile",
                    "hr___propose_address_change", "hr___propose_emergency_contact_change", "hr___commit_change"},
    }
    for domain, expected in expected_lists.items():
        listed = Mcp(tools_url, t2[domain]).tools()
        check(f"{domain} token lists only its tools", listed == expected, f"{sorted(listed - expected)} extra, {sorted(expected - listed)} missing")
    canvas_listed = Mcp(tools_url, t1p).tools()
    check("canvas token lists reads and tickets only",
          canvas_listed == {"docs___Retrieve", "hr___open_ticket", "hr___get_profile", "hr___list_pay_statements"},
          f"{sorted(canvas_listed)}")
    check("profile token reads the profile", Mcp(tools_url, t2["profile"]).call("hr___get_profile") == "allowed")
    check("travel token cannot read pay", Mcp(tools_url, t2["travel"]).call("hr___list_pay_statements") == "denied")
    check("profile token cannot read pay", Mcp(tools_url, t2["profile"]).call("hr___list_pay_statements") == "denied")
    check("canvas token reads pay statements", Mcp(tools_url, t1p).call("hr___list_pay_statements") == "allowed")
    deposit = {"routing_number": "011000015", "account_number": "000000000", "account_type": "checking"}
    check("canvas token cannot propose a deposit change", Mcp(tools_url, t1p).call("hr___propose_direct_deposit_change", deposit) == "denied")
    check("canvas token cannot commit", Mcp(tools_url, t1p).call("hr___commit_change", {"proposal_id": "x"}) == "denied")
    check("canvas token cannot read bank details", Mcp(tools_url, t1p).call("hr___get_direct_deposit") == "denied")
    check("profile token cannot propose a deposit change",
          Mcp(tools_url, t2["profile"]).call("hr___propose_direct_deposit_change", deposit) == "denied")
    # A pending proposal on the synthetic record, never committed; it expires on its own.
    outcome, text = Mcp(tools_url, t2["pay"]).call_with_text("hr___propose_direct_deposit_change", deposit)
    proposal_id = json.loads(text).get("proposal_id") if outcome == "allowed" else None
    check("pay token proposes a deposit change", bool(proposal_id), outcome)
    if proposal_id:
        outcome, text = Mcp(tools_url, t2["profile"]).call_with_text("hr___commit_change", {"proposal_id": proposal_id})
        check("profile token cannot commit the pay proposal", outcome == "refused" and "may not change" in text, outcome)

    print("tools runtime, called directly")
    tools_runtime = runtime_url("hr_super_agent_tools")
    init = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "obo-checks", "version": "0"}}
    for label, token in (("a sub-agent's tools token", t2["profile"]), ("the canvas token", t1p), ("the Okta token", t0)):
        status = Mcp(tools_runtime, token).send("initialize", init)[0]
        check(f"{label} is refused", status in (401, 403), f"HTTP {status}")
    status = Mcp(tools_runtime, t3).send("initialize", init)[0]
    check("the gateway's runtime token gets in", status == 200, f"HTTP {status}")

    print(f"\n{len(failures)} failed" if failures else "\nall checks passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
