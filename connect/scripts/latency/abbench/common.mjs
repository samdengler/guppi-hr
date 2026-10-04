// Shared helpers for the /p/hr/ A/B bench and live checks: a passwordless headless sign-in
// (the way guppi-gpt scripts/browser-check.mjs seeds the page's IndexedDB session), the
// page's /config.json routed to the harness's Okta client (plan M7), and per-page
// instrumentation. No token is ever printed or written anywhere but the session file.

import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { chmodSync, mkdirSync, readFileSync, renameSync, rmdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const GUPPI_GPT = join(homedir(), "src/github.com/samdengler/guppi-gpt");
export const { chromium } = createRequire(join(GUPPI_GPT, "web", "package.json"))("playwright");

export const SITE = process.env.GUPPI_SITE_URL || "https://chat.dengler.io";
const SESSION_FILE = join(homedir(), ".config", "guppi", "test-session.json");
export const INSTANCE_ID = "5665011a-f5fa-40e3-92d0-85ff625d10f6";

const ssm = (name) =>
  execFileSync("aws", ["ssm", "get-parameter", "--name", name, "--query", "Parameter.Value", "--output", "text", "--region", "us-east-1"], {
    encoding: "utf8",
  }).trim();

export function oktaOutputs() {
  return { tokenUrl: ssm("/guppi/okta/token-url"), client: ssm("/guppi/okta/harness-client-id") };
}

async function withLock(fn) {
  const lock = `${SESSION_FILE}.lock`;
  for (let i = 0; i < 100; i += 1) {
    try {
      mkdirSync(lock);
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      await new Promise((r) => setTimeout(r, 100));
      continue;
    }
    try {
      return await fn();
    } finally {
      rmdirSync(lock);
    }
  }
  throw new Error(`could not take ${lock}`);
}

function readRefreshToken() {
  const token = JSON.parse(readFileSync(SESSION_FILE, "utf8")).refreshToken;
  if (typeof token !== "string" || !token) throw new Error(`${SESSION_FILE} has no refreshToken`);
  return token;
}

function writeRefreshToken(token) {
  const tmp = `${SESSION_FILE}.${process.pid}`;
  writeFileSync(tmp, JSON.stringify({ refreshToken: token }), { mode: 0o600 });
  chmodSync(tmp, 0o600);
  renameSync(tmp, SESSION_FILE);
}

function decodeClaims(idToken) {
  const p = JSON.parse(Buffer.from(idToken.split(".")[1], "base64url").toString("utf8"));
  const { email, name, given_name, family_name, sub } = p;
  return { email, name, given_name, family_name, sub };
}

/** One refresh grant for fresh id token claims; the rotated refresh token is stored at once. */
export async function freshSession(okta) {
  return withLock(async () => {
    const body = new URLSearchParams({ grant_type: "refresh_token", client_id: okta.client, refresh_token: readRefreshToken() });
    const response = await fetch(okta.tokenUrl, { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body });
    const json = await response.json().catch(() => ({}));
    if (!response.ok || !json.id_token) throw new Error(`refresh refused: ${json.error || response.status}`);
    const refreshToken = json.refresh_token || body.get("refresh_token");
    if (json.refresh_token) writeRefreshToken(json.refresh_token);
    return { refreshToken, claims: decodeClaims(json.id_token), okta };
  });
}

function seedSession(record) {
  if (window !== window.top) return;
  const open = indexedDB.open("guppigpt-session", 1);
  open.onupgradeneeded = () => {
    if (!open.result.objectStoreNames.contains("session")) open.result.createObjectStore("session", { keyPath: "id" });
  };
  open.onsuccess = () => {
    const tx = open.result.transaction("session", "readwrite");
    tx.objectStore("session").put(record);
    tx.oncomplete = () => open.result.close();
  };
}

async function storedRefreshToken(page) {
  return page.evaluate(
    () =>
      new Promise((resolve) => {
        const open = indexedDB.open("guppigpt-session", 1);
        open.onsuccess = () => {
          try {
            const get = open.result.transaction("session").objectStore("session").get("current");
            get.onsuccess = () => resolve(get.result ? get.result.refreshToken : null);
            get.onerror = () => resolve(null);
          } catch {
            resolve(null);
          }
        };
        open.onerror = () => resolve(null);
      }),
  );
}

/** Reads the page's rotated refresh token back into the shared session and the file. */
export async function keepNewestToken(page, session) {
  const newest = await storedRefreshToken(page).catch(() => null);
  if (newest && newest !== session.refreshToken) {
    await withLock(async () => writeRefreshToken(newest));
    session.refreshToken = newest;
  }
}

// Per-page instrumentation, before the page's scripts: CSP violations, the click on a
// suggestion, the first reply text in the DOM, the debug block's "done", and an optional
// visibility override for the hidden-tab check.
function instrument() {
  if (window !== window.top) return;
  const w = window;
  w.__bench = { csp: [], clickAt: null, firstAt: null, doneAt: null, firstText: null };
  document.addEventListener("securitypolicyviolation", (e) => {
    w.__bench.csp.push({ blocked: String(e.blockedURI).slice(0, 120), directive: e.violatedDirective });
  });
  // Visibility override: __setVisibility("hidden" | "visible") fires visibilitychange.
  let vis = null;
  try {
    Object.defineProperty(Document.prototype, "visibilityState", { configurable: true, get: () => vis ?? "visible" });
    Object.defineProperty(Document.prototype, "hidden", { configurable: true, get: () => (vis ?? "visible") === "hidden" });
  } catch {}
  w.__setVisibility = (state) => {
    vis = state;
    document.dispatchEvent(new Event("visibilitychange"));
  };
  w.__armTurn = () => {
    w.__bench.clickAt = performance.now();
    w.__bench.firstAt = null;
    w.__bench.doneAt = null;
    w.__bench.firstText = null;
    w.__bench.turnIndex = document.querySelectorAll(".reply").length;
  };
  document.addEventListener(
    "click",
    (e) => {
      if (e.target && e.target.closest && e.target.closest(".suggestion")) w.__armTurn();
    },
    true,
  );
  const check = () => {
    const b = w.__bench;
    if (b.clickAt === null) return;
    const replies = document.querySelectorAll(".reply");
    const own = [...replies].slice(b.turnIndex ?? 0);
    if (b.firstAt === null) {
      for (const reply of own) {
        for (const t of reply.querySelectorAll(".reply-text")) {
          if (t.textContent.trim()) {
            b.firstAt = performance.now();
            b.firstText = t.textContent.trim().slice(0, 80);
            break;
          }
        }
        if (b.firstAt !== null) break;
      }
    }
    if (b.doneAt === null) {
      for (const reply of own) {
        const s = reply.querySelector(".reply-debug-summary");
        if (s && /· (done|failed) /.test(s.textContent)) b.doneAt = performance.now();
      }
    }
  };
  const start = () => new MutationObserver(check).observe(document.documentElement, { subtree: true, childList: true, characterData: true });
  if (document.documentElement) start();
  else document.addEventListener("DOMContentLoaded", start);
}

/** A context for one arm: /config.json routed to the harness's client, instrumentation. */
export async function newArmContext(browser, okta) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await context.route("**/config.json", async (route) => {
    const response = await route.fetch();
    const config = await response.json();
    if (config.oidc) config.oidc.clientId = okta.client;
    await route.fulfill({ response, json: config });
  });
  await context.addInitScript(instrument);
  return context;
}

