"""On-behalf-of tokens for the HR hops (D20, D47; docs/proposals/obo-token-exchange.md).

The platform stack (guppi-gpt `obo.py`) runs the token-exchange issuer and one AgentCore
Identity credential provider per client, and publishes them under /guppi/obo/*. This
module reads them and holds what the HR side of the contract needs: the audiences and
scopes each checkpoint accepts, the grants a runtime needs to exchange through its
provider, and the Gateway Policy rules on the tools gateway.
"""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_iam as iam
from aws_cdk import aws_ssm as ssm
from constructs import Construct

PARAMS = "/guppi/obo"

TOOLS_AUDIENCE = "api://hr-tools"
TOOLS_RUNTIME_AUDIENCE = "api://hr-tools-runtime"
POLICY_SCOPE = "hr.tools.policy"


def agents_audience(domain: str) -> str:
    """Each sub-agent has its own agents audience and scope, so a token meant for one
    sub-agent cannot drive another (critique of the build, finding 3)."""
    return f"api://hr-agents/{domain}"


def agents_scope(domain: str) -> str:
    return f"hr.agents.{domain}"


BRIDGE_CLIENT = "hr-bridge"
TOOLS_GATEWAY_CLIENT = "hr-tools-gateway"
DOMAIN_SCOPES = {
    "profile": [POLICY_SCOPE, "hr.tools.profile.read", "hr.tools.profile.write"],
    "pay": [POLICY_SCOPE, "hr.tools.pay.statements.read", "hr.tools.pay.read", "hr.tools.pay.write"],
    "travel": [POLICY_SCOPE],
}
# The canvas reads the profile and pay statements, never bank details or writes.
CANVAS_SCOPES = [POLICY_SCOPE, "hr.tools.profile.read", "hr.tools.pay.statements.read"]


def agent_client(domain: str) -> str:
    return f"hr-agent-{domain}"


AGENT_CLIENTS = [agent_client(d) for d in DOMAIN_SCOPES]

# Gateway Policy on the tools gateway: each tool for the tokens that hold its scope (A15).
# A request is allowed only when a rule permits it, so a tool missing here is refused. The
# knowledge base target no longer offers docs___AgenticRetrieveStream at all (D48). The HR tools server checks the same table again (hr_agent.tools.scopes; a
# test holds the two together).
TOOL_SCOPES: dict[str, list[str]] = {
    POLICY_SCOPE: ["docs___Retrieve", "hr___open_ticket"],
    "hr.tools.profile.read": ["hr___get_profile"],
    "hr.tools.profile.write": ["hr___propose_address_change", "hr___propose_emergency_contact_change"],
    "hr.tools.pay.statements.read": ["hr___list_pay_statements"],
    "hr.tools.pay.read": ["hr___get_direct_deposit"],
    "hr.tools.pay.write": ["hr___propose_direct_deposit_change"],
}
# commit_change takes a proposal id, so Policy lets any writer call it and the tools server
# checks the proposal's field against the token's write scope (store.WRITE_SCOPE).
COMMIT_TOOL = "hr___commit_change"
WRITE_SCOPES = ["hr.tools.profile.write", "hr.tools.pay.write"]


def scope_condition(scope: str) -> str:
    # Every claim reaches Cedar as a string (A15), and Cedar cannot concatenate, so the scope
    # is matched as a whole word of the space-separated claim: alone, first, last or inside.
    # A bare "*scope*" would let hr.tools.pay match hr.tools.payroll.
    tag = 'principal.getTag("scope")'
    patterns = (scope, f"{scope} *", f"* {scope}", f"* {scope} *")
    return "(" + " || ".join(f'{tag} like "{p}"' for p in patterns) + ")"


def policy_statements(gateway_arn: str) -> dict[str, str]:
    """Cedar statements by policy name."""
    statements = {}
    for scope, actions in TOOL_SCOPES.items():
        listed = ", ".join(f'AgentCore::Action::"{a}"' for a in actions)
        statements[scope.replace(".", "_")] = (
            "permit(\n  principal is AgentCore::OAuthUser,\n"
            f"  action in [{listed}],\n"
            f'  resource == AgentCore::Gateway::"{gateway_arn}"\n)\n'
            f'when {{ principal.hasTag("scope") && {scope_condition(scope)} }};'
        )
    writers = " || ".join(scope_condition(s) for s in WRITE_SCOPES)
    statements["commit_change"] = (
        "permit(\n  principal is AgentCore::OAuthUser,\n"
        f'  action == AgentCore::Action::"{COMMIT_TOOL}",\n'
        f'  resource == AgentCore::Gateway::"{gateway_arn}"\n)\n'
        f'when {{ principal.hasTag("scope") && ({writers}) }};'
    )
    return statements


@dataclass(frozen=True)
class Obo:
    discovery_url: str
    issuer: str

    @classmethod
    def read(cls, scope: Construct) -> "Obo":
        return cls(
            discovery_url=ssm.StringParameter.value_for_string_parameter(scope, f"{PARAMS}/discovery-url"),
            issuer=ssm.StringParameter.value_for_string_parameter(scope, f"{PARAMS}/issuer"),
        )

    def provider_name(self, scope: Construct, client: str) -> str:
        return ssm.StringParameter.value_for_string_parameter(scope, f"{PARAMS}/{client}/provider-name")

    def provider_arn(self, scope: Construct, client: str) -> str:
        return ssm.StringParameter.value_for_string_parameter(scope, f"{PARAMS}/{client}/provider-arn")

    @staticmethod
    def secret_arn(scope: Construct, client: str) -> str:
        """The client secret by its stable name (guppi-gpt names it guppi/obo/<client>), so a
        replaced secret keeps its grant."""
        stack = Stack.of(scope)
        # Secrets Manager adds a six-character suffix; matching exactly six keeps
        # guppi/obo/hr-bridge from also matching a later guppi/obo/hr-bridge-<anything>.
        return f"arn:aws:secretsmanager:{stack.region}:{stack.account}:secret:guppi/obo/{client}-??????"


def workload_identity(scope: Construct, construct_id: str, runtime_name: str) -> agentcore.CfnWorkloadIdentity:
    """The identity a runtime exchanges under. Its name falls under the runtime role's
    existing GetWorkloadAccessToken* grant ({runtime_name}-*)."""
    return agentcore.CfnWorkloadIdentity(scope, construct_id, name=f"{runtime_name}-obo")


def grant_secret(role: iam.IRole, secret_arn: str) -> None:
    """AgentCore Identity reads a provider's EXTERNAL client secret as the caller of
    GetResourceOauth2Token (aws-feedback A16), so the caller's role reads its own client's
    secret, and only that one."""
    role.add_to_principal_policy(
        iam.PolicyStatement(actions=["secretsmanager:GetSecretValue"], resources=[secret_arn])
    )


def grant_exchange(
    role: iam.Role, provider_arn: str, secret_arn: str, workload: agentcore.CfnWorkloadIdentity
) -> None:
    """Lets a runtime ask Identity for tokens through one credential provider only."""
    grant_secret(role, secret_arn)
    stack = Stack.of(role)
    role.add_to_policy(
        iam.PolicyStatement(
            actions=["bedrock-agentcore:GetResourceOauth2Token"],
            resources=[
                provider_arn,
                f"arn:aws:bedrock-agentcore:{stack.region}:{stack.account}:token-vault/default",
                f"arn:aws:bedrock-agentcore:{stack.region}:{stack.account}:workload-identity-directory/default",
                workload.attr_workload_identity_arn,
            ],
        )
    )
