// The stage 1 A/B measurement on /p/hr/ (docs/proposals/connect-chatjs.md, step 5).
// Arm A: the default page (Connect chat transport). Arm B: ?ff=connect-bridge (the bridge).
// Both with ?ff=debug. Presses interleaved A, B, A, B; each press on a fresh page (a new
// chat), `wait` seconds after the chat screen is visible, cycling the four suggestions.
//
//   node bench.mjs --per 8 --wait 10 --label main     (64 presses)
//   node bench.mjs --per 2 --wait 1 --label quick     (16 presses)
//
// Results: results/<label>.json, one record per press.

import { mkdirSync, writeFileSync } from "node:fs";
import { chromium, freshSession, keepNewestToken, newArmContext, oktaOutputs, openPage, parseMs, readDebug, sleep, stopContact } from "./common.mjs";

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, all) => (a.startsWith("--") ? [...acc, [a.slice(2), all[i + 1]]] : acc), []),
);
const PER = Number(args.per || 8);
const WAIT_S = Number(args.wait || 10);
const LABEL = args.label || "run";
const SUGGESTIONS = ["Update my information", "Change my address", "PTO policy", "Buddy passes"];
const ARMS = { A: "/p/hr/?ff=debug", B: "/p/hr/?ff=debug,connect-bridge" };
const OUT = new URL("./results/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

const okta = oktaOutputs();
const session = await freshSession(okta);
const browser = await chromium.launch();
const contexts = { A: await newArmContext(browser, okta), B: await newArmContext(browser, okta) };
const records = [];
const contacts = [];
const save = () => writeFileSync(`${OUT}${LABEL}.json`, JSON.stringify({ label: LABEL, per: PER, waitS: WAIT_S, records }, null, 2));

async function press(arm, suggestion, index) {
  const log = [];
  const rec = { index, arm, suggestion, startedAt: new Date().toISOString() };
  let opened;
  try {
    opened = await openPage(contexts[arm], session, ARMS[arm], { log });
    const { page } = opened;
    rec.loadMs = opened.loadMs;
    await sleep(WAIT_S * 1000);
    rec.pressedAt = new Date().toISOString();
    await page.locator(".suggestion", { hasText: suggestion }).click();
    await page.waitForFunction(() => window.__bench.doneAt !== null, null, { timeout: 60000, polling: 50 });
    // A moment for the report to go out after RUN_FINISHED.
    await sleep(1500);
    const b = await page.evaluate(() => window.__bench);
    rec.firstMs = b.firstAt !== null ? Math.round(b.firstAt - b.clickAt) : null;
    rec.doneMs = Math.round(b.doneAt - b.clickAt);
    rec.firstText = b.firstText;
    rec.csp = b.csp;
    const debug = await readDebug(page);
    rec.debug = debug;
    const ids = Object.fromEntries(debug.ids || []);
    rec.contact = ids.contact || null;
    rec.transport = ids.transport || (opened.net.some((n) => n.path.endsWith("/invocations") && n.kind === "request") ? "bridge" : "unknown");
    const pageLines = Object.fromEntries(debug.page || []);
    rec.debugFirstMs = parseMs(pageLines["first text"]);
    rec.debugDoneMs = parseMs(pageLines["run finished"]);
    rec.debugChatReadyMs = parseMs(pageLines["chat ready"]);
    rec.replyCount = await page.locator(".reply").count();
    rec.net = opened.net.map(({ t, ...n }) => n);
    rec.sockets = opened.sockets.map(({ host, frames }) => ({ host, frames }));
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
  console.log(`${index} ${arm} ${suggestion.padEnd(22)} first ${t(rec.firstMs)} done ${t(rec.doneMs)} ${rec.transport} ${rec.error || ""}`);
}

try {
  const total = PER * SUGGESTIONS.length;
  for (let i = 0; i < total; i++) {
    const suggestion = SUGGESTIONS[i % SUGGESTIONS.length];
    await press("A", suggestion, i);
    await press("B", suggestion, i);
  }
} finally {
  await contexts.A.close();
  await contexts.B.close();
  await browser.close();
  save();
}
// Tidy up: end the test contacts the closed pages left open.
let stopped = 0;
for (const c of contacts) if (stopContact(c)) stopped += 1;
console.log(`stopped ${stopped} of ${contacts.length} contacts`);
