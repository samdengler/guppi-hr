// Headless browser check of the HR project on the platform page (docs/phase-8.md, step 7),
// adapted from guppi-gpt's scripts/browser-check.mjs. Signs the page in without Google by
// seeding the platform page's IndexedDB session before load, the way a reload after a real
// sign-in finds it, then runs the four scenarios of docs/plan.md on /p/hr/:
//
//   thread A  disambiguation   "I need to update my information"
//   thread B  confirmation     the address change, then "yes"
//             sticky context   "what about my emergency contact?"
//             topic shift      "How many buddy passes do I get?", then "I need to talk to someone"
//
// For every turn it records the reply label, every status line the reply showed, and the
// start of the reply text, and it saves .deploy/phase-8-<scenario>.png after each scenario.
// It then opens / and /p/mcp-app/ and records that each still reaches the chat screen.
//
// The refresh token comes from $HOME/.config/guppi/test-session.json, as for guppi-gpt's
// scripts/test-token.sh; the platform's auth domain and app client id come from the
// platform's public config.json. The user pool client rotates refresh tokens on every use,
// so each rotation (this script's own refresh for the id token claims, and the page's
// silent refresh) is written back to that file, mode 600, under the same lock test-token.sh
// takes. No token is printed or logged.
//
//   node scripts/browser-check.mjs        (Playwright is a dev dependency of web/)

import { createRequire } from "node:module";
import { chmodSync, mkdirSync, readFileSync, renameSync, rmdirSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const { chromium } = createRequire(join(ROOT, "web", "package.json"))("playwright");

const SITE = process.env.GUPPI_SITE_URL || "https://chat.dengler.io";
const SESSION_FILE =
  process.env.GUPPI_TEST_SESSION_FILE || join(homedir(), ".config", "guppi", "test-session.json");
const OUT = join(ROOT, ".deploy");
const TURN_TIMEOUT_MS = 180000;

const SCENARIOS = [
  { name: "disambiguation", thread: "A", turns: ["I need to update my information"] },
  {
    name: "confirmation",
    thread: "B",
    turns: ["Change my home address to 419 Glendale Ave, Decatur GA 30030", "yes"],
  },
  { name: "sticky", thread: "B", turns: ["what about my emergency contact?"] },
  {
    name: "topic-shift",
    thread: "B",
    turns: ["How many buddy passes do I get?", "I need to talk to someone"],
  },
];

function fail(message) {
  console.error(`browser-check: ${message}`);
  process.exit(1);
}

async function platformConfig() {
  const response = await fetch(`${SITE}/config.json`, { cache: "no-store" });
  if (!response.ok) fail(`config.json answered ${response.status}`);
  const config = await response.json();
  return { auth: config.authDomain, client: config.userPoolClientId };
}

async function withLock(fn) {
  const lock = `${SESSION_FILE}.lock`;
  for (let i = 0; i < 100; i += 1) {
    try {
      mkdirSync(lock);
      try {
        return await fn();
      } finally {
        rmdirSync(lock);
      }
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  fail(`could not take ${lock}`);
}

function readRefreshToken() {
  const token = JSON.parse(readFileSync(SESSION_FILE, "utf8")).refreshToken;
  if (typeof token !== "string" || !token) fail(`${SESSION_FILE} has no refreshToken`);
  return token;
}

function writeRefreshToken(token) {
  const tmp = `${SESSION_FILE}.${process.pid}`;
  writeFileSync(tmp, JSON.stringify({ refreshToken: token }), { mode: 0o600 });
  chmodSync(tmp, 0o600);
  renameSync(tmp, SESSION_FILE);
}

function decodeClaims(idToken) {
  const payload = JSON.parse(Buffer.from(idToken.split(".")[1], "base64url").toString("utf8"));
  const { email, name, given_name, family_name, sub } = payload;
  return { email, name, given_name, family_name, sub };
}

// One refresh grant, for a fresh id token's claims; the rotated refresh token is stored at once.
async function freshSession({ auth, client }) {
  return withLock(async () => {
    const body = new URLSearchParams({
      grant_type: "refresh_token",
      client_id: client,
      refresh_token: readRefreshToken(),
    });
    const response = await fetch(`https://${auth}/oauth2/token`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body,
    });
    const json = await response.json().catch(() => ({}));
    if (!response.ok || !json.id_token) fail(`refresh refused: ${json.error || response.status}`);
    const refreshToken = json.refresh_token || body.get("refresh_token");
    if (json.refresh_token) writeRefreshToken(json.refresh_token);
    return { refreshToken, claims: decodeClaims(json.id_token) };
  });
}

// Runs in every frame before the page's scripts; only the top frame has storage.
function seedSession(record) {
  if (window !== window.top) return;
  const open = indexedDB.open("guppigpt-session", 1);
  open.onupgradeneeded = () => {
    if (!open.result.objectStoreNames.contains("session")) {
      open.result.createObjectStore("session", { keyPath: "id" });
    }
  };
  open.onsuccess = () => {
    const tx = open.result.transaction("session", "readwrite");
    tx.objectStore("session").put(record);
    tx.oncomplete = () => open.result.close();
  };
}

// Records every text the newest reply's status line and label take, since the running
// lines ("Asking the Profile agent…") last only until the next event.
function watchReplies() {
  if (window !== window.top) return;
  window.__hrSeen = [];
  const observer = new MutationObserver(() => {
    const replies = document.querySelectorAll(".reply");
    const reply = replies[replies.length - 1];
    if (!reply) return;
    for (const selector of [".reply-status", ".reply-label"]) {
      const el = reply.querySelector(selector);
      const text = el && !el.hidden ? el.textContent : "";
      const seen = window.__hrSeen;
      if (text && !seen.some((entry) => entry.kind === selector && entry.text === text && entry.reply === replies.length)) {
        seen.push({ reply: replies.length, kind: selector, text });
      }
    }
  });
  document.addEventListener("DOMContentLoaded", () => {
    observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true });
  });
}

