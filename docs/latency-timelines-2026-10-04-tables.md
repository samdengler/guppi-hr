# Step tables for the latency timelines of 4 October 2026

Per-path step tables behind `latency-timelines-2026-10-04.md`: median start and end in ms from the click (from navigation for the chat start), with spreads and counts.


### clarify (5 turns)

First words median 1134 ms (p10 987, p90 1307, range 975 to 1326); done median 1133 ms.

| Step | Owner | Start | End | Duration median | p10 to p90 | n |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Browser to Connect: SendMessage until Connect stamps the message | connect | 0 | 156 | 156 | 142 to 166 | 5 |
| SendMessage request as the browser sees it (overlaps) | connect | 18 | 214 | 194 | 188 to 207 | 5 |
| Connect hands the message to the designer | connect | 156 | 359 | 199 | 187 to 273 | 5 |
| Designer before the routing model | designer | 359 | 371 | 12 | 11 to 13 | 5 |
| Routing model (designer, Bedrock) | model | 371 | 796 | 446 | 366 to 651 | 5 |
| Designer to its response (NluResponded) | designer | 796 | 888 | 18 | 17 to 90 | 5 |
| Connect posts the reply to the transcript | connect | 888 | 1002 | 113 | 106 to 129 | 5 |
| Connect pushes the reply to the browser, the page shows it | connect | 1002 | 1134 | 93 | 85 to 118 | 5 |

### policy-first (5 turns)

First words median 3446 ms (p10 3184, p90 3731, range 3144 to 3797); done median 4245 ms.

