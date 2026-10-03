# Demo: the four scenarios

A walk through the four conversations in [plan.md](plan.md), about five minutes. Open
`https://chat.dengler.io/p/hr-diy/`, sign in with Google, and start a **New chat** (the four
suggestions under the empty state are the scenarios' opening lines). Each signed-in
account gets its own synthetic employee record the first time it asks about one, so the
names and addresses below differ per account; every value is invented.

## Disambiguation

Type: `I need to update my information`

The reply is one question that names both candidate areas: "Is this about your personal
details, such as your home address or emergency contact, or about your pay, such as your
direct deposit account or pay statements?" No agent is asked; the reply label reads plain
"HR Assistant".

## Confirmation

Type: `Change my home address to 25 Ponce de Leon Ave, Atlanta GA 30308`

The status line shows "Asking the Profile agent..." and then "Profile agent answered", and
the label reads "HR Assistant · Profile". The reply states the exact change, from the
address on file to the new one, and asks for confirmation. Nothing is saved yet.

Type: `yes`

The reply confirms the update. Asking `What is my home address?` shows the new address.

## Sticky context

Type: `what about my emergency contact?`

The turn stays with the Profile agent without a new routing decision, and the reply says
which emergency contact is on file before offering to change it.

## Topic shift and escalation

Type: `How many buddy passes do I get?`

The label changes to "HR Assistant · Travel" and the answer comes from the pass travel
policy: 8 buddy passes a year, issued January 1, expiring December 31.

Type: `I need to talk to someone`

The Travel agent opens a ticket at once and gives its id, `HR-` and six digits, with the
two business day follow-up.

## Checking the results behind the page

With AWS credentials for the account:

```sh
# The run lines: domain, confidence, action, delegated_to, confirmed per turn
group=$(aws logs describe-log-groups --log-group-name-prefix /aws/bedrock-agentcore/runtimes/hr_super_agent- \
  --query 'logGroups[0].logGroupName' --output text)
aws logs filter-log-events --log-group-name "$group" --filter-pattern '"delegated_to"' \
  --start-time $(( ($(date +%s) - 900) * 1000 )) --query 'events[].message' --output text

# The audit entry of the confirmed change, with the same trace id as the confirming run
table=$(aws cloudformation describe-stack-resources --stack-name HrSuperAgent \
  --query "StackResources[?starts_with(LogicalResourceId,'HrToolsAudit')].PhysicalResourceId" --output text)
aws dynamodb scan --table-name "$table" --query 'Items[].{field:field.S,trace:trace_id.S}'
```

## Routing accuracy

```sh
uv run python evals/route.py
```

Prints accuracy per expected outcome over the 60 labeled utterances, the write-weighted
accuracy, a confusion table, and any misses (about 35 seconds of Bedrock calls).
