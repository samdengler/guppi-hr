# E10. Network mode: findings

## Hypothesis

From the plan: the documentation says VPC "may increase session startup times"; the attach of
an elastic network interface per microVM would add hundreds of ms to a restore.

## What was run

Runtime `hr_v2_net_vpc`: V2, HTTP, image `py`, `MODE=http`, idle 900 s, SigV4,
`networkMode` VPC in the account's default VPC `vpc-fa06609e` (172.31.0.0/16) with the public
subnets `subnet-2615f00c` (us-east-1a, `use1-az2`) and `subnet-843decf2` (us-east-1b,
`use1-az4`) and the security group `sg-0b6c011914cb60048` (`hr-v2-study`: no inbound rules,
all outbound). No NAT gateway; `requireServiceS3Endpoint` was not sent (the API reports it as
false). The probe makes no outbound call. Both AZ ids are on the list the documentation gives
for AgentCore VPC mode in us-east-1, and the service-linked role
`AWSServiceRoleForBedrockAgentCoreNetwork` exists.

The runtime never reached READY. Three creates, all on 5 October 2026 UTC:

| attempt | runtime id | created | CREATE_FAILED | time to failure | ENIs |
| --- | --- | --- | --- | --- | --- |
| 1 | `hr_v2_net_vpc-bCGl0k4ZbA` | 00:55:33 | 01:03:35 | 8 min 2 s | validation dry runs passed 00:56:07; two ENIs created 00:56:08 (`eni-05aa5604491d79150`, `eni-07fe026566016363a`, one per subnet); deleted 01:13:10, 9 minutes after the runtime was deleted |
| 2 | `hr_v2_net_vpc-YuOLSp95wN` | 01:04:09 | 01:06:43 | 2 min 34 s | only a `DescribeSubnets` by the network role at 01:04:10 in CloudTrail; no dry run and no ENI (attempt 1's ENIs still existed) |
| 3 | `hr_v2_net_vpc-0UJ9BB4VVB` | 01:15:57 | 01:23:18 | 7 min 21 s | started after attempt 1's ENIs were gone; dry runs passed 01:16:08; two ENIs created 01:16:10 (`eni-0532fce1e6f29db07`, `eni-09ae5823cd752e313`, interface type `agentic_ai`, in-use at 01:22); gone by 01:30 |

Every attempt ended with the same `failureReason`:

```
An internal error occurred while processing your request. Please try again.
```

The PUBLIC runtimes created from the same image in the same minutes reached READY in 185 to
186 s (`hr_v2_auth_jwt`, `hr_v2_idle_60`, baseline 184.9 s), so the image, the role and the
log delivery are not the cause.

## Results

No invocation was possible, so there is no latency result: no receipt to handler, no build
time. The planned 25 new sessions with 2 follow-ups were not sent.

## Conclusion

On this account, on 5 October 2026, a V2 runtime in VPC mode could not be created: three
attempts failed with an internal error after the ENIs were created and attached (or, on the
attempt that overlapped the previous ENIs, before any ENI). The question whether VPC mode slows
a V2 restore stays open, and VPC mode is not available to the HR runtimes on V2 until AWS
explains the failure.

## Surprises and notes for AWS

- The failure is opaque: `CREATE_FAILED` with "An internal error occurred while processing
  your request. Please try again.", after the network role's validation dry runs reported
  success and the ENIs were created. Retrying did not help (three attempts in 28 minutes).
- The failed runtime held its two ENIs until well after the failure; attempt 1's ENIs were
  deleted 9 minutes after the runtime itself was deleted.
- The second attempt failed in 2.6 minutes with no ENI activity while attempt 1's ENIs still
  existed, which looks like a different path to the same message.
- A V1 runtime with the same VPC settings would show whether the failure is specific to V2.
  That create was not run: the agent's permission check refused it, so it is left for Sam to
  decide.
- Worth sending to AWS with the three runtime ids and times above.

## Commands

```
PY=<scratchpad>/venv/bin/python
$PY scripts/v2study/create.py create hr_v2_net_vpc --image py --protocol HTTP --platform V2 --env MODE=http \
  --vpc subnet-2615f00c,subnet-843decf2 --sg sg-0b6c011914cb60048 --experiment E10
# after each failure:
$PY scripts/v2study/create.py delete hr_v2_net_vpc --wait
aws bedrock-agentcore-control get-agent-runtime --agent-runtime-id <id>
aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventSource,AttributeValue=ec2.amazonaws.com \
  --start-time 2026-10-05T00:55:00Z --end-time 2026-10-05T01:30:00Z
aws ec2 describe-network-interfaces --filters Name=group-id,Values=sg-0b6c011914cb60048
```

## Addendum by the main session, 01:45 to 02:05 UTC

- A fourth V2 attempt (`hr_v2_net_vpc_v2b-2CTvvl3e8W`, created 01:53:29) failed the same way
  at 02:01:39: `CREATE_FAILED`, "An internal error occurred while processing your request.
  Please try again." Four of four V2 creates in VPC mode failed over 66 minutes.
- A V1 runtime with the same VPC settings (`hr_v2_net_vpc_v1-bdQbduE2Bg`) was created at
  01:48:56 and READY after 258.6 s (a PUBLIC V1 runtime takes 6 s). It then answered no
  request: every new session failed with `RuntimeClientError ... Received error (502) from
  runtime` after about 65 s (7 of 7), and every follow-up on those sessions after about 4.2 s
  (the runtime's own records show 4.1 s receipt to completion with a null response). Its
  container log group holds no `runtime-logs-*` stream, so no container ever started.
- Inference: in VPC mode the microVM reaches ECR and the AgentCore control services only
  through the customer's VPC, and the default VPC used here has an internet gateway but no NAT
  gateway and no VPC endpoints, so the `agentic_ai` interfaces (no public address) cannot pull
  the image. On V1 that shows as a 65 s boot timeout and a 502 per session; on V2 the
  snapshot build fails and the platform reports it as an internal error. The documentation's
  `requireServiceS3Endpoint` hint and its VPC prerequisites (NAT or interface endpoints for
  ECR, S3, CloudWatch and the AgentCore services) point the same way. Not verified: the
  experiment did not add a NAT gateway or endpoints (cost, and out of the study's shape), so
  the latency question for VPC mode stays open and the finding for AWS is the opaque error.
- Both runtimes were deleted (02:04 UTC).
