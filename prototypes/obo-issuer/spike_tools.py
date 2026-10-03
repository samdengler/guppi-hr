"""Spike for the AgentCore key stack (Gateway + Policy + Identity + Runtime), D20.

    ../../.venv/bin/python spike_tools.py

1. A test copy of the HR tools runtime (same image, role and tables) whose JWT authorizer
   and token verifier trust the prototype issuer, behind a test MCP gateway that trusts the
   issuer inbound and exchanges each caller's token (OAuth TOKEN_EXCHANGE) toward the
   runtime. Times get_profile in one MCP session and counts exchanges, beside today's tools
   gateway as a baseline.
2. Policy in AgentCore on that gateway: Cedar rules that allow each tool only for a token
   holding its scope. Profile, Pay and Travel tokens call tools they may and may not use.
Prints statuses, timings and decisions only.
"""

from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3

import run
import spike

REGION = "us-east-1"
TOOLS_COPY = "obo_spike_tools"
TOOLS_GATEWAY = "obo-spike-tools-gw"
ENGINE = "obo_spike_policy"
control = spike.control
logs = boto3.client("logs", region_name=REGION)


class Mcp:
    """A minimal MCP client that keeps one session, as the sub-agents do (D38)."""

    def __init__(self, url: str, token: str, extra: dict | None = None) -> None:
        self.url, self.token, self.extra, self.sid, self.next = url, token, extra or {}, None, 1

    def send(self, method: str, params: dict | None = None, notify: bool = False) -> tuple[int, dict | None]:
        body = {"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})}
        if not notify:
            body["id"] = self.next
            self.next += 1
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                   "Authorization": f"Bearer {self.token}", **self.extra}
        if self.sid:
            headers["Mcp-Session-Id"] = self.sid
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                self.sid = response.headers.get("Mcp-Session-Id") or self.sid
                raw = response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, {"error": error.read().decode(errors="replace")[:300]}
        if not raw.strip():
            return response.status, None
        if raw.lstrip().startswith("event:") or raw.lstrip().startswith("data:"):
            raw = "\n".join(line[5:] for line in raw.splitlines() if line.startswith("data:"))
        return response.status, json.loads(raw)

    def open(self) -> int:
        status, _ = self.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                             "clientInfo": {"name": "obo-spike", "version": "0"}})
        self.send("notifications/initialized", notify=True)
        return status

    def tools(self) -> list[str]:
        _, body = self.send("tools/list")
        return sorted(t["name"] for t in (body or {}).get("result", {}).get("tools", []))

    def call(self, name: str, arguments: dict | None = None) -> str:
        status, body = self.send("tools/call", {"name": name, "arguments": arguments or {}})
        if status != 200 or body is None:
            return f"HTTP {status} {json.dumps(body)[:160]}"
        if "error" in body:
            return f"error: {body['error'].get('message', '')[:160]}"
        result = body["result"]
        text = (result.get("content") or [{}])[0].get("text", "")
        return ("tool error: " if result.get("isError") else "ok: ") + text[:80].replace("\n", " ")


def exchanges_since(start_ms: int, issuer_fn: str) -> int:
    events = logs.filter_log_events(logGroupName=f"/aws/lambda/{issuer_fn}", startTime=start_ms,
                                    filterPattern='"token-exchange"').get("events", [])
    return sum(1 for e in events if "Python-urllib" not in e["message"])


def timed_calls(client: Mcp, name: str, n: int) -> list[int]:
    out = []
    for _ in range(n):
        a = time.perf_counter()
        result = client.call(name)
        out.append(round((time.perf_counter() - a) * 1000))
        if not result.startswith("ok"):
            print(f"    {name}: {result}")
    return out


