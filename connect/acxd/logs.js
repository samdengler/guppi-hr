'use strict';

/**
 * Print the designer's runtime log for one conversation (the Connect contact id).
 *
 *   node logs.js <contactId> [span]     # span in ms, defaults to one hour
 */

const { makeClient, sdk, mask } = require('./lib/client');

(async () => {
  const [conversationId, span = '3600000'] = process.argv.slice(2);
  if (!conversationId) throw new Error('usage: node logs.js <contactId> [span]');
  const client = makeClient();
  let items = [];
  for (let attempt = 0; attempt < 12 && !items.length; attempt++) {
    if (attempt) await new Promise((r) => setTimeout(r, 10000));
    items = await query(client, conversationId, span);
  }
  print(items);
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
    console.log(`${new Date(e.eventTime).toISOString().slice(11, 19)} ${e.eventType} ${mask(brief)}`);
  }
  if (!items.length) console.log('no log events after two minutes');
}