| Step | Owner | Start | End | Duration median | p10 to p90 | n |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Browser to Connect: SendMessage until Connect stamps the message | connect | 0 | 162 | 162 | 154 to 179 | 5 |
| SendMessage request as the browser sees it (overlaps) | connect | 17 | 221 | 204 | 191 to 229 | 5 |
| Connect hands the message to the designer | connect | 162 | 419 | 262 | 221 to 294 | 5 |
| Designer before the routing model | designer | 419 | 446 | 12 | 11 to 38 | 5 |
| Routing model (designer, Bedrock) | model | 446 | 898 | 424 | 409 to 526 | 5 |
| Designer flow to the data request | designer | 898 | 951 | 19 | 16 to 100 | 5 |
| Data request PolicySearch (designer's view) | designer | 951 | 1678 | 727 | 658 to 771 | 5 |
| &nbsp;&nbsp;Designer to the tools gateway | designer | 951 | 1033 | 83 | 67 to 99 | 5 |
| &nbsp;&nbsp;Tools gateway: authorizer, Cedar Policy, routing | gateway | 1033 | 1129 | 105 | 98 to 109 | 5 |
| &nbsp;&nbsp;Tools gateway: knowledge base Retrieve (Bedrock Knowledge Bases) | gateway | 1129 | 1608 | 490 | 391 to 503 | 5 |
| &nbsp;&nbsp;Tools gateway to the designer | designer | 1608 | 1678 | 66 | 61 to 89 | 5 |
| Designer to the generative journey | designer | 1678 | 1682 | 4 | 3 to 23 | 5 |
| Generative journey agent (Haiku 4.5, in the designer) | model | 1682 | 3221 | 1493 | 1272 to 1743 | 5 |
| Designer to its response (NluResponded) | designer | 3221 | 3243 | 25 | 21 to 29 | 5 |
| Connect posts the reply to the transcript | connect | 3243 | 3352 | 109 | 106 to 166 | 5 |
| Connect pushes the reply to the browser, the page shows it | connect | 3352 | 3446 | 99 | 93 to 148 | 5 |
| Page waits for quiet to end the turn (no end mark) | ours | 3446 | 4245 | 799 | 788 to 801 | 5 |

### policy-follow (5 turns)

First words median 1724 ms (p10 1572, p90 2098, range 1565 to 2205); done median 2523 ms.

| Step | Owner | Start | End | Duration median | p10 to p90 | n |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Browser to Connect: SendMessage until Connect stamps the message | connect | 0 | 104 | 104 | 95 to 125 | 5 |
| SendMessage request as the browser sees it (overlaps) | connect | 6 | 164 | 158 | 149 to 187 | 5 |
| Connect hands the message to the designer | connect | 104 | 374 | 275 | 200 to 326 | 5 |
| Designer to the generative journey | designer | 374 | 382 | 10 | 9 to 14 | 5 |
| Generative journey agent (Haiku 4.5, in the designer) | model | 382 | 1454 | 985 | 926 to 1498 | 5 |
| Designer to its response (NluResponded) | designer | 1454 | 1474 | 19 | 17 to 29 | 5 |
| Connect posts the reply to the transcript | connect | 1474 | 1618 | 118 | 103 to 145 | 5 |
| Connect pushes the reply to the browser, the page shows it | connect | 1618 | 1724 | 107 | 89 to 171 | 5 |
| Page waits for quiet to end the turn (no end mark) | ours | 1724 | 2523 | 791 | 790 to 799 | 5 |

### profile-first (17 turns)

First words median 6193 ms (p10 5621, p90 7140, range 5486 to 7200); done median 6192 ms.

| Step | Owner | Start | End | Duration median | p10 to p90 | n |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Browser to Connect: SendMessage until Connect stamps the message | connect | 0 | 154 | 154 | 107 to 184 | 17 |
| SendMessage request as the browser sees it (overlaps) | connect | 17 | 217 | 200 | 164 to 263 | 17 |
| Connect hands the message to the designer | connect | 154 | 414 | 285 | 210 to 345 | 17 |
| Designer before the routing model | designer | 414 | 425 | 12 | 11 to 39 | 17 |
| Routing model (designer, Bedrock) | model | 425 | 905 | 455 | 403 to 591 | 17 |
| Designer flow to the data request | designer | 905 | 951 | 16 | 15 to 65 | 17 |
| Data request DelegateProfile (designer's view) | designer | 951 | 5959 | 5047 | 4521 to 5757 | 17 |
| &nbsp;&nbsp;Designer to the agents gateway | designer | 951 | 1038 | 95 | 82 to 114 | 17 |
| &nbsp;&nbsp;Agents gateway: authorizer and target | gateway | 1038 | 1044 | 6 | 5 to 14 | 17 |
| &nbsp;&nbsp;Runtime: session and delivery to the sub-agent | runtime | 1044 | 1991 | 933 | 586 to 1310 | 17 |
| &nbsp;&nbsp;Sub-agent profile (POST / on the runtime) | ours | 1991 | 5840 | 3834 | 3619 to 4340 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: A2A request handling before the first call | ours | 1991 | 2142 | 154 | 142 to 178 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;Instance credentials from IMDS (read 1) | runtime | 2142 | 2147 | 3 | 3 to 4 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: our code before: workload access token | ours | 2147 | 2228 | 58 | 55 to 75 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;workload access token (Identity) | identity | 2228 | 2283 | 59 | 55 to 67 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;on-behalf-of exchange for the tools token (Identity, issuer) | identity | 2283 | 2437 | 157 | 139 to 172 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: MCP client start (session thread, connection) | ours | 2437 | 2749 | 310 | 279 to 388 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP initialize (tools gateway) | gateway | 2749 | 2859 | 98 | 78 to 115 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP notifications/initialized (tools gateway) | gateway | 2862 | 2957 | 80 | 46 to 93 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP tools/list (tools gateway) | gateway | 2959 | 3147 | 188 | 165 to 203 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP tools/call hr___get_profile through the tools gateway | gateway | 3150 | 5040 | 1865 | 1690 to 2243 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Sub-agent to the tools gateway (hr___get_profile) | gateway | 3150 | 3261 | 75 | 38 to 107 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: authorizer, Cedar Policy, routing (hr___get_profile) | gateway | 3261 | 3378 | 100 | 88 to 121 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Identity and the issuer: on-behalf-of exchange for the runtime token (hr___get_profile) | identity | 3378 | 3544 | 152 | 145 to 170 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Runtime: delivery of MCP initialize to the tools runtime (hr___get_profile) | runtime | 3544 | 4162 | 708 | 593 to 1036 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: initialize and initialized round trips to the target (hr___get_profile) | runtime | 4162 | 4842 | 611 | 562 to 662 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools runtime: the tool call (JWT check, DynamoDB) (hr___get_profile) | ours | 4842 | 5012 | 168 | 157 to 209 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway and the sub-agent: the answer back (hr___get_profile) | gateway | 5012 | 5040 | 30 | 28 to 37 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;Instance credentials from IMDS (read 2) | runtime | 5053 | 5056 | 3 | 2 to 3 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: agent build (Strands Agent, Bedrock client) | ours | 5056 | 5128 | 57 | 52 to 71 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: time to first token (Haiku 4.5) | model | 5128 | 5667 | 539 | 500 to 583 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: generation | model | 5667 | 5835 | 224 | 195 to 300 | 17 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: after the model to the A2A answer | ours | 5835 | 5840 | 4 | 3 to 5 | 17 |
| &nbsp;&nbsp;Runtime and agents gateway return the answer | runtime | 5840 | 5861 | 19 | 17 to 23 | 17 |
| &nbsp;&nbsp;Agents gateway to the designer | designer | 5861 | 5959 | 84 | 56 to 103 | 17 |
| Designer to its response (NluResponded) | designer | 5959 | 5986 | 17 | 13 to 51 | 17 |
| Connect posts the reply to the transcript | connect | 5986 | 6099 | 118 | 111 to 171 | 17 |
| Connect pushes the reply to the browser, the page shows it | connect | 6099 | 6193 | 94 | 84 to 135 | 17 |

### profile-follow (6 turns)

First words median 2748 ms (p10 2505, p90 3377, range 2437 to 3653); done median 2748 ms.

| Step | Owner | Start | End | Duration median | p10 to p90 | n |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Browser to Connect: SendMessage until Connect stamps the message | connect | 0 | 105 | 105 | 97 to 162 | 6 |
| SendMessage request as the browser sees it (overlaps) | connect | 6 | 190 | 184 | 154 to 244 | 6 |
| Connect hands the message to the designer | connect | 105 | 410 | 270 | 182 to 374 | 6 |
| Designer before the routing model | designer | 410 | 423 | 12 | 12 to 14 | 6 |
| Routing model (designer, Bedrock) | model | 423 | 889 | 442 | 396 to 587 | 6 |
| Designer flow to the data request | designer | 889 | 904 | 16 | 15 to 16 | 6 |
| Data request DelegateProfile (designer's view) | designer | 904 | 2441 | 1480 | 1448 to 2194 | 6 |
| &nbsp;&nbsp;Designer to the agents gateway | designer | 904 | 1014 | 99 | 91 to 110 | 6 |
| &nbsp;&nbsp;Agents gateway: authorizer and target | gateway | 1014 | 1028 | 9 | 6 to 13 | 6 |
| &nbsp;&nbsp;Runtime: session and delivery to the sub-agent | runtime | 1028 | 1320 | 289 | 265 to 300 | 6 |
| &nbsp;&nbsp;Sub-agent profile (POST / on the runtime) | ours | 1320 | 2361 | 998 | 926 to 1702 | 6 |
| &nbsp;&nbsp;&nbsp;&nbsp;Instance credentials from IMDS (read 1) | runtime | 1331 | 1334 | 2 | 2 to 3 | 6 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: agent build (Strands Agent, Bedrock client) | ours | 1334 | 1390 | 49 | 48 to 63 | 6 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: time to first token (Haiku 4.5) | model | 1390 | 1978 | 588 | 554 to 630 | 6 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: generation | model | 1978 | 2355 | 333 | 266 to 1042 | 6 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: after the model to the A2A answer | ours | 2355 | 2361 | 3 | 3 to 6 | 6 |
| &nbsp;&nbsp;Runtime and agents gateway return the answer | runtime | 2361 | 2381 | 20 | 18 to 33 | 6 |
| &nbsp;&nbsp;Agents gateway to the designer | designer | 2381 | 2441 | 71 | 59 to 113 | 6 |
| Designer to its response (NluResponded) | designer | 2441 | 2485 | 31 | 18 to 64 | 6 |
| Connect posts the reply to the transcript | connect | 2485 | 2636 | 124 | 102 to 186 | 6 |
| Connect pushes the reply to the browser, the page shows it | connect | 2636 | 2748 | 93 | 78 to 112 | 6 |

### travel-first (5 turns)

First words median 6880 ms (p10 5922, p90 6986, range 5606 to 7032); done median 6878 ms.

| Step | Owner | Start | End | Duration median | p10 to p90 | n |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Browser to Connect: SendMessage until Connect stamps the message | connect | 0 | 158 | 158 | 154 to 173 | 5 |
| SendMessage request as the browser sees it (overlaps) | connect | 18 | 217 | 200 | 198 to 223 | 5 |
| Connect hands the message to the designer | connect | 158 | 418 | 258 | 201 to 279 | 5 |
| Designer before the routing model | designer | 418 | 426 | 11 | 8 to 13 | 5 |
| Routing model (designer, Bedrock) | model | 426 | 813 | 389 | 373 to 422 | 5 |
| Designer flow to the data request | designer | 813 | 855 | 16 | 14 to 124 | 5 |
| Data request DelegateTravel (designer's view) | designer | 855 | 6593 | 5767 | 4793 to 5865 | 5 |
| &nbsp;&nbsp;Designer to the agents gateway | designer | 855 | 964 | 95 | 86 to 109 | 5 |
| &nbsp;&nbsp;Agents gateway: authorizer and target | gateway | 964 | 972 | 8 | 6 to 12 | 5 |
| &nbsp;&nbsp;Runtime: session and delivery to the sub-agent | runtime | 972 | 2163 | 1236 | 834 to 1248 | 5 |
| &nbsp;&nbsp;Sub-agent travel (POST / on the runtime) | ours | 2163 | 6509 | 4346 | 3563 to 4663 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: A2A request handling before the first call | ours | 2163 | 2345 | 173 | 145 to 182 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Instance credentials from IMDS (read 1) | runtime | 2345 | 2348 | 3 | 3 to 3 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: our code before: workload access token | ours | 2348 | 2423 | 72 | 62 to 74 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;workload access token (Identity) | identity | 2423 | 2494 | 67 | 61 to 70 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;on-behalf-of exchange for the tools token (Identity, issuer) | identity | 2494 | 2666 | 171 | 148 to 180 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: MCP client start (session thread, connection) | ours | 2666 | 3055 | 379 | 277 to 386 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP initialize (tools gateway) | gateway | 3055 | 3157 | 100 | 78 to 102 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP notifications/initialized (tools gateway) | gateway | 3161 | 3251 | 79 | 39 to 87 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP tools/list (tools gateway) | gateway | 3252 | 3438 | 182 | 164 to 202 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP tools/call docs___Retrieve through the tools gateway | gateway | 3442 | 4095 | 689 | 652 to 725 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Sub-agent to the tools gateway (docs___Retrieve) | gateway | 3442 | 3518 | 77 | 61 to 82 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: authorizer, Cedar Policy, routing (docs___Retrieve) | gateway | 3518 | 3608 | 94 | 90 to 112 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: target call (knowledge base) (docs___Retrieve) | gateway | 3608 | 4092 | 506 | 484 to 541 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway and the sub-agent: the answer back (docs___Retrieve) | gateway | 4092 | 4095 | 3 | 3 to 5 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Instance credentials from IMDS (read 2) | runtime | 4108 | 4110 | 3 | 2 to 3 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: agent build (Strands Agent, Bedrock client) | ours | 4110 | 4180 | 68 | 53 to 71 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: time to first token (Haiku 4.5) | model | 4180 | 4774 | 538 | 513 to 578 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: generation | model | 4774 | 6505 | 1729 | 1225 to 2191 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: after the model to the A2A answer | ours | 6505 | 6509 | 4 | 4 to 5 | 5 |
| &nbsp;&nbsp;Runtime and agents gateway return the answer | runtime | 6509 | 6527 | 18 | 17 to 19 | 5 |
| &nbsp;&nbsp;Agents gateway to the designer | designer | 6527 | 6593 | 87 | 67 to 100 | 5 |
| Designer to its response (NluResponded) | designer | 6593 | 6647 | 27 | 17 to 46 | 5 |
| Connect posts the reply to the transcript | connect | 6647 | 6769 | 122 | 111 to 126 | 5 |
| Connect pushes the reply to the browser, the page shows it | connect | 6769 | 6880 | 103 | 82 to 117 | 5 |

### travel-follow (5 turns)

First words median 4130 ms (p10 3715, p90 4402, range 3468 to 4515); done median 4130 ms.

| Step | Owner | Start | End | Duration median | p10 to p90 | n |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Browser to Connect: SendMessage until Connect stamps the message | connect | 0 | 111 | 111 | 104 to 130 | 5 |
| SendMessage request as the browser sees it (overlaps) | connect | 7 | 165 | 158 | 153 to 207 | 5 |
| Connect hands the message to the designer | connect | 111 | 339 | 219 | 193 to 238 | 5 |
| Designer before the routing model | designer | 339 | 360 | 13 | 12 to 31 | 5 |
| Routing model (designer, Bedrock) | model | 360 | 761 | 442 | 364 to 608 | 5 |
| Designer flow to the data request | designer | 761 | 773 | 12 | 11 to 14 | 5 |
| Data request DelegateTravel (designer's view) | designer | 773 | 3894 | 3144 | 2718 to 3266 | 5 |
| &nbsp;&nbsp;Designer to the agents gateway | designer | 773 | 873 | 91 | 90 to 120 | 5 |
| &nbsp;&nbsp;Agents gateway: authorizer and target | gateway | 873 | 880 | 6 | 5 to 6 | 5 |
| &nbsp;&nbsp;Runtime: session and delivery to the sub-agent | runtime | 880 | 1154 | 271 | 261 to 274 | 5 |
| &nbsp;&nbsp;Sub-agent travel (POST / on the runtime) | ours | 1154 | 3799 | 2658 | 2232 to 2795 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP tools/call docs___Retrieve through the tools gateway | gateway | 1157 | 1866 | 705 | 678 to 761 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Sub-agent to the tools gateway (docs___Retrieve) | gateway | 1157 | 1237 | 80 | 75 to 87 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: authorizer, Cedar Policy, routing (docs___Retrieve) | gateway | 1237 | 1355 | 103 | 100 to 114 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: target call (knowledge base) (docs___Retrieve) | gateway | 1355 | 1863 | 517 | 500 to 558 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway and the sub-agent: the answer back (docs___Retrieve) | gateway | 1863 | 1866 | 3 | 3 to 3 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Instance credentials from IMDS (read 1) | runtime | 1880 | 1882 | 3 | 2 to 3 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: agent build (Strands Agent, Bedrock client) | ours | 1882 | 1945 | 61 | 47 to 63 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: time to first token (Haiku 4.5) | model | 1945 | 2546 | 594 | 565 to 627 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: generation | model | 2546 | 3796 | 1227 | 859 to 1444 | 5 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: after the model to the A2A answer | ours | 3796 | 3799 | 4 | 3 to 4 | 5 |
| &nbsp;&nbsp;Runtime and agents gateway return the answer | runtime | 3799 | 3817 | 18 | 18 to 21 | 5 |
| &nbsp;&nbsp;Agents gateway to the designer | designer | 3817 | 3894 | 98 | 55 to 118 | 5 |
| Designer to its response (NluResponded) | designer | 3894 | 3923 | 18 | 15 to 25 | 5 |
| Connect posts the reply to the transcript | connect | 3923 | 4023 | 105 | 98 to 110 | 5 |
| Connect pushes the reply to the browser, the page shows it | connect | 4023 | 4130 | 80 | 78 to 106 | 5 |

### pay-first (2 turns)

First words median 8617 ms (p10 8063, p90 9171, range 7924 to 9310); done median 8617 ms.

| Step | Owner | Start | End | Duration median | p10 to p90 | n |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Browser to Connect: SendMessage until Connect stamps the message | connect | 0 | 153 | 153 | 145 to 160 | 2 |
| SendMessage request as the browser sees it (overlaps) | connect | 14 | 219 | 205 | 190 to 220 | 2 |
| Connect hands the message to the designer | connect | 153 | 384 | 232 | 198 to 266 | 2 |
| Designer before the routing model | designer | 384 | 401 | 16 | 14 to 19 | 2 |
| Routing model (designer, Bedrock) | model | 401 | 905 | 504 | 493 to 515 | 2 |
| Designer flow to the data request | designer | 905 | 948 | 43 | 21 to 65 | 2 |
| Data request DelegatePay (designer's view) | designer | 948 | 8371 | 7423 | 6832 to 8014 | 2 |
| &nbsp;&nbsp;Designer to the agents gateway | designer | 948 | 1041 | 93 | 81 to 106 | 2 |
| &nbsp;&nbsp;Agents gateway: authorizer and target | gateway | 1041 | 1048 | 6 | 6 to 7 | 2 |
| &nbsp;&nbsp;Runtime: session and delivery to the sub-agent | runtime | 1048 | 1906 | 858 | 774 to 943 | 2 |
| &nbsp;&nbsp;Sub-agent pay (POST / on the runtime) | ours | 1906 | 8256 | 6350 | 5892 to 6807 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: A2A request handling before the first call | ours | 1906 | 2073 | 167 | 149 to 185 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Instance credentials from IMDS (read 1) | runtime | 2073 | 2076 | 3 | 3 to 4 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: our code before: workload access token | ours | 2076 | 2144 | 68 | 59 to 77 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;workload access token (Identity) | identity | 2144 | 2209 | 65 | 57 to 73 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;on-behalf-of exchange for the tools token (Identity, issuer) | identity | 2210 | 2361 | 151 | 149 to 154 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: MCP client start (session thread, connection) | ours | 2361 | 2697 | 336 | 287 to 386 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP initialize (tools gateway) | gateway | 2697 | 2796 | 99 | 96 to 101 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP notifications/initialized (tools gateway) | gateway | 2800 | 2882 | 82 | 78 to 86 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP tools/list (tools gateway) | gateway | 2884 | 3093 | 209 | 206 to 212 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP tools/call hr___get_direct_deposit through the tools gateway | gateway | 3096 | 5000 | 1904 | 1889 to 1919 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Sub-agent to the tools gateway (hr___get_direct_deposit) | gateway | 3096 | 3151 | 56 | 49 to 62 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: authorizer, Cedar Policy, routing (hr___get_direct_deposit) | gateway | 3151 | 3248 | 96 | 92 to 101 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Identity and the issuer: on-behalf-of exchange for the runtime token (hr___get_direct_deposit) | identity | 3248 | 3412 | 164 | 157 to 171 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Runtime: delivery of MCP initialize to the tools runtime (hr___get_direct_deposit) | runtime | 3412 | 4187 | 775 | 766 to 784 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: initialize and initialized round trips to the target (hr___get_direct_deposit) | runtime | 4187 | 4788 | 602 | 577 to 626 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools runtime: the tool call (JWT check, DynamoDB) (hr___get_direct_deposit) | ours | 4788 | 4968 | 179 | 164 to 195 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway and the sub-agent: the answer back (hr___get_direct_deposit) | gateway | 4968 | 5000 | 32 | 31 to 34 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;MCP tools/call hr___list_pay_statements through the tools gateway | gateway | 5003 | 6999 | 1996 | 1734 to 2259 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Sub-agent to the tools gateway (hr___list_pay_statements) | gateway | 5003 | 5060 | 58 | 29 to 87 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: authorizer, Cedar Policy, routing (hr___list_pay_statements) | gateway | 5060 | 5161 | 100 | 99 to 101 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Identity and the issuer: on-behalf-of exchange for the runtime token (hr___list_pay_statements) | identity | 5161 | 5316 | 155 | 153 to 156 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Runtime: delivery of MCP initialize to the tools runtime (hr___list_pay_statements) | runtime | 5316 | 6227 | 912 | 628 to 1196 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway: initialize and initialized round trips to the target (hr___list_pay_statements) | runtime | 6227 | 6786 | 559 | 558 to 560 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools runtime: the tool call (JWT check, DynamoDB) (hr___list_pay_statements) | ours | 6786 | 6969 | 183 | 175 to 191 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Tools gateway and the sub-agent: the answer back (hr___list_pay_statements) | gateway | 6969 | 6999 | 30 | 29 to 30 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Instance credentials from IMDS (read 2) | runtime | 7011 | 7014 | 3 | 2 to 3 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: agent build (Strands Agent, Bedrock client) | ours | 7014 | 7083 | 69 | 65 to 72 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: time to first token (Haiku 4.5) | model | 7083 | 7644 | 562 | 557 to 566 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: generation | model | 7644 | 8252 | 608 | 471 to 744 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: after the model to the A2A answer | ours | 8252 | 8256 | 4 | 3 to 4 | 2 |
| &nbsp;&nbsp;Runtime and agents gateway return the answer | runtime | 8256 | 8272 | 17 | 16 to 18 | 2 |
| &nbsp;&nbsp;Agents gateway to the designer | designer | 8272 | 8371 | 98 | 64 to 133 | 2 |
| Designer to its response (NluResponded) | designer | 8371 | 8406 | 36 | 31 to 40 | 2 |
| Connect posts the reply to the transcript | connect | 8406 | 8532 | 126 | 116 to 136 | 2 |
| Connect pushes the reply to the browser, the page shows it | connect | 8532 | 8617 | 85 | 79 to 91 | 2 |

### pay-follow (2 turns)

First words median 2466 ms (p10 2343, p90 2590, range 2312 to 2621); done median 2466 ms.

| Step | Owner | Start | End | Duration median | p10 to p90 | n |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| Browser to Connect: SendMessage until Connect stamps the message | connect | 0 | 112 | 112 | 93 to 130 | 2 |
| SendMessage request as the browser sees it (overlaps) | connect | 6 | 192 | 186 | 147 to 225 | 2 |
| Connect hands the message to the designer | connect | 112 | 370 | 258 | 234 to 283 | 2 |
| Designer before the routing model | designer | 370 | 382 | 12 | 11 to 13 | 2 |
| Routing model (designer, Bedrock) | model | 382 | 856 | 474 | 399 to 548 | 2 |
| Designer flow to the data request | designer | 856 | 870 | 14 | 12 to 16 | 2 |
| Data request DelegatePay (designer's view) | designer | 870 | 2216 | 1346 | 1331 to 1361 | 2 |
| &nbsp;&nbsp;Designer to the agents gateway | designer | 870 | 968 | 98 | 97 to 99 | 2 |
| &nbsp;&nbsp;Agents gateway: authorizer and target | gateway | 968 | 973 | 5 | 5 to 5 | 2 |
| &nbsp;&nbsp;Runtime: session and delivery to the sub-agent | runtime | 973 | 1252 | 279 | 277 to 282 | 2 |
| &nbsp;&nbsp;Sub-agent pay (POST / on the runtime) | ours | 1252 | 2098 | 846 | 842 to 851 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Instance credentials from IMDS (read 1) | runtime | 1264 | 1266 | 3 | 2 to 3 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: agent build (Strands Agent, Bedrock client) | ours | 1266 | 1321 | 55 | 48 to 61 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: time to first token (Haiku 4.5) | model | 1321 | 1886 | 565 | 559 to 571 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Model: generation | model | 1886 | 2095 | 209 | 207 to 210 | 2 |
| &nbsp;&nbsp;&nbsp;&nbsp;Sub-agent: after the model to the A2A answer | ours | 2095 | 2098 | 4 | 4 to 4 | 2 |
| &nbsp;&nbsp;Runtime and agents gateway return the answer | runtime | 2098 | 2125 | 26 | 20 to 33 | 2 |
| &nbsp;&nbsp;Agents gateway to the designer | designer | 2125 | 2216 | 91 | 76 to 106 | 2 |
| Designer to its response (NluResponded) | designer | 2216 | 2233 | 17 | 15 to 19 | 2 |
| Connect posts the reply to the transcript | connect | 2233 | 2355 | 122 | 110 to 134 | 2 |
| Connect pushes the reply to the browser, the page shows it | connect | 2355 | 2466 | 112 | 89 to 135 | 2 |

### chat start (28 page loads on a warm function instance)

| Step | Owner | Start | End | Duration median | p10 to p90 | min to max | n |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: |
| Page HTML (navigation) | internet | 0 | 96 | 96 | 88 to 129 | 85 to 211 | 28 |
| Page scripts to DOMContentLoaded | ours | 96 | 236 | 139 | 129 to 157 | 123 to 163 | 28 |
| config.json through CloudFront | internet | 235 | 332 | 96 | 91 to 124 | 88 to 167 | 28 |
| Okta refresh token grant | identity | 344 | 780 | 438 | 402 to 479 | 394 to 598 | 28 |
| POST /api/hr/chat/start (browser's view) | ours | 787 | 3092 | 2305 | 2075 to 2515 | 1953 to 2790 | 28 |
| &nbsp;&nbsp;Browser to the function: CloudFront, API Gateway, Lambda invoke | internet | 788 | 829 | 49 | 30 to 74 | 28 to 98 | 28 |
| &nbsp;&nbsp;Hop token exchanges (workload token, then 4 at once) | identity | 829 | 1063 | 218 | 191 to 246 | 183 to 279 | 28 |
| &nbsp;&nbsp;&nbsp;&nbsp;Identity before the issuer (workload access token, Identity's own work) | identity | 829 | 974 | 142 | 123 to 174 | 108 to 188 | 28 |
| &nbsp;&nbsp;Okta token check in the function (RS256, built-in keys) | ours | 829 | 829 | 0 | 0 to 0 | 0 to 1 | 28 |
| &nbsp;&nbsp;&nbsp;&nbsp;Issuer exchange for hr-agents/profile (Lambda handler) | identity | 983 | 1003 | 22 | 19 to 24 | 8 to 29 | 28 |
| &nbsp;&nbsp;&nbsp;&nbsp;Issuer exchange for hr-agents/travel (Lambda handler) | identity | 984 | 1007 | 23 | 17 to 26 | 8 to 27 | 28 |
| &nbsp;&nbsp;&nbsp;&nbsp;Issuer exchange for hr-agents/pay (Lambda handler) | identity | 986 | 1009 | 22 | 8 to 24 | 8 to 28 | 28 |
| &nbsp;&nbsp;&nbsp;&nbsp;Issuer exchange for hr-tools (Lambda handler) | identity | 988 | 1003 | 22 | 9 to 26 | 7 to 27 | 28 |
| &nbsp;&nbsp;&nbsp;&nbsp;Identity after the issuer (API Gateway return, Identity to the function) | identity | 1011 | 1063 | 33 | 19 to 48 | 16 to 75 | 28 |
| &nbsp;&nbsp;StartChatContact (function to Connect) | connect | 1063 | 1518 | 484 | 401 to 564 | 357 to 585 | 28 |
| &nbsp;&nbsp;CreateParticipantConnection (function to Connect) | connect | 1518 | 1752 | 216 | 193 to 254 | 187 to 307 | 28 |
| &nbsp;&nbsp;Flow WebSocket open and subscribe (function) | connect | 1752 | 1841 | 92 | 60 to 111 | 55 to 234 | 28 |
| &nbsp;&nbsp;Greeting wait (function) | connect | 1841 | 2918 | 1090 | 925 to 1204 | 870 to 1477 | 28 |
| &nbsp;&nbsp;&nbsp;&nbsp;Connect runs the contact flow to the Agentic CX block | connect | 1841 | 2482 | 641 | 509 to 727 | 477 to 771 | 28 |
| &nbsp;&nbsp;&nbsp;&nbsp;Designer greets (WelcomeFlow) | designer | 2482 | 2504 | 18 | 16 to 36 | 14 to 128 | 28 |
| &nbsp;&nbsp;&nbsp;&nbsp;Connect delivers the greeting to the function's WebSocket | connect | 2504 | 2918 | 406 | 369 to 456 | 346 to 823 | 28 |
| &nbsp;&nbsp;Token attribute blanking (UpdateContactAttributes) | connect | 2918 | 3068 | 146 | 112 to 179 | 92 to 237 | 28 |
| &nbsp;&nbsp;Function answers; API Gateway and CloudFront to the browser | internet | 3069 | 3092 | 22 | 21 to 31 | 20 to 51 | 28 |
| chatjs CreateParticipantConnection (browser) | connect | 3105 | 3303 | 174 | 155 to 230 | 151 to 332 | 28 |
| chatjs WebSocket open | connect | 3308 | 3437 | 137 | 126 to 164 | 122 to 197 | 28 |
| chatjs GetTranscript (browser) | connect | 3310 | 3481 | 169 | 159 to 186 | 154 to 208 | 28 |
| WebSocket first frame (subscribe acknowledgement) | connect | 3437 | 3476 | 38 | 35 to 41 | 34 to 47 | 28 |