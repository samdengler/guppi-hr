'use strict';

/**
 * Print the designer's runtime log for one conversation (the Connect contact id).
 *
 *   node logs.js <contactId> [span]          # span in ms, defaults to one hour
 *   node logs.js <contactId> [span] --json   # one JSON object per event, for a script
 *
 * With --json each line is {eventTime, eventType, flowId, correlationId, properties}, with
 * eventTime in ISO 8601 to the millisecond and properties the event's own properties; the
 * query runs once, so a conversation the designer no longer keeps prints nothing.
 * connect/scripts/turn_timeline.py reads this output.
 */

const { makeClient, sdk, mask } = require('./lib/client');

(async () => {
  const args = process.argv.slice(2);
  const json = args.includes('--json');
  const [conversationId, span = '3600000'] = args.filter((a) => a !== '--json');
  if (!conversationId) throw new Error('usage: node logs.js <contactId> [span] [--json]');
  const client = makeClient();
  let items = [];
  for (let attempt = 0; attempt < (json ? 1 : 12) && !items.length; attempt++) {
    if (attempt) await new Promise((r) => setTimeout(r, 10000));
    items = await query(client, conversationId, span);
  }
  if (json) printJson(items);
  else print(items);
})().catch((e) => {
  console.error(e.name, mask(e.message));
  process.exitCode = 1;
});

async function query(client, conversationId, span) {
  const items = [];
  let nextToken;
  do {
    const res = await client.send(
      new sdk.QueryLogsCommand({
        timeFilter: { relative: { span } },
        searchFilter: { conversationId },
        sortOrder: 'ASC',
        maxResults: 100,
        ...(nextToken ? { nextToken } : {}),
      }),
    );
    items.push(...(res.items ?? []));
    nextToken = res.nextToken;
  } while (nextToken);
  return items;
}

function print(items) {
  for (const e of items) {
    const props = Object.fromEntries((e.eventProperties ?? []).map((p) => [p.key, p.value]));
    const brief = JSON.stringify(props).slice(0, 400);
    console.log(`${new Date(e.eventTime).toISOString().slice(11, 23)} ${e.eventType} ${mask(brief)}`);
  }
  if (!items.length) console.log('no log events after two minutes');
}

function printJson(items) {
  for (const e of items) {
    const common = Object.fromEntries((e.commonProperties ?? []).map((p) => [p.key, p.value]));
    const line = {
      eventTime: new Date(e.eventTime).toISOString(),
      eventType: e.eventType,
      flowId: common.flowId ?? null,
      correlationId: common.correlationId ?? null,
      properties: Object.fromEntries((e.eventProperties ?? []).map((p) => [p.key, p.value])),
    };
    console.log(mask(JSON.stringify(line)));
  }
}
