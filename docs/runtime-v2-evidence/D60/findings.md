# D60 test runtime: the Runtime's workload token in an A2A sub-agent

Run on 6 October 2026 by the session that implemented D60 commit A, to settle the doc's open
questions before the deploy ("Sub-agent token exchange on the Runtime workload token").

## Questions

1. Does AgentCore Runtime deliver `WorkloadAccessToken` to an A2A runtime behind a JWT
   authorizer, and does the SDK's A2A app put it in `call_context.state`?
2. Does Identity accept that token in `GetResourceOauth2Token` with
   `ON_BEHALF_OF_TOKEN_EXCHANGE`, called with the runtime's execution role?
3. Which IAM resource does that call check, and does the pattern grant
   `workload-identity/<runtime name>-*` cover it (CloudFormation lists only the whole
   `WorkloadIdentityDetails` object as a read-only attribute, so a nested `Fn::GetAtt` of
   its ARN is not documented)?

## Setup

- Runtime `hr_v2_obo_a2a` (id `hr_v2_obo_a2a-azQhJhHkL6`): V2, A2A, the study's probe image
  (`scripts/v2study/images/python`, `MODE=a2a`) with `bedrock-agentcore` 1.24.0 and the A2A
  app the HR sub-agents use; request header allowlist `Authorization`, as the sub-agents
  have; a `customJWTAuthorizer` on a Cognito user pool built for the test (client
  credentials).
- An Identity credential provider `hr-v2-obo-probe`, `CustomOauth2` on that pool's discovery
  URL, with the same `onBehalfOfTokenExchangeConfig` as the production providers
  (`TOKEN_EXCHANGE`, `actorTokenContent` `NONE`). Cognito does not implement token exchange,
  so its token endpoint answers 400: a 400 means Identity took the workload token and
  called the provider.
- The probe's handler reports whether the token is in the call state and in the SDK's
  context variable, its length, and Identity's answer to one exchange; never the token.
- The test role's grant on `GetResourceOauth2Token`: first the provider, token vault and
  directory only (negative control), then also `workload-identity/hr_v2_obo_a2a-*`.

## Results

| Run | Sessions | Token in the call state | Identity's answer |
| --- | --- | --- | --- |
| negative-grant | 2 new, 2 follow-ups | 4 of 4, 2,850 characters, also in the SDK context variable | `AccessDeniedException ... not authorized to perform: bedrock-agentcore:GetResourceOauth2Token on resource: ...workload-identity/hr_v2_obo_a2a-...` |
| runtime-grant | 3 new, 3 follow-ups | 6 of 6 | `ValidationException: OnBehalfOfTokenExchangeConfig is required in the OBO flow for OAuth2 credential provider type: CustomOauth2` (test provider not yet configured) |
| runtime-grant-obo-provider | 3 new, 3 follow-ups | 6 of 6 | `ValidationException: Token exchange failed with HTTP status 400`, the provider's refusal |

The exchange call took 190 to 300 ms on a new session and 130 to 140 ms on a follow-up,
including Cognito's 400. On the first two sessions after READY it took 5.0 and 5.3 s, the
slow window after READY (aws-feedback A31). Receipt to handler on a follow-up was 204 ms
(JWT authorizer) against 74 ms on SigV4 in the study, as A34 found.

## Answers

1. Yes. Every request carried the `WorkloadAccessToken` header past the allowlist, and the
   SDK's A2A app put it in `call_context.state["workload_access_token"]` and in
   `BedrockAgentCoreContext`, so `requires_access_token` would also find it.
2. Yes. With the grant in place Identity accepted the Runtime's token and called the
   provider's token endpoint, which is as far as a provider that refuses token exchange can
   go. That the subject Identity sends is the inbound bearer token is the documented flow
   and is not shown here; the production issuer checks it, and `scripts/d60.sh` runs the
   live checks after the deploy.
3. IAM checks the call against the runtime's own workload identity,
   `workload-identity/<runtime name>-<id>` (the full name is in `get-agent-runtime`'s
   `workloadIdentityDetails`). The pattern `<runtime name>-*` grants it; without it the call
   is refused. Commit A grants `hr_super_agent_<name>-*` on each sub-agent role.

Without question 3's grant, commit A would have failed closed on every sub-agent request
the moment the header arrived: the fallback covers a missing header, not a refused grant.

## Commands

```
scripts/v2study/setup.sh
docker build -t <repo>:py-obo scripts/v2study/images/python && docker push <repo>:py-obo
# Cognito pool with a client-credentials client; Identity provider hr-v2-obo-probe (CustomOauth2)
create.py create hr_v2_obo_a2a --image py-obo --protocol A2A --platform V2 --env MODE=a2a \
  --env OBO_PROBE_PROVIDER=hr-v2-obo-probe --headers Authorization \
  --jwt-discovery <pool discovery URL> --jwt-client <client id> --experiment D60
invoke.py --name hr_v2_obo_a2a --protocol a2a --jwt-file <token file> --new 2 --followups 1 --label negative-grant ...
# put the grant with workload-identity/hr_v2_obo_a2a-*; then the provider's onBehalfOfTokenExchangeConfig
invoke.py ... --label runtime-grant ...; invoke.py ... --label runtime-grant-obo-provider ...
collect.py docs/runtime-v2-evidence/D60/*.jsonl --md docs/runtime-v2-evidence/D60/results.md
# then: delete the runtime, the provider, the pool, the policy; setup.sh teardown
```
