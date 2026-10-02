# Phase 8 report

Run unattended on 2 October 2026 from a Claude Code session on `main`, following
`docs/phase-8.md`. Sam approved running it straight through, including the in-place update
of `HrSuperAgent` in step 6.

The precondition held: `../guppi-gpt/docs/proposals/platform-phase-5a-report.md` records
`kit-v0.2.0` (commit 763fe42, tag on github.com/samdengler/guppi-gpt) and the extension
members `TOOL_CALL_START` and `TOOL_CALL_END` renderers, `ctx.setLabel`, `guppi.onThread`
and `state` from `onSend`, with no blockers.

## What landed

| Step | Commit | Change |
| --- | --- | --- |
| 1 | `fe05cde` | The orchestrator on the kit: `app = create_app(build_strands_agent)`; `keepalive.py`, `validation.py`, `conversation_log.py` deleted after a diff against `kit-v0.2.0` showed them identical apart from the package name; the image installs git and reads a GitHub token as a BuildKit secret (D29, D30) |
| 2 | `3e0d51b` | The stack on the platform contract: `/guppi/platform/*` from SSM, the platform-owned sections removed, every JWT authorizer and the HR tools issuer on the platform pool, the target `hr` on the platform edge gateway and the `InvokeAgentRuntime` policy on its role (D31); stack tests rewritten (174 Python tests green), `cdk synth -c image_uri=...` green |
| 3 | `06be59d` | `web/src` page and its tests deleted; `web/manifest.json` (no `theme`), `web/src/ext.js` as an ES module, `copy.js` cut to its pure helpers; 14 `node:test` cases (D32, D33) |
| 4 | `5eafcc3` | `scripts/deploy.sh`: no Google OAuth read, Dynatrace from 1Password with fallback, `--reuse-parameters` and `--site-only` kept, `HR_GITHUB_TOKEN` from `gh auth token`, manifest and extension to `projects/hr/` with `no-cache`, `/projects/hr/*` invalidated |
| 5 | `a5123eb` | README, AGENTS.md, design.md, plan.md (phase 8), demo.md, agent/README.md; D34 records the move and marks D9, D10 and D17 Reversed |
| 6 | this commit | `scripts/deploy.sh --reuse-parameters --require-approval never`: `deploy exit=0` (`.deploy/deploy-20261002-073017.log`, 1433 s of `cdk deploy`) |

## Resources removed

From `cdk diff HrSuperAgent` (saved to `.deploy/phase8-diff.txt`), taken before the deploy.
No resource is replaced; the agents and tools gateways are updated in place (authorizer
only), so `AgentsGatewayUrl` and `ToolsGatewayUrl`, which guppi-connect reads, keep their
values.

| Area | Resources deleted |
| --- | --- |
| Sign-in | `UserPool`, its `Web` client, the `Google` identity provider, the `auth-hr.dengler.io` user pool domain, `Branding` |
| DNS and certificates | `AuthRecord` (auth-hr.dengler.io), `ChatARecord` and `ChatAAAARecord` (hr.dengler.io), `ChatCertificate`, `AuthCertificate` |
| Edge gateway | `EdgeGateway` (hr-super-agent-edge), its `RuntimeTarget` (`api`), `GatewayRole`, `GatewayInvokePolicy`, `EdgeGatewayPerUserRateLimit` |
| WAF | `EdgeWebAcl`, `EdgeWebAclAssociation`, `OriginVerifySecret`, the `WafBlocks`, `WafFailCloses` and `WafFailOpens` alarms |
| Page | `Distribution`, its origin access control, `SecurityHeadersPolicy`, the site bucket's policy |
| Feedback | `FeedbackApi` with its deployment, `prod` stage, resources, method, validator, model, two gateway responses and Cognito authorizer; `FeedbackApiRole`; `FeedbackBus` and `FeedbackArchive`; the Dynatrace business events connection, API destination, its role and policy, rule, dead letter queue and queue policy, and `FeedbackDeadLetterAlarm` |
| Edge observability | `EdgeGateway5xxAlarm`, `EdgeGateway4xxRateAlarm`, the edge gateway's vended log group, delivery source, destination and delivery, and its Dynatrace subscription filter |
| Template | Parameters `GoogleClientId`, `GoogleClientSecret`, `DynatraceBeaconOrigin`; condition `HasDynatraceBeaconOrigin`; the CloudFront hosted zone mapping; outputs `SiteBucketName`, `DistributionId`, `UserPoolId`, `UserPoolClientId`, `AuthDomain`, `GatewayUrl`, `GatewayArn`, `FeedbackApiUrl`, `FeedbackApiEndpoint`, `FeedbackBusName`, `RumScriptPath`, `RumBeaconOrigin` |

Orphaned, not deleted: the site bucket `hrsuperagent-sitebucket397a1860-ahfzxmjr1rik`
(`SiteBucket`, `RemovalPolicy.RETAIN`). It leaves the stack and stays in the account for
Sam to delete.

Added: `PlatformTarget` (target `hr` on the platform edge gateway, JWT passthrough) and
`PlatformGatewayInvokePolicy` (`InvokeAgentRuntime` on the orchestrator for the platform
gateway role), plus five SSM-typed parameters for `/guppi/platform/*`. Updated in place:
the orchestrator, sub-agent and HR tools runtimes (new image; authorizers or token
settings on the platform pool), the agents and tools gateways (authorizer), the
investigator role's policy (`ListUsers` on the platform pool). Outputs: `SiteUrl` is
`https://chat.dengler.io/p/hr/`, `AgentPath` is new.

## Deploy

`HrSuperAgent` reached `UPDATE_COMPLETE` with no failed resource. The image built under
CDK with the `github_token` build secret and was pushed; the four runtimes took it. The
cleanup phase deleted every resource listed above; the one `DELETE_SKIPPED` event is
`SiteBucket397A1860`, the retained site bucket, which still exists. The platform edge
gateway lists two targets, `api` and `hr`, both `READY`. `hr.dengler.io` and
`auth-hr.dengler.io` no longer resolve. `AgentsGatewayUrl` and `ToolsGatewayUrl` in
`cdk-outputs.json` are unchanged:
`https://hr-super-agent-agents-rfkdgz7314.gateway.bedrock-agentcore.us-east-1.amazonaws.com`
and `https://hr-super-agent-tools-7bi54dgr6g.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp`.
Both now accept only the platform pool's token, which is what guppi-connect's plan expects.
