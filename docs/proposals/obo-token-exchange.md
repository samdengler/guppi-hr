# On-behalf-of token exchange for `/p/hr/` (D20)

Status: proposal, 3 October 2026. Sam asked for this as a high priority after the
critique's finding 1.

## What is wrong today

One token does everything. The page signs in with Cognito (federated to Google) and gets
an access token whose audience is the platform's client. That same token:

- reaches the bridge, which puts it on the Connect contact as `hrToken` (blanked after the
  greeting since D42, but the Agentic CX designer keeps the value it read for the whole
  conversation);
- goes from the designer to the agents gateway, and from every sub-agent to the tools
  gateway, as both `Authorization` and `X-Hr-User-Token`;
- is accepted by every HR hop, since all of them check only the platform client id
  (critique finding 17).

So a token taken from any hop opens all of them for its hour, and nothing in a token says
which agent acted for the employee.

## What on-behalf-of exchange gives

At each hop the caller trades the token it received for a new one issued for the next
service only (`aud`), still naming the employee (`sub`) and, with RFC 8693, the agent that
asked (`act`). A token that leaks from the designer can call the agents gateway and
nothing else; the tools server can tell the Profile agent from the Travel agent and refuse
a pay tool to the latter.

AgentCore does the exchange for us. AgentCore Identity's OAuth credential provider has an
on-behalf-of mode, RFC 8693 `TOKEN_EXCHANGE` (or the JWT bearer grant that Microsoft's OBO
uses), and an AgentCore Gateway target can carry that credential provider, so the gateway
exchanges the inbound token before it calls the target; an agent can also ask for one with
`GetWorkloadAccessTokenForJWT` and `GetResourceOauth2Token` (`ON_BEHALF_OF_TOKEN_EXCHANGE`).
Sources: [AgentCore on-behalf-of token exchange](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/on-behalf-of-token-exchange.html),
[AWS blog: on-behalf-of token exchange with AgentCore Gateway](https://aws.amazon.com/blogs/machine-learning/implement-on-behalf-of-token-exchange-for-multi-tenant-agents-with-amazon-bedrock-agentcore-gateway/).

The identity provider must issue the exchanged tokens. Cognito has no token exchange
grant, which is why D20 kept OBO out of the MVP.

## The identity provider

D20 records that the Delta version runs RFC 8693 with an `act` claim on PingFederate. The
POC should use the same grant, so what it proves carries over.

| Option | Cost | RFC 8693 | Notes |
| --- | --- | --- | --- |
| Okta Integrator Free Plan | free | yes, with two custom authorization servers ("on-behalf-of token exchange") | API Access Management is included for testing; it is the identity provider in AWS's reference sample, so the AgentCore settings are known to work. Can federate Google for sign-in |
| Keycloak | free software; about 20 to 40 dollars a month to host (ECS Fargate and a small database) | yes, standard token exchange since 26.2 | Closest to "own the server" like PingFederate; we run and patch it |
| Microsoft Entra ID | free tenant | no; its OBO is the JWT bearer grant, which AgentCore supports as `MicrosoftOauth2` | Right if the pilot's identity provider is Entra; not the grant Delta uses |
| PingOne | trial only | yes | Closest product to PingFederate, but no free plan for a lasting POC |
| Auth0 | free plan | custom token exchange on paid plans | Not a fit |

Recommendation: **Okta Integrator Free Plan**. It costs nothing, speaks the same grant as
Delta's PingFederate, and matches AWS's own sample. Keycloak is the fallback if Sam wants
no third-party tenant.

## The token chain on `/p/hr/`

| Hop | Token | Audience | Who exchanges |
| --- | --- | --- | --- |
| Page to edge gateway and bridge | T0, from sign-in | `chat-platform` | none (sign-in) |
| Bridge to the designer (contact attribute), designer to agents gateway | T1 | `hr-agents`, scope `agents.invoke` | the bridge, with AgentCore Identity, before it starts the contact |
| Agents gateway to a sub-agent | T1 | `hr-agents` | none (passthrough; A1 permitting) |
| Sub-agent to tools gateway | T2 | `hr-tools`, scopes for that domain only (`profile.read`, `profile.write`, ...) | the sub-agent, with AgentCore Identity |
| Designer's own tool calls (policy search, ticket) | T1 | the tools gateway also accepts `hr-agents` for `docs___Retrieve` and `open_ticket` only | none (the designer cannot exchange) |

T1 lives as long as a chat (60 minutes) because the designer keeps it, but it opens one
gateway and only for invoking agents. T2 lives minutes. The tools server checks the scope
for each tool, so the Travel agent cannot propose a direct deposit change.

## What changes

1. **Identity provider tenant** (Sam): create the Okta Integrator Free Plan org; Claude
   cannot create accounts. Then an admin API token in 1Password, which Claude reads at
   deploy time like the Dynatrace token.
2. **Okta configuration as code**: the custom authorization servers (`chat-platform`,
   `hr-agents`, `hr-tools`), scopes, the token exchange policies, the platform's OIDC
   client and the two exchange clients, by a script against Okta's API.
3. **Sign-in**: chat.dengler.io signs in against Okta instead of Cognito, keeping the PKCE
   code the page already does. The invite gate becomes "assigned to the app" in Okta,
   which retires the pre sign-up Lambda. Google stays possible as an Okta identity
   provider. This touches guppi-gpt and every project, since they share one sign-in.
4. **Authorizers**: the edge gateway, the bridge runtime and both HR gateways point at
   Okta's discovery URLs with the audience above.
5. **Bridge**: exchange T0 for T1 before `StartChatContact`.
6. **Sub-agents and tools server**: exchange T1 for T2; check scopes per tool; drop
   `X-Hr-User-Token`, since the tools server can trust T2's `sub`.
7. **Checks**: tests per hop, a live run, a Dynatrace check that no token appears, and
   decision log and aws-feedback entries for what AgentCore does and does not do.

Roughly two to three days of work after the Okta org exists; each step deploys on its own
behind the current Cognito path until the switch in step 3.

## Questions for Sam

- Okta Integrator Free Plan, or Keycloak, or match a pilot that will run on Entra?
- Move all of chat.dengler.io to the new sign-in (simplest), or only `/p/hr/`?
