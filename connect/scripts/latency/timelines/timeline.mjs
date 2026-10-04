// Latency timeline runs on /p/hr/ (4 Oct 2026, after D57). Each chat on a fresh page, the
// first turn `wait` s after the chat shows, then one follow-up in the same chat. Records the
// browser's own clock for every turn (click, SendMessage, first item, done) as epoch ms, the
// page load's resource timings (Okta refresh, chat start, participant connection) and the
// WebSockets' open and first frame times. No token is printed or written.
//
//   node timeline.mjs main      5 chats per suggestion, interleaved, plus 2 pay chats
//   node timeline.mjs reuse     3 pairs: "Change my address", 60 s, again in a new chat
//   node timeline.mjs smoke     one chat of "Change my address" with its follow-up
//
// Results: results-<mode>.json next to this file. Every contact seen is stopped at the end.

import { writeFileSync } from "node:fs";
import {
  chromium,
  freshSession,
  keepNewestToken,
  newArmContext,
  oktaOutputs,
  openPage,
  parseMs,
  readDebug,
  sleep,
  stopContact,
} from "../abbench/common.mjs";

const MODE = process.argv[2] || "smoke";
const WAIT_S = 10;
const OUT = new URL(`./results-${MODE}.json`, import.meta.url).pathname;

const PLANS = {
  "Update my information": { follow: "my home address", path: "clarify" },
  "Change my address": { follow: "And what is my emergency contact?", path: "profile" },
  "PTO policy": { follow: "Does unused PTO carry over?", path: "policy" },
  "Buddy passes": { follow: "Can my parents use them?", path: "travel" },
};
const PAY = { typed: "When was my last paycheck and how much was it?", follow: "And the one before that?", path: "pay" };

