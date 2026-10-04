# On-behalf-of token exchange for `/p/hr/` (D20, D47, D48)

Status: built and deployed 3 October 2026; this is revision 4, the system as built after
the first critique of the build (D48). `scripts/obo-checks.py` checks every hop and Policy
rule against the deployed stacks; `scripts/obo-rollback.sh` reverts the change.

History, briefly:
- Revision 1 chose Okta for the exchange, which its free plan cannot do (X8).
- An independent critique of revision 1
  ([OBO Exchange Design Critique](https://claude.ai/artifact/FP3jciuzGA4PVVyoPWXwJK))
  and two spikes on a throwaway issuer shaped revisions 2 and 3.
- Sam's decisions on revision 3 are D47.
- A critique of the build led to D48.

Okta stays the sign-in provider (D46). A small issuer of our own on API Gateway, Lambda and
KMS does the exchange, in guppi-gpt's platform stack. It stands in for the production
identity provider (PingFederate at Delta). Sam approved it as a Lambda in the request path.

## The AgentCore pieces and their jobs

| Piece | Job |
| --- | --- |
| Identity | Every exchange, through on-behalf-of credential providers that read the client secrets: the bridge's, each sub-agent's, the `/p/hr-diy/` orchestrator's, and the tools gateway's |
| Gateway | Checks every inbound hop token (issuer, audience, client, scope); the agents gateway passes the sub-agent's token through; the tools gateway's target exchanges for the runtime |
| Policy | Decides each tool call on the tools gateway from the caller token's scopes, and filters `tools/list` to the tools that token may call |
| Runtime | Hosts the bridge, the sub-agents and the tools server; each runtime's authorizer checks the token it receives |

## What hop tokens buy, and what they do not

Before D47 one Okta token (audience `api://guppi`) travelled every hop, and every gateway
and runtime checked the same issuer and audience. A token taken from any hop opened every
hop for the rest of its hour.

With hop tokens:

- **Each hop opens only the next.** A token taken from one hop works only at the next, and
  only for the scopes that hop needs.
- **Each agents token drives one sub-agent.** The bridge gets one per sub-agent; the
  Travel agents token cannot drive the Pay agent.
- **The canvas's tools token is read-only.** It reads the profile and pay statements, and
  cannot see bank details or change anything.
- **Each sub-agent's tools token covers only its own domain.** The issuer will not mint
  anything wider. Gateway Policy and then the tools server refuse any tool outside its
  scopes.
- **The Okta token stops early.** It goes no further than the bridge and the `/p/hr-diy/`
  orchestrator. It still travels from the page through the edge gateway.
- **Every change is audited with the clients that acted** (the `act` chain).

What stays, on the threat list:

- **A stolen agents token can do what its sub-agent can do.** A thief holding the Pay
  agents token can talk the Pay agent into proposing and committing a direct deposit
  change, as the employee could, until the token expires. Rate limits per employee and the
  one-hour life bound it.
- **The Connect participant token** the bridge stores in DynamoDB drives the same
  designer, with the agents tokens attached, for the life of the chat.
- **The Okta harness client is accepted** alongside the chat app. Its refresh token, on
  Sam's laptop for the test harness, can mint hop tokens for Sam, the only member of
  `chat-users`.

## The token chain

| Token | Holder | Exchanged from, by | Audience | Scope |
| --- | --- | --- | --- | --- |
| Okta | page, bridge, `/p/hr-diy/` orchestrator | sign-in | `api://guppi` | `openid email profile offline_access` |
| Agents, one per sub-agent | the canvas (`hrProfileToken`, `hrPayToken`, `hrTravelToken`), the bridge's warm calls, the orchestrator | Okta, by the bridge's client | `api://hr-agents/<name>` | `hr.agents.<name>` |
| Canvas tools | the canvas (`hrToolsToken`) | Okta, by the bridge's client | `api://hr-tools` | `hr.tools.policy hr.tools.profile.read hr.tools.pay.statements.read` |
| Sub-agent tools | each sub-agent | its agents token, by its own client | `api://hr-tools` | its domain's scopes (below) |
| Runtime | the tools gateway, per tool call | a tools token, by the gateway's client | `api://hr-tools-runtime` | the scopes of the tools token |

The `/p/hr-diy/` orchestrator's general agent gets a tools token with `hr.tools.policy`
alone.

Scopes per tool. Gateway Policy enforces them on the caller's token, and the tools server
checks the same table again on the runtime token (`hr_agent/tools/scopes.py`):

| Scope | Tools |
| --- | --- |
| `hr.tools.policy` | `open_ticket`, and at the gateway the knowledge base's `docs___Retrieve` |
| `hr.tools.profile.read` | `get_profile` |
| `hr.tools.profile.write` | `propose_address_change`, `propose_emergency_contact_change`, `commit_change` of a profile proposal |
| `hr.tools.pay.statements.read` | `list_pay_statements` |
| `hr.tools.pay.read` | `get_direct_deposit` |
| `hr.tools.pay.write` | `propose_direct_deposit_change`, `commit_change` of a pay proposal |

`docs___AgenticRetrieveStream` has no rule, so it is refused: no caller uses it, and it
runs managed models at a cost per call.

Sub-agent tools scopes:

| Sub-agent | Scope |
| --- | --- |
| Profile | `hr.tools.policy hr.tools.profile.read hr.tools.profile.write` |
| Pay | `hr.tools.policy hr.tools.pay.statements.read hr.tools.pay.read hr.tools.pay.write` |
| Travel | `hr.tools.policy` |

The bridge blanks all four token attributes right after the greeting (D42). The designer
keeps the values it read at start (C2).

## Where the exchanges happen

| Exchange | When | Cache |
| --- | --- | --- |
| Okta to three agents tokens and the canvas tools token, four calls in parallel | the bridge, at the warm start, before `StartChatContact` | none: one set per contact |
| Agents token to tools token | each sub-agent, at its warm call or its first call | in the process, by the subject token, until a minute before expiry |
| Okta to an agents token per sub-agent, and to a policy tools token | the `/p/hr-diy/` orchestrator, when it first needs each | the same |
| Tools token to runtime token | the tools gateway's target, on every tool call | none: the gateway does not reuse tokens (A14) |

The agents gateway passes the agents token through, because runtime targets cannot
exchange (A13). The tools gateway's MCP target exchanges for the runtime (OAuth
`TOKEN_EXCHANGE`), which retired `X-Hr-User-Token` and the gateway's SigV4 call (D19).
That costs about 430 ms per tool call (A14), which Sam accepted for the Delta-shaped path
D20 describes. The fallback, SigV4 with the caller's token forwarded in a header, stays
available if the cost proves too high. The tools target carries its tool list inline
(`mcpToolSchema`), so the gateway never asks for a token without an employee in it.

## The issuer

One Lambda function (`guppi-gpt-obo-issuer`, 1024 MB, reserved concurrency 10) behind a
regional REST API. Routes: `GET /.well-known/openid-configuration`,
`GET /jwks.json`, `POST /token` (RFC 8693 only). An RSA 2048 KMS key signs; the private key
never leaves KMS.

### Clients and what each may exchange

| Client | Used by | Subject token it may present | May receive |
| --- | --- | --- | --- |
| `hr-bridge` | the bridge, the `/p/hr-diy/` orchestrator | Okta: audience `api://guppi`, `cid` the chat app or the harness, `uid` present | one sub-agent's agents token at a time, or the canvas tools scopes |
| `hr-agent-<name>` | that sub-agent | this issuer's: audience `api://hr-agents/<name>` only, client `hr-bridge`, `act` one deep | its domain's tools scopes |
| `hr-tools-gateway` | the tools gateway's target | this issuer's: audience `api://hr-tools`, client `hr-bridge` or an agent client, `act` one or two deep | a runtime token carrying the subject's scopes, whatever it requests |

As a result:
- a Travel runtime cannot mint a pay token or become the Pay agent;
- a canvas token cannot become an agents token;
- a runtime token cannot be exchanged again;
- no chain is more than three exchanges from Okta.

### Tokens it mints

- Claims: `iss` (a configured URL), `sub` (Okta `uid`), `aud`, `scope`, `client_id`,
  `act` (nested per hop), `iat`, `nbf`, `exp`, `jti`. Header `typ` `at+jwt`.
- `exp` is the subject token's expiry or one hour, whichever comes first.
- A subject with less than a minute left is refused, so no token is minted already expired.

### Verification

- **The standard library, with no dependencies to bundle.** guppi-gpt's stack synthesizes
  without Docker, and `cryptography` has native code.
- **The signature check:** RS256 only, no `crit`. It re-encodes PKCS#1 v1.5 and compares
  in constant time, with the RFC 8017 length and range checks and a 2048-bit minimum.
- **The claim checks:** `kid`, `iss`, `aud`, `exp`, `nbf` and `iat`, with 60 seconds of
  leeway, plus `typ` `at+jwt` on its own tokens.
- **Okta's keys** are cached for an hour, survive an Okta outage, and an unknown `kid`
  refetches at most once a minute.
- **Errors are generic** (`invalid_client`, `invalid_grant`, `invalid_scope`), never a
  500.
- **31 unit tests** cover the rules and verification.

### Exposure and cost controls

- **The token endpoint is public by nature, with no web ACL in front.** This is an accepted
  risk for the POC (Sam, 3 October 2026). Anyone who sends more than the token throttle,
  100 requests a second, makes the issuer refuse every exchange until they stop, and
  every caller then fails closed; HR tool calls stop. A regional web ACL with a per-IP
  rate rule would close it for about 6 dollars a month. A REST API can take one later
  with no other change.
- **Throttles:** `/token` at 100 a second with a burst of 200. Key and discovery reads have
  their own limit, 50 a second with a burst of 100, so a flood of token requests never
  starves authorizers' key fetches. Those reads may be cached for five minutes.
- **Access logs** go to `/aws/apigateway/guppi-obo-issuer`. Alarms watch the function's
  errors and throttles and the API's 4xx and 5xx counts.
- **The issuer logs** client, status, audience, scope, the new token's `jti` and the
  subject's `jti`. It never logs the employee or a token. A chain of exchanges can be
  followed back to the Okta token, whose `jti` Okta's system log holds.

### Keys and secrets

- **The key policy** gives the account administration but neither `kms:Sign` nor
  `kms:CreateGrant`, so an IAM policy alone cannot mint a token.
- **Administrators can still sign.** One who rewrites the key policy (`kms:PutKeyPolicy`
  stays, or the key would be unmanageable) or the function's code could mint tokens. The
  account has no CloudTrail trail to alarm on either; that is accepted for the POC.
- **Each client's secret** is generated in Secrets Manager as `guppi/obo/<client>`. The
  issuer reads it at cold start.
- **Identity reads the secret as the caller** of `GetResourceOauth2Token` (A16). So each
  caller's role may read its own client's secret, by name (`guppi/obo/<client>-*`), so a
  replaced secret keeps its grant.
- **What else each role may call:** `GetResourceOauth2Token` on its own provider only, and
  `GetWorkloadAccessTokenForJWT` for its own workload identity only (never `ForUserId`).
- **Nothing is rotated for the POC.**

## Checks at every hop

| Checkpoint | Issuer | Audience | `allowedClients` | `allowedScopes` |
| --- | --- | --- | --- | --- |
| Edge gateway, bridge runtime, `/p/hr-diy/` runtime | Okta | `api://guppi` | (A11) | none |
| Agents gateway | exchange service | the three agents audiences | `hr-bridge` | the three agents scopes |
| Each sub-agent runtime | exchange service | its own agents audience | `hr-bridge` | its own agents scope |
| Tools gateway | exchange service | `api://hr-tools` | `hr-bridge`, the three agent clients | `hr.tools.policy` |
| Tools runtime | exchange service | `api://hr-tools-runtime` | `hr-tools-gateway` | none; Policy decided, and the server checks |

Gateway Policy holds one Cedar rule per scope. Every claim reaches Cedar as a string and
Cedar cannot concatenate (A15), so the scope is matched as a whole word, alone, first,
last or inside:

```
permit(
  principal is AgentCore::OAuthUser,
  action in [AgentCore::Action::"hr___list_pay_statements"],
  resource == AgentCore::Gateway::"<tools gateway ARN>"
)
when { principal.hasTag("scope") && (principal.getTag("scope") like "hr.tools.pay.statements.read"
  || principal.getTag("scope") like "hr.tools.pay.statements.read *"
  || principal.getTag("scope") like "* hr.tools.pay.statements.read"
  || principal.getTag("scope") like "* hr.tools.pay.statements.read *") };
```

The tools server verifies the runtime token again and checks each tool's scope on it. So a
Policy engine in LOG_ONLY, a detached engine, or a runtime token minted outside the
gateway still meets the same table. `commit_change` also needs the write scope of the
proposal's field, which Policy cannot see. The audit records the `act` chain.

Tests hold the tables together:
- the server's table equals Policy's;
- every tool the server lists has a rule;
- the whole-word match is checked against prefixes and look-alikes;
- the HR side's scopes and audiences equal the issuer's rules in guppi-gpt.

## When something fails

Every caller fails closed with a plain line, and none falls back to the Okta token:

- **The bridge cannot exchange.** It starts no contact; the page shows "HR could not
  confirm the sign-in. Try again in a minute." Checked live with the issuer at concurrency
  0.
- **The orchestrator cannot exchange.** `/p/hr-diy/` shows the same line.
- **A sub-agent cannot exchange.** It answers that it could not complete the request.
- **The exchanger has no provider configured.** It refuses rather than pass the Okta token
  on. Only `OBO=off`, set by hand for a local run or the tests, returns the token unchanged.
- **The tools server gets no valid token or scope.** It refuses the call.

## Token lifetime and the one-hour contact

The hop tokens expire with the Okta token, and a contact lasts up to 60 minutes. The page
refreshes the Okta token before it sends a warm start unless the token has 50 minutes
left, so the token, the hop tokens and the contact start together. The bridge's rule
stays as the fallback: a contact whose tokens are within 5 minutes of expiry is replaced
when a fresher token arrives (D42).

## Latency

| Call | Time |
| --- | --- |
| Direct exchange, warm, from a laptop | median 126 ms, of which the Lambda took 16 ms |
| Identity, `GetWorkloadAccessTokenForJWT` plus `GetResourceOauth2Token`, from a laptop | about 270 ms |
| The tools gateway's exchange, per tool call, against a copy of the tools runtime | about 430 ms |
| Warm start on `/p/hr/`, before and after D47 (3 rounds each) | 7.5 s and 8.6 s |
| First reply in a new chat on `/p/hr/`, before and after | 4.7 s and 3.7 s, within the noise of three rounds |

The latency log has the details (L23).

## Cost

| Item | Monthly |
| --- | --- |
| KMS key | 1.00 dollar |
| Secrets Manager, five client secrets | 2.00 dollars |
| Lambda, REST API, access logs | under 0.50 dollars |
| Policy, $0.000025 per authorization | about 3 cents per thousand tool calls |
| Identity | no charge through Runtime and Gateway; $0.01 per thousand tokens otherwise |

About 3.50 dollars a month. A web ACL in front of the issuer would add about 6; Sam
accepted the risk instead.

## Rollback

`scripts/obo-rollback.sh --diff` shows what a rollback would change. Without the flag, it
reverts the code of the D47 and D48 commits on top of HEAD in a temporary worktree, leaving
the documents and the decision history as they are, and deploys: the HR
stack, the bridge, the canvas and the contact flow. Its known risks are listed in the
script. `infra/tests/test_rollback.py` runs its revert step (`--check`) on every test run. Rehearsed with `--diff` on 4 October, after the third critique of the build:
- the HR stack drops the policy engine, its seven rules and its workload identities, and
  reverts the gateways, runtimes, targets and role policies;
- the Connect stack drops the bridge's workload identity and reverts its runtime and role.

Nothing was deployed.

## Options compared

| Option | Outcome |
| --- | --- |
| Okta token exchange, or two Okta servers trusting each other | Not on the free plan (X8) |
| Keycloak on Fargate with a database | 20 to 40 dollars a month, and a server to patch |
| Cognito with AWS's token-exchange sample | An API Gateway and six Lambda functions around a provider without the grant |
| Gateway-side exchange on the agents gateway | Not possible: HTTP targets fall back to client credentials (A13) |
| Gateway-side exchange on the tools gateway | Built; about 430 ms per tool call until the gateway reuses tokens (A14) |
| IAM actor tokens instead of client secrets | Needs outbound web identity federation turned on for the account; not decided |
| The issuer on an HTTP API | Same cost, but no per-method throttles and no web ACL if one is ever needed (D48) |
| A web ACL with a per-IP rate rule in front of the issuer | About 6 dollars a month; Sam accepted the risk for the POC |

## Spike results that shaped the design

| Check | Result |
| --- | --- |
| Gateway authorizer, `scope` or `scp` alone | both read; `allowedScopes` is any-of (A12) |
| Gateway and runtime `allowedClients`, `allowedScopes` | enforced on both (A12) |
| Gateway-side exchange on HTTP targets | client credentials only, no employee (A13) |
| Gateway-side exchange on an MCP server target | a real exchange, but one per call and a new MCP session each time (A14) |
| `JWT_PASSTHROUGH` on an MCP server target | refused by the API (A14) |
| Gateway Policy on `scope` | each token listed and called only its tools; no added time (A15) |
| Identity with `EXTERNAL` secrets | reads the secret as the caller (A16) |

## Decisions

D47 (Sam, 3 October 2026):
1. The issuer is approved as a Lambda in the request path.
2. The tools gateway exchanges on every call; the tools runtime verifies its own token.
3. A client per domain with secrets, plus one for the tools gateway.
4. The issuer lives in the guppi-gpt platform stack.
5. One switch with a scripted rollback. It happened as a single cut-over: no LOG_ONLY
   phase and no `OBO` setting, which made the window shorter.

D48 (proposed, after the critique of the build):
- agents tokens per sub-agent;
- the pay-statements scope;
- the tools server's own per-tool check;
- fail-closed exchangers;
- the REST API, with the missing web ACL as an accepted risk;
- the issuer's other hardening.