// The page rotates the refresh token on its silent refresh; this reads the newest back.
async function storedRefreshToken(page) {
  return page.evaluate(
    () =>
      new Promise((resolve) => {
        const open = indexedDB.open("guppigpt-session", 1);
        open.onsuccess = () => {
          const get = open.result.transaction("session").objectStore("session").get("current");
          get.onsuccess = () => resolve(get.result ? get.result.refreshToken : null);
          get.onerror = () => resolve(null);
        };
        open.onerror = () => resolve(null);
      }),
  );
}

async function keepNewestToken(page, session) {
  const newest = await storedRefreshToken(page);
  if (newest && newest !== session.refreshToken) {
    await withLock(async () => writeRefreshToken(newest));
    session.refreshToken = newest;
  }
}

async function openSignedIn(browser, session, path, log) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  const record = {
    id: "current",
    refreshToken: session.refreshToken,
    claims: session.claims,
    savedAt: Date.now(),
  };
  await context.addInitScript(seedSession, record);
  await context.addInitScript(watchReplies);
  const page = await context.newPage();
  page.on("console", (message) => {
    if (message.type() === "error" || message.type() === "warning") {
      log.push(`${path} console ${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => log.push(`${path} pageerror: ${error.message}`));
  // Failed responses by origin and path only; a query string could carry an OAuth value.
  page.on("response", (response) => {
    if (response.status() < 400) return;
    const url = new URL(response.url());
    log.push(`${path} response ${response.status()}: ${url.origin}${url.pathname}`);
  });
  await page.goto(`${SITE}${path}`);
  await page.locator("#chat-screen").waitFor({ state: "visible", timeout: 30000 });
  await keepNewestToken(page, session);
  return { context, page };
}

// The composer accepts a send only while the page is idle, so a filled input with an
// enabled send button means the previous run has ended (or failed, which shows an error).
async function waitIdle(page) {
  await page.locator("#composer-input").fill(".");
  await page.waitForFunction(
    () => {
      const errors = [...document.querySelectorAll(".reply-error")].filter((el) => !el.hidden);
      return errors.length > 0 || !document.querySelector("#send-btn").disabled;
    },
    null,
    { timeout: TURN_TIMEOUT_MS },
  );
  await page.locator("#composer-input").fill("");
}

async function turn(page, text) {
  await waitIdle(page);
  const before = await page.locator(".reply").count();
  await page.locator("#composer-input").fill(text);
  await page.locator("#composer-input").press("Enter");
  await page.locator(".reply").nth(before).waitFor({ state: "attached", timeout: 30000 });
  await waitIdle(page);
  const reply = page.locator(".reply").nth(before);
  const errorVisible = await reply.locator(".reply-error").isVisible().catch(() => false);
  const seen = await page.evaluate((index) => window.__hrSeen.filter((entry) => entry.reply === index + 1), before);
  return {
    sent: text,
    label: await reply.locator(".reply-label").textContent(),
    statusLines: seen.filter((entry) => entry.kind === ".reply-status").map((entry) => entry.text),
    labels: seen.filter((entry) => entry.kind === ".reply-label").map((entry) => entry.text),
    reply: ((await reply.locator(".reply-text").textContent()) || "").slice(0, 400),
    error: errorVisible ? await reply.locator(".reply-error").textContent() : null,
  };
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const session = await freshSession(await platformConfig());
  const browser = await chromium.launch();
  const log = [];
  const results = { scenarios: {}, pages: {} };
  try {
    const threads = {};
    try {
      for (const scenario of SCENARIOS) {
        if (!threads[scenario.thread]) {
          threads[scenario.thread] = await openSignedIn(browser, session, "/p/hr/", log);
          const { page } = threads[scenario.thread];
          results.pages.hr = {
            brand: await page.locator("#brand").textContent(),
            suggestions: await page.locator("#suggestions .suggestion").allTextContents(),
          };
        }
        const { page } = threads[scenario.thread];
        const turns = [];
        try {
          for (const text of scenario.turns) turns.push(await turn(page, text));
        } catch (error) {
          turns.push({ failed: error.message.split("\n")[0] });
        }
        results.scenarios[scenario.name] = turns;
        await page.screenshot({ path: join(OUT, `phase-8-${scenario.name}.png`), fullPage: true });
        await keepNewestToken(page, session);
      }
    } finally {
      for (const { context, page } of Object.values(threads)) {
        await keepNewestToken(page, session).catch(() => {});
        await context.close();
      }
    }
    // The platform's own pages still answer.
    for (const [name, path] of [["root", "/"], ["mcpApp", "/p/mcp-app/"]]) {
      const { context, page } = await openSignedIn(browser, session, path, log);
      try {
        results.pages[name] = {
          brand: await page.locator("#brand").textContent(),
          title: await page.title(),
          placeholder: await page.locator("#composer-input").getAttribute("placeholder"),
        };
        await page.screenshot({ path: join(OUT, `phase-8-${name}.png`), fullPage: true });
        await keepNewestToken(page, session);
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(results, null, 2));
  if (log.length) console.log(log.join("\n"));
  const failed = Object.values(results.scenarios).flat().some((t) => t.failed || t.error);
  if (failed) process.exitCode = 1;
}

main().catch((error) => fail(error.message.split("\n")[0]));
