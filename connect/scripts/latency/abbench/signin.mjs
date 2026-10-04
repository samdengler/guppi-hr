// Proves the headless sign-in: /p/hr/ shows the chat (not the sign-in screen) and its four
// suggestions. Asks nothing.
import { chromium, freshSession, newArmContext, oktaOutputs, openPage, sleep } from "./common.mjs";

const okta = oktaOutputs();
const session = await freshSession(okta);
const browser = await chromium.launch();
const log = [];
try {
  const context = await newArmContext(browser, okta);
  const { page, net, loadMs } = await openPage(context, session, "/p/hr/?ff=debug", { log });
  await sleep(4000);
  const state = await page.evaluate(() => ({
    chatVisible: !document.getElementById("chat-screen").hidden,
    signinVisible: !document.getElementById("signin-screen").hidden,
    brand: document.getElementById("brand").textContent,
    suggestions: [...document.querySelectorAll(".suggestion")].map((s) => s.textContent),
    features: document.body.dataset.features,
    email: document.getElementById("account-email")?.textContent,
  }));
  await page.screenshot({ path: new URL("./signin.png", import.meta.url).pathname });
  console.log(JSON.stringify({ loadMs, state, net: net.map((n) => `${n.kind} ${n.method} ${n.host}${n.path} ${n.status ?? ""}`) }, null, 2));
  await context.close();
} finally {
  await browser.close();
}
if (log.length) console.log(log.join("\n"));
