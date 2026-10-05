No requests: `hr_v2_net_vpc` never reached READY. Create attempts on 5 October 2026 (UTC),
from `get-agent-runtime` and CloudTrail:

| attempt | runtime id | createdAt | lastUpdatedAt (CREATE_FAILED) | failureReason |
| --- | --- | --- | --- | --- |
| 1 | hr_v2_net_vpc-bCGl0k4ZbA | 00:55:33.836 | 01:03:35.608 | An internal error occurred while processing your request. Please try again. |
| 2 | hr_v2_net_vpc-YuOLSp95wN | 01:04:09.383 | 01:06:43.255 | An internal error occurred while processing your request. Please try again. |
| 3 | hr_v2_net_vpc-0UJ9BB4VVB | 01:15:57.179 | 01:23:18.516 | An internal error occurred while processing your request. Please try again. |

Configuration returned for every attempt: platformVersion V2, serverProtocol HTTP, image
`hr-v2-study:py`, networkMode VPC, subnets subnet-2615f00c and subnet-843decf2, securityGroups
sg-0b6c011914cb60048, requireServiceS3Endpoint false, idleRuntimeSessionTimeout 900,
maxLifetime 28800, metadataConfiguration requireMMDSV2 true.

ENI events (CloudTrail, ec2.amazonaws.com, by AWSServiceRoleForBedrockAgentCoreNetwork):

| time | event | session | subnet or ENI | result |
| --- | --- | --- | --- | --- |
| 00:55:45 | DescribeSubnets | CustomerSlrValidation | | ok |
| 00:56:07 | CreateNetworkInterface (dry run) x2 | request-validation-session | subnet-2615f00c, subnet-843decf2 | DryRunOperation (would have succeeded) |
| 00:56:08 | CreateNetworkInterface x2 | 265801606522 | eni-05aa5604491d79150, eni-07fe026566016363a | ok |
| 01:04:10 | DescribeSubnets | CustomerSlrValidation | | ok |
| 01:13:10 | DeleteNetworkInterface x2 | 265801606522 | eni-05aa5604491d79150, eni-07fe026566016363a | ok |
| 01:15:58 | DescribeSubnets | CustomerSlrValidation | | ok |
| 01:16:08 | CreateNetworkInterface (dry run) x2 | request-validation-session | subnet-2615f00c, subnet-843decf2 | DryRunOperation (would have succeeded) |
| 01:16:10 | CreateNetworkInterface x2 | 265801606522 | eni-0532fce1e6f29db07, eni-09ae5823cd752e313 | ok (interface type agentic_ai, in-use at 01:22) |
