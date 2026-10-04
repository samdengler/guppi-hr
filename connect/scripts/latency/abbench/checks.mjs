// Live checks of the new default path on /p/hr/ (stage 2's list in
// docs/proposals/connect-chatjs.md). One mode per run:
//
//   node checks.mjs conversation   five turns: CSP, SendEvent, reports; then New chat
//   node checks.mjs offline        30 s offline right after a question is sent
//   node checks.mjs hidden         hidden 5 minutes with the network up, then a question
//
// Results: results/check-<mode>.json.

import { writeFileSync, mkdirSync } from "node:fs";
import { chromium, freshSession, keepNewestToken, newArmContext, oktaOutputs, openPage, parseMs, readDebug, sleep } from "./common.mjs";

const MODE = process.argv[2];
const OUT = new URL("./results/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
const okta = oktaOutputs();
const session = await freshSession(okta);
const browser = await chromium.launch();
const context = await newArmContext(browser, okta);
const log = [];
const result = { mode: MODE, at: new Date().toISOString(), turns: [] };
const save = () => writeFileSync(`${OUT}check-${MODE}.json`, JSON.stringify(result, null, 2));

async function ask(page, text, { timeout = 60000 } = {}) {
  await page.evaluate(() => window.__armTurn());
  await page.locator("#composer-input").fill(text);
  await page.locator("#composer-input").press("Enter");
}

async function finishTurn(page, question, { timeout = 90000 } = {}) {
  await page.waitForFunction(() => window.__bench.doneAt !== null, null, { timeout, polling: 50 });
  await sleep(2000);
  const b = await page.evaluate(() => window.__bench);
  const debug = await readDebug(page);
  const ids = Object.fromEntries(debug.ids || []);
  const turn = {
    question,
    firstMs: b.firstAt !== null ? Math.round(b.firstAt - b.clickAt) : null,
    doneMs: Math.round(b.doneAt - b.clickAt),
    contact: ids.contact || null,
    transport: ids.transport || null,
    texts: debug.texts,
    summary: debug.summary,
    notes: debug.notes,
    steps: debug.steps,
  };
  result.turns.push(turn);
  save();
  console.log(`${question}: first ${turn.firstMs} ms, done ${turn.doneMs} ms, ${turn.transport}, ${turn.texts.length} text(s)`);
  return turn;
}

const summarizeNet = (net) => net.map(({ t, ...n }) => n);
const allTexts = (page) => page.evaluate(() => [...document.querySelectorAll(".reply-text")].map((t) => t.textContent));

try {
  if (MODE === "conversation") {
    const opened = await openPage(context, session, "/p/hr/?ff=debug", { log });
    const { page, net } = opened;
    await sleep(10000);
    const questions = [
      "How do buddy passes work?",
      "Can my parents use them?",
      "How much PTO do I earn per year?",
      "Does unused PTO carry over?",
      "What is my home address on file?",
    ];
    for (const q of questions) {
      await ask(page, q);
      await finishTurn(page, q);
    }
    await sleep(3000);
    const b = await page.evaluate(() => window.__bench);
    result.csp = b.csp;
    result.sendEvent = net.filter((n) => n.kind === "request" && n.path.includes("/participant/event")).length;
    result.sendMessage = net.filter((n) => n.kind === "request" && n.path.includes("/participant/message")).length;
    result.reports = net.filter((n) => n.path.endsWith("/chat/report") && n.kind !== "request").map((n) => n.status ?? n.failure);
    result.participantPaths = [...new Set(net.filter((n) => n.host.startsWith("participant")).map((n) => n.path))];
    result.sockets = opened.sockets.map(({ host, frames }) => ({ host, frames }));
    result.allTexts = await allTexts(page);
    // Check 5: New chat ends this contact and starts another.
    const oldContact = result.turns.at(-1).contact;
    result.restart = { oldContact, newChatAt: new Date().toISOString() };
    const startsBefore = net.filter((n) => n.path.endsWith("/chat/start") && n.kind === "response").length;
    await page.locator("#new-chat-btn").click();
    await page.waitForFunction(() => document.querySelectorAll(".reply").length === 0, null, { timeout: 10000 });
    await sleep(12000);
    result.restart.startResponses = net.filter((n) => n.path.endsWith("/chat/start") && n.kind === "response").length - startsBefore;
    result.net = summarizeNet(net);
    await keepNewestToken(page, session);
    await page.close();
  } else if (MODE === "offline") {
    const opened = await openPage(context, session, "/p/hr/?ff=debug", { log });
    const { page, net, sockets } = opened;
    await sleep(10000);
    const q = "How much PTO do I earn per year?";
    const sent = page.waitForResponse((r) => r.url().includes("/participant/message"), { timeout: 30000 });
    await ask(page, q);
    await sent;
    await context.setOffline(true);
    const offAt = Date.now();
    result.offlineAt = new Date(offAt).toISOString();
    const framesAtOff = sockets.map((s) => s.frames);
    const firstWhileOff = [];
    for (let i = 0; i < 30; i++) {
      await sleep(1000);
      const b = await page.evaluate(() => window.__bench);
      firstWhileOff.push({ s: i + 1, first: b.firstAt !== null, done: b.doneAt !== null });
    }
    const framesAtOn = sockets.map((s) => s.frames);
    await context.setOffline(false);
    result.onlineAt = new Date().toISOString();
    result.framesDuringOffline = framesAtOn.map((f, i) => f - (framesAtOff[i] || 0));
    result.socketsClosed = sockets.map((s) => (s.closedAt ? s.closedAt - offAt : null));
    result.whileOffline = firstWhileOff.filter((x, i) => i === 0 || x.first !== firstWhileOff[i - 1].first || x.done !== firstWhileOff[i - 1].done);
    await finishTurn(page, q, { timeout: 90000 }).catch((e) => (result.turnError = e.message.split("\n")[0]));
    // Time for a reconnect and catch-up to deliver anything late.
    await sleep(20000);
    result.allTexts = await allTexts(page);
    result.replyCount = await page.locator(".reply").count();
    result.statusLines = await page.evaluate(() => [...document.querySelectorAll(".reply-status")].filter((s) => !s.hidden).map((s) => s.textContent));
    result.lastDebug = await readDebug(page);
    result.net = summarizeNet(net);
    result.sockets = sockets.map(({ host, frames, closedAt }) => ({ host, frames, closedAfterOffMs: closedAt ? closedAt - offAt : null }));
    result.csp = (await page.evaluate(() => window.__bench)).csp;
    await keepNewestToken(page, session);
    await page.close();
  } else if (MODE === "hidden") {
    const opened = await openPage(context, session, "/p/hr/?ff=debug", { log });
    const { page, net, sockets } = opened;
    await sleep(10000);
    const startsBefore = net.length;
    await page.evaluate(() => window.__setVisibility("hidden"));
    result.hiddenAt = new Date().toISOString();
    result.visibilityWhileHidden = await page.evaluate(() => document.visibilityState);
    await sleep(5 * 60 * 1000);
    const netWhileHidden = net.slice(startsBefore);
    await page.evaluate(() => window.__setVisibility("visible"));
    result.visibleAt = new Date().toISOString();
    await sleep(3000);
    result.netWhileHidden = summarizeNet(netWhileHidden);
    result.netAfterVisible = summarizeNet(net.slice(startsBefore + netWhileHidden.length));
    const q = "How do buddy passes work?";
    await ask(page, q);
    await finishTurn(page, q);
    await sleep(5000);
    result.allTexts = await allTexts(page);
    result.replyCount = await page.locator(".reply").count();
    result.net = summarizeNet(net);
    result.sockets = sockets.map(({ host, frames, closedAt }) => ({ host, frames, closed: Boolean(closedAt) }));
    result.csp = (await page.evaluate(() => window.__bench)).csp;
    await keepNewestToken(page, session);
    await page.close();
  } else {
    throw new Error(`unknown mode ${MODE}`);
  }
} finally {
  result.log = log.filter((l) => !l.includes("dynatrace.com") && !l.includes("net::ERR_FAILED"));
  save();
  await context.close();
  await browser.close();
}
console.log(JSON.stringify({ ...result, turns: undefined, net: undefined }, null, 2));