const INTEREST = /\/api\/hr\/(chat\/start|chat\/report|invocations)|participant\.connect|\/participant\//;

/** Opens a signed-in page at `path` and records the requests of interest (path only). */
export async function openPage(context, session, path, { log = [] } = {}) {
  const page = await context.newPage();
  const record = { id: "current", refreshToken: session.refreshToken, claims: session.claims, savedAt: Date.now() };
  await page.addInitScript(seedSession, record);
  const net = [];
  const sockets = [];
  page.on("request", (req) => {
    const url = new URL(req.url());
    if (!INTEREST.test(url.href)) return;
    net.push({ t: Date.now(), method: req.method(), host: url.host, path: url.pathname, kind: "request" });
  });
  page.on("response", (res) => {
    const url = new URL(res.url());
    if (res.status() >= 400) log.push(`response ${res.status()}: ${url.origin}${url.pathname}`);
    if (!INTEREST.test(url.href)) return;
    net.push({ t: Date.now(), method: res.request().method(), host: url.host, path: url.pathname, status: res.status(), kind: "response" });
  });
  page.on("requestfailed", (req) => {
    const url = new URL(req.url());
    if (!INTEREST.test(url.href)) return;
    net.push({ t: Date.now(), method: req.method(), host: url.host, path: url.pathname, failure: req.failure()?.errorText, kind: "failed" });
  });
  page.on("websocket", (ws) => {
    const url = new URL(ws.url());
    const entry = { t: Date.now(), host: url.host, frames: 0, closedAt: null };
    sockets.push(entry);
    ws.on("framereceived", () => (entry.frames += 1));
    ws.on("close", () => (entry.closedAt = Date.now()));
  });
  page.on("console", (m) => {
    if (m.type() === "error") log.push(`console error: ${m.text().slice(0, 200)}`);
  });
  page.on("pageerror", (e) => log.push(`pageerror: ${e.message.slice(0, 200)}`));
  const t0 = Date.now();
  await page.goto(`${SITE}${path}`);
  await page.locator("#chat-screen").waitFor({ state: "visible", timeout: 30000 });
  const visibleAt = Date.now();
  await keepNewestToken(page, session);
  return { page, net, sockets, loadMs: visibleAt - t0, visibleAt };
}

