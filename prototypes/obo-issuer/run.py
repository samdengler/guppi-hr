"""Deploy the prototype issuer and test it three ways. Prints claims and statuses only.

1. Direct RFC 8693 exchange: the harness's Okta token (T0) for an hr.agents token (T1)
   as the bridge client, then T1 for an hr.tools.profile token (T2) as the agent client,
   and the refusals (wrong secret, a scope the client lacks, a tampered token).
2. AgentCore Identity: a workload identity and an on-behalf-of credential provider pointed
   at this issuer; GetWorkloadAccessTokenForJWT then GetResourceOauth2Token.
3. AgentCore Gateway: a throwaway MCP gateway whose JWT authorizer trusts this issuer
   (audience api://hr-agents, scp containing hr.agents); T1 should pass, T0 should not.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
GUPPI_GPT = HERE.parents[2] / "guppi-gpt"
REGION = "us-east-1"
TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS = "urn:ietf:params:oauth:token-type:access_token"
WORKLOAD = "obo-prototype"
PROVIDER = "obo-prototype-bridge"
GATEWAY = "obo-prototype-gw"


def claims_of(token: str) -> dict:
    part = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def show(label: str, token: str) -> None:
    c = claims_of(token)
    print(f"  {label}: iss={'prototype' if 'execute-api' in c['iss'] else c['iss']} aud={c['aud']} scp={c.get('scp')} "
          f"client_id={c.get('client_id')} act={c.get('act')} ttl={c['exp'] - c['iat']}s sub_is_okta_uid={c['sub'].startswith('00u')}")


def exchange(issuer: str, client: str, secret: str, subject: str, scope: str) -> tuple[int, dict]:
    body = urllib.parse.urlencode({"grant_type": TOKEN_EXCHANGE, "subject_token": subject,
                                   "subject_token_type": ACCESS, "scope": scope}).encode()
    basic = base64.b64encode(f"{client}:{secret}".encode()).decode()
    request = urllib.request.Request(f"{issuer}/token", data=body, headers={
        "Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def mcp_status(url: str, token: str | None) -> int:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "obo-prototype", "version": "0"}}}).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=15) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def main() -> None:
    secrets_by_client = {"prototype-bridge": secrets.token_urlsafe(32), "prototype-agent": secrets.token_urlsafe(32)}
    clients = {
        "prototype-bridge": {"secret_sha256": hashlib.sha256(secrets_by_client["prototype-bridge"].encode()).hexdigest(),
                             "scopes": ["hr.agents", "hr.tools.policy"]},
        "prototype-agent": {"secret_sha256": hashlib.sha256(secrets_by_client["prototype-agent"].encode()).hexdigest(),
                            "scopes": ["hr.tools.policy", "hr.tools.profile", "hr.tools.pay"]},
    }
    ssm = boto3.client("ssm", region_name=REGION)
    upstream = ssm.get_parameter(Name="/guppi/okta/issuer")["Parameter"]["Value"]
    print("deploying the prototype stack ...", flush=True)
    subprocess.run(["npx", "--yes", "aws-cdk@2", "deploy", "GuppiOboPrototype", "--require-approval", "never",
                    "-c", f"upstream_issuer={upstream}", "-c", f"clients={json.dumps(clients)}",
                    "--outputs-file", "outputs.json"], cwd=HERE, check=True, capture_output=True, text=True)
    outputs = json.loads((HERE / "outputs.json").read_text())["GuppiOboPrototype"]
    issuer = outputs["IssuerUrl"].rstrip("/")
    print(f"issuer {issuer}")
    print("discovery:", sorted(json.load(urllib.request.urlopen(f"{issuer}/.well-known/openid-configuration"))))
    print("jwks keys:", len(json.load(urllib.request.urlopen(f"{issuer}/jwks.json"))["keys"]))

    t0 = subprocess.run([str(GUPPI_GPT / "scripts/test-token.sh")], capture_output=True, text=True, check=True).stdout.strip()
    print("\n1. direct exchange")
    status, body = exchange(issuer, "prototype-bridge", secrets_by_client["prototype-bridge"], t0, "hr.agents")
    print(f"  T0 -> T1 as the bridge: HTTP {status}")
    t1 = body.get("access_token", "")
    if t1:
        show("T1", t1)
    status, body = exchange(issuer, "prototype-agent", secrets_by_client["prototype-agent"], t1, "hr.tools.profile")
    print(f"  T1 -> T2 as the agent: HTTP {status}")
    if body.get("access_token"):
        show("T2", body["access_token"])
    print("  refusals:",
          "wrong secret", exchange(issuer, "prototype-bridge", "nope", t0, "hr.agents")[0],
          "| scope the client lacks", exchange(issuer, "prototype-bridge", secrets_by_client["prototype-bridge"], t0, "hr.tools.pay")[0],
          "| tampered token", exchange(issuer, "prototype-bridge", secrets_by_client["prototype-bridge"], t0[:-4] + "AAAA", "hr.agents")[0])

    print("\n2. AgentCore Identity on-behalf-of")
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)
    if WORKLOAD not in {w["name"] for w in control.list_workload_identities().get("workloadIdentities", [])}:
        control.create_workload_identity(name=WORKLOAD)
    if PROVIDER in {p["name"] for p in control.list_oauth2_credential_providers().get("credentialProviders", [])}:
        control.delete_oauth2_credential_provider(name=PROVIDER)
    control.create_oauth2_credential_provider(
        name=PROVIDER, credentialProviderVendor="CustomOauth2",
        oauth2ProviderConfigInput={"customOauth2ProviderConfig": {
            "oauthDiscovery": {"discoveryUrl": f"{issuer}/.well-known/openid-configuration"},
            "clientId": "prototype-bridge", "clientSecret": secrets_by_client["prototype-bridge"],
            "clientAuthenticationMethod": "CLIENT_SECRET_BASIC",
            "onBehalfOfTokenExchangeConfig": {"grantType": "TOKEN_EXCHANGE",
                                              "tokenExchangeGrantTypeConfig": {"actorTokenContent": "NONE"}},
        }})
    try:
        wat = data.get_workload_access_token_for_jwt(workloadName=WORKLOAD, userToken=t0)["workloadAccessToken"]
        print("  workload access token for the Okta JWT: ok")
        result = data.get_resource_oauth2_token(
            workloadIdentityToken=wat, resourceCredentialProviderName=PROVIDER,
            oauth2Flow="ON_BEHALF_OF_TOKEN_EXCHANGE", scopes=["hr.agents"],
            customParameters={"subject_token_type": ACCESS})
        token = result.get("accessToken")
        print("  GetResourceOauth2Token:", "token issued" if token else f"no token: {sorted(result)}")
        if token:
            show("T1 via AgentCore", token)
    except Exception as error:  # noqa: BLE001
        print(f"  failed: {type(error).__name__}: {str(error)[:400]}")

    print("\n3. AgentCore Gateway authorizer")
    existing = [g for g in control.list_gateways().get("items", []) if g["name"] == GATEWAY]
    for g in existing:
        control.delete_gateway(gatewayIdentifier=g["gatewayId"])
        time.sleep(5)
    gw = control.create_gateway(
        name=GATEWAY, roleArn=outputs["GatewayRoleArn"], protocolType="MCP", authorizerType="CUSTOM_JWT",
        authorizerConfiguration={"customJWTAuthorizer": {
            "discoveryUrl": f"{issuer}/.well-known/openid-configuration",
            "allowedAudience": ["api://hr-agents"],
            # AgentCore refuses scp as a custom claim and checks scopes itself.
            "allowedScopes": ["hr.agents"],
        }})
    for _ in range(40):
        state = control.get_gateway(gatewayIdentifier=gw["gatewayId"])
        if state["status"] in ("READY", "FAILED"):
            break
        time.sleep(5)
    print("  gateway status:", state["status"], state.get("statusReasons") or "")
    url = state["gatewayUrl"]
    time.sleep(10)
    print("  initialize with T1 (prototype issuer, hr.agents):", mcp_status(url, t1))
    print("  initialize with T0 (Okta, api://guppi):", mcp_status(url, t0))
    print("  initialize with no token:", mcp_status(url, None))
    print(f"\nleft in place for review: stack GuppiOboPrototype, workload {WORKLOAD}, provider {PROVIDER}, gateway {GATEWAY}")


if __name__ == "__main__":
    main()
