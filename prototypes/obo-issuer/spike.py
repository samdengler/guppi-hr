"""Spike after the design critique (D20). Prints claims summaries and statuses only.

    ../../.venv/bin/python spike.py scopes runtime exchange

scopes    What the gateway's JWT authorizer enforces: `scope` or `scp` alone, a wrong scope at
          the right audience, the wrong audience, all-of or any-of for `allowedScopes`, and
          `allowedClients` against this issuer's `client_id`.
runtime   A throwaway runtime (an existing HR sub-agent image) whose authorizer trusts this
          issuer with `allowedClients` and `allowedScopes`, invoked directly.
exchange  Gateways that exchange the employee's Okta token themselves: an MCP server target
          and an HTTP target with OAuth `TOKEN_EXCHANGE`, the runtime as an HTTP target too.
          Needs the gateway role's exchange and invoke permissions in app.py.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3

import run

REGION = "us-east-1"
SPIKE_RUNTIME = "obo_spike_rt"
MCP_GATEWAY = "obo-spike-mcp-gw2"  # the first one's target stuck in CREATING
HTTP_GATEWAY = "obo-spike-http-gw"

control = boto3.client("bedrock-agentcore-control", region_name=REGION)


def post(url: str, token: str | None, body: dict, extra: dict | None = None) -> tuple[int, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **(extra or {})}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode(errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode(errors="replace")
    except Exception as error:  # noqa: BLE001
        return 0, f"{type(error).__name__}: {error}"


def wait_gateway(gateway_id: str) -> dict:
    for _ in range(60):
        state = control.get_gateway(gatewayIdentifier=gateway_id)
        if state["status"] in ("READY", "FAILED"):
            return state
        time.sleep(5)
    return state


def wait_target(gateway_id: str, target_id: str) -> dict:
    for _ in range(60):
        state = control.get_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
        if state["status"] in ("READY", "FAILED", "SYNCHRONIZE_UNSUCCESSFUL"):
            return state
        time.sleep(5)
    return state


def fresh_gateway(name: str, **kwargs) -> dict:
    for g in control.list_gateways().get("items", []):
        if g["name"] == name:
            for t in control.list_gateway_targets(gatewayIdentifier=g["gatewayId"]).get("items", []):
                control.delete_gateway_target(gatewayIdentifier=g["gatewayId"], targetId=t["targetId"])
            time.sleep(10)
            control.delete_gateway(gatewayIdentifier=g["gatewayId"])
            time.sleep(10)
    created = control.create_gateway(name=name, **kwargs)
    return wait_gateway(created["gatewayId"])


def provider_arn(name: str) -> str:
    return control.get_oauth2_credential_provider(name=name)["credentialProviderArn"]


class Spike:
    def __init__(self) -> None:
        self.secret = {"prototype-bridge": secrets.token_urlsafe(32), "prototype-agent": secrets.token_urlsafe(32)}
        clients = {
            "prototype-bridge": {"secret_sha256": hashlib.sha256(self.secret["prototype-bridge"].encode()).hexdigest(),
                                 "scopes": ["hr.agents", "hr.agents.other", "hr.tools.policy", "hr.tools.profile.read", "hr.tools.pay.read"]},
            "prototype-agent": {"secret_sha256": hashlib.sha256(self.secret["prototype-agent"].encode()).hexdigest(),
                                "scopes": ["hr.agents.other", "hr.tools.policy", "hr.tools.profile", "hr.tools.pay",
                                           "hr.tools.profile.read", "hr.tools.profile.write", "hr.tools.pay.read", "hr.tools.pay.write"]},
        }
        ssm = boto3.client("ssm", region_name=REGION)
        self.okta_issuer = ssm.get_parameter(Name="/guppi/okta/issuer")["Parameter"]["Value"]
        self.okta_discovery = ssm.get_parameter(Name="/guppi/okta/discovery-url")["Parameter"]["Value"]
        print("deploying the prototype stack ...", flush=True)
        subprocess.run(["npx", "--yes", "aws-cdk@2", "deploy", "GuppiOboPrototype", "--require-approval", "never",
                        "-c", f"upstream_issuer={self.okta_issuer}", "-c", f"clients={json.dumps(clients)}",
                        "--outputs-file", "outputs.json"], cwd=run.HERE, check=True, capture_output=True, text=True)
        self.outputs = json.loads((run.HERE / "outputs.json").read_text())["GuppiOboPrototype"]
        self.issuer = self.outputs["IssuerUrl"].rstrip("/")
        self.discovery = f"{self.issuer}/.well-known/openid-configuration"
        self.t0 = subprocess.run([str(run.GUPPI_GPT / "scripts/test-token.sh")], capture_output=True, text=True,
                                 check=True).stdout.strip()
        self.t1 = self.token("prototype-bridge", self.t0, "hr.agents")
        # Credential providers with this deploy's secrets, for the gateways that exchange.
        have = {p["name"] for p in control.list_oauth2_credential_providers().get("credentialProviders", [])}
        for name, client in (("obo-prototype-bridge", "prototype-bridge"),):
            if name in have:
                control.delete_oauth2_credential_provider(name=name)
            control.create_oauth2_credential_provider(
                name=name, credentialProviderVendor="CustomOauth2",
                oauth2ProviderConfigInput={"customOauth2ProviderConfig": {
                    "oauthDiscovery": {"discoveryUrl": self.discovery},
                    "clientId": client, "clientSecret": self.secret[client],
                    "clientAuthenticationMethod": "CLIENT_SECRET_BASIC",
                    "onBehalfOfTokenExchangeConfig": {"grantType": "TOKEN_EXCHANGE",
                                                      "tokenExchangeGrantTypeConfig": {"actorTokenContent": "NONE"}}}})

    def token(self, client: str, subject: str, scope: str, shape: str = "both") -> str:
        body = urllib.parse.urlencode({"grant_type": run.TOKEN_EXCHANGE, "subject_token": subject,
                                       "subject_token_type": run.ACCESS, "scope": scope, "shape": shape}).encode()
        import base64
        basic = base64.b64encode(f"{client}:{self.secret[client]}".encode()).decode()
        request = urllib.request.Request(f"{self.issuer}/token", data=body, headers={
            "Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)["access_token"]

    # -- scopes --------------------------------------------------------------------------

    def scopes(self) -> None:
        print("\nscopes: the gateway's JWT authorizer")
        gw = next(g for g in control.list_gateways()["items"] if g["name"] == run.GATEWAY)
        gid = gw["gatewayId"]

        def configure(**authorizer) -> str:
            state = control.get_gateway(gatewayIdentifier=gid)
            control.update_gateway(gatewayIdentifier=gid, name=state["name"], roleArn=state["roleArn"],
                                   protocolType=state["protocolType"], authorizerType="CUSTOM_JWT",
                                   authorizerConfiguration={"customJWTAuthorizer": {
                                       "discoveryUrl": self.discovery, "allowedAudience": ["api://hr-agents"], **authorizer}})
            state = wait_gateway(gid)
            time.sleep(15)
            return state["gatewayUrl"]

        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "obo-spike", "version": "0"}}}

        url = configure(allowedScopes=["hr.agents"])
        print("  allowedScopes [hr.agents]")
        cases = {
            "scope and scp, hr.agents": self.t1,
            "scope string only, hr.agents": self.token("prototype-bridge", self.t0, "hr.agents", "scope"),
            "scp list only, hr.agents": self.token("prototype-bridge", self.t0, "hr.agents", "scp"),
            "right audience, wrong scope (hr.agents.other)": self.token("prototype-bridge", self.t0, "hr.agents.other"),
            "wrong audience (api://hr-tools, hr.tools.policy)": self.token("prototype-bridge", self.t0, "hr.tools.policy"),
            "two scopes, hr.agents hr.agents.other": self.token("prototype-bridge", self.t0, "hr.agents hr.agents.other"),
        }
        for label, token in cases.items():
            print(f"    {label}: {post(url, token, init)[0]}")

        url = configure(allowedScopes=["hr.agents", "hr.agents.other"])
        print("  allowedScopes [hr.agents, hr.agents.other]")
        print(f"    hr.agents alone: {post(url, self.t1, init)[0]}")
        print(f"    both scopes: {post(url, cases['two scopes, hr.agents hr.agents.other'], init)[0]}")

        url = configure(allowedScopes=["hr.agents.other"], allowedClients=["prototype-bridge"])
        print("  allowedScopes [hr.agents.other], allowedClients [prototype-bridge]")
        bridge = cases["right audience, wrong scope (hr.agents.other)"]
        agent = self.token("prototype-agent", self.t1, "hr.agents.other")
        print(f"    bridge client: {post(url, bridge, init)[0]}")
        print(f"    agent client (same scope and audience): {post(url, agent, init)[0]}")
        configure(allowedScopes=["hr.agents"])

    # -- runtime -------------------------------------------------------------------------

    def runtime_arn(self) -> str:
        existing = [r for r in control.list_agent_runtimes().get("agentRuntimes", []) if r["agentRuntimeName"] == SPIKE_RUNTIME]
        travel = next(r for r in control.list_agent_runtimes()["agentRuntimes"] if r["agentRuntimeName"] == "hr_super_agent_travel")
        image = control.get_agent_runtime(agentRuntimeId=travel["agentRuntimeId"])["agentRuntimeArtifact"]
        config = dict(
            agentRuntimeArtifact=image, roleArn=self.outputs["RuntimeRoleArn"],
            networkConfiguration={"networkMode": "PUBLIC"}, protocolConfiguration={"serverProtocol": "A2A"},
            authorizerConfiguration={"customJWTAuthorizer": {
                "discoveryUrl": self.discovery, "allowedAudience": ["api://hr-agents"],
                "allowedClients": ["prototype-bridge"], "allowedScopes": ["hr.agents"]}},
            requestHeaderConfiguration={"requestHeaderAllowlist": ["Authorization"]},
        )
        if existing:
            rid = existing[0]["agentRuntimeId"]
            control.update_agent_runtime(agentRuntimeId=rid, **config)
        else:
            rid = control.create_agent_runtime(agentRuntimeName=SPIKE_RUNTIME, **config)["agentRuntimeId"]
        for _ in range(60):
            state = control.get_agent_runtime(agentRuntimeId=rid)
            if state["status"] in ("READY", "CREATE_FAILED", "UPDATE_FAILED"):
                break
            time.sleep(5)
        print(f"  runtime {SPIKE_RUNTIME}: {state['status']}")
        return state["agentRuntimeArn"]

    def runtime(self) -> None:
        print("\nruntime: a runtime authorizer with allowedClients and allowedScopes")
        arn = self.runtime_arn()
        url = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{urllib.parse.quote(arn, safe='')}/invocations?qualifier=DEFAULT"
        message = {"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {"message": {
            "role": "user", "messageId": "spike-1", "parts": [{"kind": "text", "text": "warm"}], "metadata": {"warm": True}}}}
        session = {"X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"obo-spike-{int(time.time())}-0000000000000000"}
        time.sleep(10)
        cases = {
            "T1 (bridge client, hr.agents)": self.t1,
            "agent client, hr.agents.other": self.token("prototype-agent", self.t1, "hr.agents.other"),
            "bridge client, hr.agents.other": self.token("prototype-bridge", self.t0, "hr.agents.other"),
            "T0 (Okta)": self.t0,
            "no token": None,
        }
        for label, token in cases.items():
            status, text = post(url, token, message, session)
            print(f"    {label}: {status} {text[:140]!r}")

    # -- exchange ------------------------------------------------------------------------

    def exchange(self) -> None:
        print("\nexchange: the gateway exchanges the Okta token itself")
        okta_authorizer = {"customJWTAuthorizer": {"discoveryUrl": self.okta_discovery, "allowedAudience": ["api://guppi"]}}
        oauth = lambda scopes: [{"credentialProviderType": "OAUTH", "credentialProvider": {"oauthCredentialProvider": {  # noqa: E731
            "providerArn": provider_arn("obo-prototype-bridge"), "scopes": scopes, "grantType": "TOKEN_EXCHANGE",
            "customParameters": {"subject_token_type": run.ACCESS}}}}]

        # An MCP gateway with an MCP server target (the shape of the tools gateway).
        gw = fresh_gateway(MCP_GATEWAY, roleArn=self.outputs["GatewayRoleArn"], protocolType="MCP",
                           authorizerType="CUSTOM_JWT", authorizerConfiguration=okta_authorizer)
        print(f"  MCP gateway: {gw['status']}")
        tool_schema = json.dumps({"tools": [{"name": "whoami", "description": "Returns the claims of the token the server received.",
                                             "inputSchema": {"type": "object", "properties": {}}}]})
        for label, extra in (("listed at sync", {}), ("schema given", {"mcpToolSchema": {"inlinePayload": tool_schema}})):
            try:
                target = control.create_gateway_target(
                    gatewayIdentifier=gw["gatewayId"], name="whoami" if not extra else "whoamischema",
                    targetConfiguration={"mcp": {"mcpServer": {"endpoint": f"{self.issuer}/mcp", **extra}}},
                    credentialProviderConfigurations=oauth(["hr.tools.policy"]))
                state = wait_target(gw["gatewayId"], target["targetId"])
                print(f"  MCP server target, {label}: {state['status']} {state.get('statusReasons') or ''}")
            except Exception as error:  # noqa: BLE001
                print(f"  MCP server target, {label}: refused: {str(error)[:300]}")
        time.sleep(10)
        url = gw["gatewayUrl"]
        print("  initialize with T0:", post(url, self.t0, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "obo-spike", "version": "0"}}})[0])
        status, text = post(url, self.t0, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        print(f"  tools/list with T0: {status} {text[:300]!r}")
        for name in ("whoami___whoami", "whoamischema___whoami"):
            status, text = post(url, self.t0, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                               "params": {"name": name, "arguments": {}}})
            print(f"  tools/call {name} with T0: {status} {text[:600]!r}")

    def http(self) -> None:
        """A gateway with HTTP targets (the shape of the agents gateway): the spike runtime,
        and a passthrough endpoint that echoes the token it got."""
        print("\nhttp: the gateway exchanges the Okta token itself")
        okta_authorizer = {"customJWTAuthorizer": {"discoveryUrl": self.okta_discovery, "allowedAudience": ["api://guppi"]}}
        oauth = lambda scopes: [{"credentialProviderType": "OAUTH", "credentialProvider": {"oauthCredentialProvider": {  # noqa: E731
            "providerArn": provider_arn("obo-prototype-bridge"), "scopes": scopes, "grantType": "TOKEN_EXCHANGE",
            "customParameters": {"subject_token_type": run.ACCESS}}}}]
        gw = fresh_gateway(HTTP_GATEWAY, roleArn=self.outputs["GatewayRoleArn"],
                           authorizerType="CUSTOM_JWT", authorizerConfiguration=okta_authorizer)
        print(f"  HTTP gateway: {gw['status']}")
        targets = {
            "echo": {"http": {"passthrough": {"endpoint": f"{self.issuer}/echo", "protocolType": "CUSTOM"}}},
            "rt": {"http": {"agentcoreRuntime": {"arn": self.runtime_arn(), "qualifier": "DEFAULT"}}},
        }
        for name, config in targets.items():
            try:
                target = control.create_gateway_target(gatewayIdentifier=gw["gatewayId"], name=name,
                                                       targetConfiguration=config,
                                                       credentialProviderConfigurations=oauth(["hr.agents"]))
                state = wait_target(gw["gatewayId"], target["targetId"])
                print(f"  HTTP target {name}: {state['status']} {state.get('statusReasons') or ''}")
            except Exception as error:  # noqa: BLE001
                print(f"  HTTP target {name}: refused: {str(error)[:300]}")
        time.sleep(10)
        url = gw["gatewayUrl"].rstrip("/")
        for path in ("echo", "echo/invocations"):
            status, text = post(f"{url}/{path}", self.t0, {"ping": True})
            print(f"  POST {path} with T0: {status} {text[:500]!r}")
        message = {"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {"message": {
            "role": "user", "messageId": "spike-2", "parts": [{"kind": "text", "text": "warm"}], "metadata": {"warm": True}}}}
        status, text = post(f"{url}/rt/invocations", self.t0, message,
                            {"X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": f"obo-spike-{int(time.time())}-1111111111111111"})
        print(f"  POST rt/invocations with T0: {status} {text[:300]!r}")


def main() -> None:
    parts = sys.argv[1:] or ["scopes", "runtime"]
    spike = Spike()
    print(f"issuer {spike.issuer}")
    for part in parts:
        getattr(spike, part)()


if __name__ == "__main__":
    main()