/** The last reply's debug block as data: page lines, agent steps, ids and notes. */
export async function readDebug(page, index = -1) {
  return page.evaluate((index) => {
    const replies = [...document.querySelectorAll(".reply")];
    const reply = replies.at(index);
    if (!reply) return null;
    const block = reply.querySelector(".reply-debug");
    const lines = (root) =>
      [...root.querySelectorAll(":scope > .reply-debug-line")].map((l) => [
        l.querySelector(".reply-debug-key")?.textContent,
        l.querySelector(".reply-debug-value")?.textContent,
      ]);
    const out = { summary: null, page: [], agentHeading: null, steps: [], ids: [], notes: [], texts: [] };
    out.texts = [...reply.querySelectorAll(".reply-text")].map((t) => t.textContent);
    if (!block) return out;
    out.summary = block.querySelector(".reply-debug-summary")?.textContent;
    const lists = block.querySelectorAll(".reply-debug-lines");
    if (lists[0]) out.page = lines(lists[0]);
    if (lists[1]) out.ids = lines(lists[1]);
    const headings = [...block.querySelectorAll(".reply-debug-heading")].map((h) => h.textContent);
    out.agentHeading = headings[1] || null;
    out.steps = [...block.querySelectorAll(".reply-debug-step")].map((s) => {
      const nums = [...s.querySelectorAll(".reply-debug-num")].map((n) => n.textContent);
      const lane = s.querySelector(".reply-debug-lane")?.textContent || "";
      const name = s.querySelector(".reply-debug-step-name")?.textContent.slice(lane.length);
      return { lane, name, start: nums[0], dur: nums[1] };
    });
    out.notes = [...block.querySelectorAll(".reply-debug-note")].map((n) => n.textContent);
    return out;
  }, index);
}

/** "1.23 s" or "456 ms" to milliseconds. */
export function parseMs(text) {
  if (!text) return null;
  const m = /([\d.]+)\s*(ms|s)/.exec(text);
  if (!m) return null;
  return m[2] === "s" ? Number(m[1]) * 1000 : Number(m[1]);
}

export function stopContact(contactId) {
  try {
    execFileSync("aws", ["connect", "stop-contact", "--instance-id", INSTANCE_ID, "--contact-id", contactId, "--region", "us-east-1"], {
      stdio: "ignore",
    });
    return true;
  } catch {
    return false;
  }
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