// Extra instrumentation: WebSocket open and first frame on the performance clock.
function wsInstrument() {
  if (window !== window.top) return;
  const Native = window.WebSocket;
  window.__ws = [];
  window.WebSocket = function (url, protocols) {
    const ws = protocols === undefined ? new Native(url) : new Native(url, protocols);
    const rec = { host: String(url).split("/")[2], created: performance.now(), open: null, firstFrame: null, frames: 0 };
    window.__ws.push(rec);
    ws.addEventListener("open", () => (rec.open = performance.now()));
    ws.addEventListener("message", () => {
      rec.frames += 1;
      if (rec.firstFrame === null) rec.firstFrame = performance.now();
    });
    return ws;
  };
  window.WebSocket.prototype = Native.prototype;
  Object.assign(window.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
}

const okta = oktaOutputs();
const session = await freshSession(okta);
const browser = await chromium.launch();
const context = await newArmContext(browser, okta);
await context.addInitScript(wsInstrument);
const chats = [];
const contacts = [];
const save = () => writeFileSync(OUT, JSON.stringify({ mode: MODE, waitS: WAIT_S, chats }, null, 2));

async function resources(page) {
  return page.evaluate(() => ({
    timeOrigin: performance.timeOrigin,
    nav: (() => {
      const n = performance.getEntriesByType("navigation")[0];
      return n ? { responseEnd: n.responseEnd, domContentLoaded: n.domContentLoadedEventEnd, load: n.loadEventEnd } : null;
    })(),
    res: performance
      .getEntriesByType("resource")
      .filter((r) => /okta|\/api\/hr\/|participant|config\.json|manifest/.test(r.name))
      .map((r) => ({
        name: r.name.replace(/\?.*$/, "").slice(0, 120),
        start: r.startTime,
        connectStart: r.connectStart,
        connectEnd: r.connectEnd,
        requestStart: r.requestStart,
        responseStart: r.responseStart,
        responseEnd: r.responseEnd,
        duration: r.duration,
      })),
    ws: window.__ws,
  }));
}

async function turn(page, how, text) {
  const out = { how, text };
  if (how === "suggestion") {
    await page.locator(".suggestion", { hasText: text }).click();
  } else {
    await page.locator("#composer-input").fill(text);
    await page.evaluate(() => window.__armTurn());
    await page.locator("#composer-input").press("Enter");
  }
  await page.waitForFunction(() => window.__bench.doneAt !== null, null, { timeout: 60000, polling: 25 });
  await sleep(1500);
  const b = await page.evaluate(() => window.__bench);
  const { timeOrigin } = await page.evaluate(() => ({ timeOrigin: performance.timeOrigin }));
  out.clickEpoch = timeOrigin + b.clickAt;
  out.clickPerf = b.clickAt;
  out.firstMs = b.firstAt !== null ? b.firstAt - b.clickAt : null;
  out.doneMs = b.doneAt - b.clickAt;
  const debug = await readDebug(page);
  out.texts = debug.texts;
  out.notes = debug.notes;
  out.steps = debug.steps;
  out.page = debug.page;
  out.ids = Object.fromEntries(debug.ids || []);
  const send = (debug.steps || []).find((s) => s.name === "SendMessage");
  out.sendStartMs = send ? parseMs(send.start) : null;
  out.sendEndMs = send ? parseMs(send.start) + parseMs(send.dur) : null;
  // The participant/message request on the performance clock (cross-origin: start and duration).
  const msgs = await page.evaluate(
    (after) =>
      performance
        .getEntriesByType("resource")
        .filter((r) => r.name.includes("/participant/message") && r.startTime >= after - 5)
        .map((r) => ({ start: r.startTime, end: r.responseEnd || r.startTime + r.duration })),
    b.clickAt,
  );
  if (msgs.length) {
    out.msgReqStartMs = msgs[0].start - b.clickAt;
    out.msgReqEndMs = msgs[0].end - b.clickAt;
  }
  return out;
}

async function chat(label, path, first, follow, { firstHow = "suggestion", followUp = true } = {}) {
  const log = [];
  const rec = { label, path, startedAt: new Date().toISOString(), turns: [] };
  let opened;
  try {
    opened = await openPage(context, session, "/p/hr/?ff=debug", { log });
    const { page } = opened;
    rec.loadMs = opened.loadMs;
    rec.visibleEpoch = opened.visibleAt;
    await sleep(WAIT_S * 1000);
    rec.load = await resources(page);
    rec.turns.push(await turn(page, firstHow, first));
    if (followUp) {
      await sleep(1500);
      rec.turns.push(await turn(page, "typed", follow));
    }
    rec.contact = rec.turns.map((t) => t.ids.contact).find(Boolean) || null;
    rec.wsAfter = await page.evaluate(() => window.__ws);
    rec.net = opened.net;
    await keepNewestToken(page, session);
  } catch (error) {
    rec.error = error.message.split("\n")[0];
  } finally {
    rec.log = log.filter((l) => !l.includes("dynatrace.com"));
    if (opened) await opened.page.close().catch(() => {});
  }
  if (rec.contact) contacts.push(rec.contact);
  chats.push(rec);
  save();
  const t = (ms) => (ms === null || ms === undefined ? "-" : (ms / 1000).toFixed(2));
  console.log(
    `${chats.length} ${label.padEnd(22)} ${rec.contact || "-"} ` +
      rec.turns.map((x) => `first ${t(x.firstMs)} done ${t(x.doneMs)}`).join(" | ") +
      ` ${rec.error || ""}`,
  );
  return rec;
}

try {
  if (MODE === "smoke") {
    await chat("Change my address", "profile", "Change my address", PLANS["Change my address"].follow);
  } else if (MODE === "main") {
    const order = Object.keys(PLANS);
    for (let round = 0; round < 5; round++) {
      for (const s of order) await chat(s, PLANS[s].path, s, PLANS[s].follow);
      if (round === 1 || round === 3) await chat("pay", "pay", PAY.typed, PAY.follow, { firstHow: "typed" });
    }
  } else if (MODE === "reuse") {
    for (let pair = 0; pair < 3; pair++) {
      const a = await chat(`reuse ${pair} A`, "profile", "Change my address", null, { followUp: false });
      const doneEpoch = a.turns[0] ? a.turns[0].clickEpoch + a.turns[0].doneMs : Date.now();
      // Chat B's click comes 60 s after chat A's answer: open the page 49 s after it, then the
      // usual 10 s wait and about 1 s of load.
      const until = doneEpoch + 49000 - Date.now();
      if (until > 0) await sleep(until);
      await chat(`reuse ${pair} B`, "profile", "Change my address", null, { followUp: false });
    }
  }
} finally {
  await context.close();
  await browser.close();
  save();
}
let stopped = 0;
for (const c of contacts) if (stopContact(c)) stopped += 1;
console.log(`stopped ${stopped} of ${contacts.length} contacts`);