def main() -> None:
    s = spike.Spike()
    issuer_fn = next(f["FunctionName"] for f in boto3.client("lambda", region_name=REGION).list_functions()["Functions"]
                     if f["FunctionName"].startswith("GuppiOboPrototype-Issuer"))

    # Tokens a caller of the tools gateway would hold: T2 per domain (agent client), T1p (bridge).
    tokens = {
        "Profile T2": s.token("prototype-agent", s.t1, "hr.tools.policy hr.tools.profile.read hr.tools.profile.write"),
        "Pay T2": s.token("prototype-agent", s.t1, "hr.tools.policy hr.tools.pay.read hr.tools.pay.write"),
        "Travel T2": s.token("prototype-agent", s.t1, "hr.tools.policy"),
        "canvas T1p": s.token("prototype-bridge", s.t0, "hr.tools.policy hr.tools.profile.read hr.tools.pay.read"),
    }

    print("\n1. the tools runtime behind an exchanging gateway")
    real = next(r for r in control.list_agent_runtimes()["agentRuntimes"] if r["agentRuntimeName"] == "hr_super_agent_tools")
    real = control.get_agent_runtime(agentRuntimeId=real["agentRuntimeId"])
    env = dict(real["environmentVariables"])
    env.update({"TOKEN_ISSUER": s.issuer, "TOKEN_JWKS_URL": f"{s.issuer}/jwks.json", "TOKEN_AUDIENCE": "api://hr-tools",
                "TOKEN_USE": ""})
    env.pop("TOKEN_ALLOWED_CLIENTS", None)
    config = dict(
        agentRuntimeArtifact=real["agentRuntimeArtifact"], roleArn=real["roleArn"],
        networkConfiguration={"networkMode": "PUBLIC"}, protocolConfiguration={"serverProtocol": "MCP"},
        environmentVariables=env,
        requestHeaderConfiguration=real["requestHeaderConfiguration"],
        authorizerConfiguration={"customJWTAuthorizer": {
            "discoveryUrl": s.discovery, "allowedAudience": ["api://hr-tools"], "allowedClients": ["prototype-bridge"]}},
    )
    existing = [r for r in control.list_agent_runtimes()["agentRuntimes"] if r["agentRuntimeName"] == TOOLS_COPY]
    if existing:
        rid = existing[0]["agentRuntimeId"]
        control.update_agent_runtime(agentRuntimeId=rid, **config)
    else:
        rid = control.create_agent_runtime(agentRuntimeName=TOOLS_COPY, **config)["agentRuntimeId"]
    for _ in range(60):
        state = control.get_agent_runtime(agentRuntimeId=rid)
        if state["status"] in ("READY", "CREATE_FAILED", "UPDATE_FAILED"):
            break
        time.sleep(5)
    print(f"  tools runtime copy: {state['status']}")
    endpoint = (f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/"
                f"{urllib.parse.quote(state['agentRuntimeArn'], safe='')}/invocations?qualifier=DEFAULT")

    gw = spike.fresh_gateway(TOOLS_GATEWAY, roleArn=s.outputs["GatewayRoleArn"], protocolType="MCP",
                             authorizerType="CUSTOM_JWT", authorizerConfiguration={"customJWTAuthorizer": {
                                 "discoveryUrl": s.discovery, "allowedAudience": ["api://hr-tools"],
                                 "allowedClients": ["prototype-agent", "prototype-bridge"]}},
                             exceptionLevel="DEBUG")
    print(f"  tools gateway: {gw['status']}")
    target = control.create_gateway_target(
        gatewayIdentifier=gw["gatewayId"], name="hr",
        targetConfiguration={"mcp": {"mcpServer": {"endpoint": endpoint}}},
        credentialProviderConfigurations=[{"credentialProviderType": "OAUTH", "credentialProvider": {"oauthCredentialProvider": {
            "providerArn": spike.provider_arn("obo-prototype-bridge"), "scopes": ["hr.tools.policy"],
            "grantType": "TOKEN_EXCHANGE", "customParameters": {"subject_token_type": run.ACCESS}}}}],
        metadataConfiguration={"allowedRequestHeaders": ["X-Hr-User-Token", "X-Hr-Thread-Id"]})
    tstate = spike.wait_target(gw["gatewayId"], target["targetId"])
    print(f"  target hr: {tstate['status']} {tstate.get('statusReasons') or ''}")
    time.sleep(10)
    url = gw["gatewayUrl"]

    # The tools server reads the employee from X-Hr-User-Token; the copy verifies this issuer's tokens.
    profile = tokens["Profile T2"]
    client = Mcp(url, profile, {"X-Hr-User-Token": profile, "X-Hr-Thread-Id": f"obo-spike-{int(time.time())}"})
    print("  initialize:", client.open(), "| session id from gateway:", bool(client.sid))
    print("  tools/list:", client.tools())
    start = int(time.time() * 1000)
    times = timed_calls(client, "hr___get_profile", 8)
    time.sleep(15)
    print(f"  get_profile x8 in one session: {times} ms; exchanges seen by the issuer: {exchanges_since(start, issuer_fn)}")

    # Baseline: today's tools gateway (Okta token, IAM target), same tool, one session.
    real_gw = next(g for g in control.list_gateways()["items"] if g["name"] == "hr-super-agent-tools")
    real_url = control.get_gateway(gatewayIdentifier=real_gw["gatewayId"])["gatewayUrl"]
    base = Mcp(real_url, s.t0, {"X-Hr-User-Token": s.t0, "X-Hr-Thread-Id": f"obo-spike-base-{int(time.time())}"})
    base.open()
    print(f"  baseline, today's tools gateway, get_profile x8: {timed_calls(base, 'hr___get_profile', 8)} ms")

    print("\n2. Policy in AgentCore on the tools gateway")
    engines = [e for e in control.list_policy_engines().get("policyEngines", []) if e["name"] == ENGINE]
    if engines:
        engine_id = engines[0]["policyEngineId"]
    else:
        engine_id = control.create_policy_engine(name=ENGINE, description="Throwaway: D20 spike")["policyEngineId"]
    for _ in range(40):
        engine = control.get_policy_engine(policyEngineId=engine_id)
        if engine["status"] in ("ACTIVE", "READY", "CREATE_FAILED", "FAILED"):
            break
        time.sleep(3)
    print(f"  policy engine: {engine['status']}")
    gw_arn = control.get_gateway(gatewayIdentifier=gw["gatewayId"])["gatewayArn"]
    rules = {
        "profile_read": ("hr.tools.profile.read", ["hr___get_profile"]),
        "profile_write": ("hr.tools.profile.write", ["hr___propose_address_change", "hr___propose_emergency_contact_change"]),
        "pay_read": ("hr.tools.pay.read", ["hr___get_direct_deposit", "hr___list_pay_statements"]),
        "pay_write": ("hr.tools.pay.write", ["hr___propose_direct_deposit_change"]),
        "policy": ("hr.tools.policy", ["hr___open_ticket"]),
    }
    for p in control.list_policies(policyEngineId=engine_id).get("policies", []):
        control.delete_policy(policyEngineId=engine_id, policyId=p["policyId"])
    time.sleep(5)
    for name, (scope, actions) in rules.items():
        statement = (
            "permit(\n  principal is AgentCore::OAuthUser,\n"
            f"  action in [{', '.join(f'AgentCore::Action::\"{a}\"' for a in actions)}],\n"
            f"  resource == AgentCore::Gateway::\"{gw_arn}\"\n)\n"
            f"when {{ principal.hasTag(\"scope\") && principal.getTag(\"scope\") like \"*{scope}*\" }};"
        )
        created = control.create_policy(policyEngineId=engine_id, name=name, definition={"cedar": {"statement": statement}},
                                        validationMode="FAIL_ON_ANY_FINDINGS")
        for _ in range(40):
            p = control.get_policy(policyEngineId=engine_id, policyId=created["policyId"])
            if p["status"] not in ("CREATING",):
                break
            time.sleep(3)
        print(f"  policy {name}: {p['status']} {p.get('statusReasons') or ''}")
    state = control.get_gateway(gatewayIdentifier=gw["gatewayId"])
    control.update_gateway(gatewayIdentifier=gw["gatewayId"], name=state["name"], roleArn=state["roleArn"],
                           protocolType=state["protocolType"], authorizerType=state["authorizerType"],
                           authorizerConfiguration=state["authorizerConfiguration"], exceptionLevel="DEBUG",
                           policyEngineConfiguration={"arn": engine["policyEngineArn"], "mode": "ENFORCE"})
    print(f"  gateway with the engine attached: {spike.wait_gateway(gw['gatewayId'])['status']}")
    time.sleep(20)
    for label, token in tokens.items():
        c = Mcp(url, token, {"X-Hr-User-Token": token, "X-Hr-Thread-Id": f"obo-spike-p-{int(time.time())}"})
        c.open()
        print(f"  {label}: tools/list {c.tools()}")
        for tool in ("hr___get_profile", "hr___list_pay_statements", "hr___propose_direct_deposit_change"):
            if tool.endswith("deposit_change") and label == "Pay T2":
                continue  # allowed for Pay; not called, so the spike writes no proposal
            args = {"routing_number": "011000015", "account_number": "000000000", "account_type": "checking"} \
                if tool.endswith("deposit_change") else {}
            print(f"    {tool}: {c.call(tool, args)}")
    c = Mcp(url, profile, {"X-Hr-User-Token": profile, "X-Hr-Thread-Id": f"obo-spike-pt-{int(time.time())}"})
    c.open()
    print(f"  Profile T2 with Policy on, get_profile x8: {timed_calls(c, 'hr___get_profile', 8)} ms")
    print(f"\nleft in place: runtime {TOOLS_COPY}, gateway {TOOLS_GATEWAY}, policy engine {ENGINE}")


if __name__ == "__main__":
    main()
