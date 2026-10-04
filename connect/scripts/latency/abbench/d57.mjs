// D57 live checks on /p/hr/ after the chat start moved behind the REST API with no warm-ups.
//
//   node d57.mjs measure --per 6 --wait 10   "Change my address" and "Buddy passes", per each,
//                                             interleaved, each on a fresh page `wait` s after load
//   node d57.mjs update                       one press of "Update my information"
//   node d57.mjs bridge                       one press of "Update my information" on ?ff=connect-bridge
//
// First words are timed from the click to the first reply text in the DOM, as in L29.
// Results: results/d57-<mode>.json. Every contact seen is stopped at the end.

import { mkdirSync, writeFileSync } from "node:fs";
import { chromium, freshSession, keepNewestToken, newArmContext, oktaOutputs, openPage, parseMs, readDebug, sleep, stopContact } from "./common.mjs";

const MODE = process.argv[2];
const args = Object.fromEntries(
  process.argv.slice(3).reduce((acc, a, i, all) => (a.startsWith("--") ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
const PER = Number(args.per || 6);
const WAIT_S = Number(args.wait || 10);
const OUT = new URL("./results/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

const okta = oktaOutputs();
const session = await freshSession(okta);
const browser = await chromium.launch();
const context = await newArmContext(browser, okta);
const records = [];
const contacts = [];
const save = () => writeFileSync(`${OUT}d57-${MODE}.json`, JSON.stringify({ mode: MODE, per: PER, waitS: WAIT_S, records }, null, 2));

async function press(path, suggestion, index) {
  const log = [];
  const rec = { index, path, suggestion, startedAt: new Date().toISOString() };
  let opened;
  try {
    opened = await openPage(context, session, path, { log });
    const { page } = opened;
    rec.loadMs = opened.loadMs;
    await sleep(WAIT_S * 1000);
    rec.pressedAt = new Date().toISOString();
    await page.locator(".suggestion", { hasText: suggestion }).click();
    await page.waitForFunction(() => window.__bench.doneAt !== null, null, { timeout: 60000, polling: 50 });
    await sleep(1500);
    const b = await page.evaluate(() => window.__bench);
    rec.firstMs = b.firstAt !== null ? Math.round(b.firstAt - b.clickAt) : null;
    rec.doneMs = Math.round(b.doneAt - b.clickAt);
    rec.firstText = b.firstText;
    rec.csp = b.csp;
    const debug = await readDebug(page);
    rec.texts = debug.texts;
    rec.notes = debug.notes;
    const ids = Object.fromEntries(debug.ids || []);
    rec.contact = ids.contact || null;
    rec.transport = ids.transport || (opened.net.some((n) => n.path.endsWith("/invocations") && n.kind === "request") ? "bridge" : "unknown");
    const pageLines = Object.fromEntries(debug.page || []);
    rec.debugChatReadyMs = parseMs(pageLines["chat ready"]);
    rec.net = opened.net.map(({ t, ...n }) => `${n.kind} ${n.method || ""} ${n.host}${n.path} ${n.status ?? n.failure ?? ""}`);
    await keepNewestToken(page, session);
  } catch (error) {
    rec.error = error.message.split("\n")[0];
  } finally {
    rec.log = log.filter((l) => !l.includes("dynatrace.com") && !l.includes("Failed to load resource: net::ERR_FAILED"));
    if (opened) await opened.page.close().catch(() => {});
  }
  if (rec.contact) contacts.push(rec.contact);
  records.push(rec);
  save();
  const t = (ms) => (ms === null || ms === undefined ? "-" : (ms / 1000).toFixed(2));
  console.log(`${index} ${suggestion.padEnd(22)} first ${t(rec.firstMs)} done ${t(rec.doneMs)} ${rec.transport} ${rec.error || ""}`);
  return rec;
}

try {
  if (MODE === "measure") {
    const suggestions = ["Change my address", "Buddy passes"];
    for (let i = 0; i < PER * suggestions.length; i++) await press("/p/hr/?ff=debug", suggestions[i % suggestions.length], i);
  } else if (MODE === "update") {
    const rec = await press("/p/hr/?ff=debug", "Update my information", 0);
    console.log(JSON.stringify({ texts: rec.texts, net: rec.net, log: rec.log, csp: rec.csp }, null, 2));
  } else if (MODE === "bridge") {
    const rec = await press("/p/hr/?ff=debug,connect-bridge", "Update my information", 0);
    console.log(JSON.stringify({ texts: rec.texts, net: rec.net, log: rec.log }, null, 2));
  }
} finally {
  await context.close();
  await browser.close();
  save();
}
let stopped = 0;
for (const c of contacts) if (stopContact(c)) stopped += 1;
console.log(`stopped ${stopped} of ${contacts.length} contacts`);
