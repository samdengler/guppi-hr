// Experiment T1 (connect/docs/touchpoint-experiment.md): AWS's Touchpoint widget in front of
// the /p/hr/ backend. The widget gets its chat from Touchpoint's `details` option, which
// calls the chat start with the employee's bearer token; everything behind the chat start
// (contact flow, canvas, sub-agents, tools) is the live /p/hr/ path, unchanged. The page's
// own text (the run log, the buttons) is plain text; only the widget renders replies.

import { create } from "@amazon-connect-touchpoint/web";
import manifest from "../../web/manifest.json";
import { chatStarter } from "./chat.js";
import { ChatStartError, hiddenLinesShown, turnTimes } from "./hr.js";

const REGION = "us-east-1";
const rules = manifest.connectChat;
const t0 = performance.now();
const log = document.getElementById("log");

const ms = (value) => (typeof value === "number" ? `${Math.round(value).toLocaleString("en-US")} ms` : "n/a");

function note(text) {
  const line = document.createElement("li");
  line.textContent = `${ms(performance.now() - t0).padStart(10)}  ${text}`;
  log.append(line);
  line.scrollIntoView({ block: "nearest" });
}

// The dev server stands in for the platform's sign-in (vite.config.js).
async function bearer() {
  const res = await fetch("/dev/token", { method: "POST" });
  const body = await res.json().catch(() => ({}));
  if (!res.ok || typeof body.token !== "string") {
    throw new ChatStartError("token", `No Okta test session (${body.error ?? res.status}); see connect/touchpoint/README.md.`);
  }
  return body.token;
}

let touchpoint = null;
const handler = () => touchpoint?.conversationHandler;
const starter = chatStarter({ bearer, rules, handler, note });

touchpoint = await create({
  config: {
    details: starter.details,
    region: REGION,
    // Receipts stay off as on /p/hr/ (D57, V5). Touchpoint's typing events cannot be turned off.
    globalConfig: { features: { messageReceipts: { shouldSendMessageReceipts: false } } },
  },
  input: "text",
  windowSize: "side-by-side",
  assistantName: manifest.assistant,
  userMessageBubble: true,
  agentMessageBubble: true,
});
touchpoint.expanded = true;
note("Touchpoint mounted");

let turnsNoted = 0;
let hiddenNoted = 0;
handler().subscribe((all) => {
  starter.track(all);
  const turns = turnTimes(all);
  if (turns.length < turnsNoted) turnsNoted = 0;
  for (; turnsNoted < turns.length && turns[turnsNoted].firstReplyMs != null; turnsNoted += 1) {
    const turn = turns[turnsNoted];
    note(`question ${turnsNoted + 1} "${turn.text}": first reply after ${ms(turn.firstReplyMs)}`);
  }
  const hidden = hiddenLinesShown(all, rules);
  if (hidden.length < hiddenNoted) hiddenNoted = 0;
  for (; hiddenNoted < hidden.length; hiddenNoted += 1) note(`the widget shows a line /p/hr/ hides: "${hidden[hiddenNoted]}"`);
});

let expiryNotedFor = null;
setInterval(() => {
  const { contactId, expiresAt } = starter.current;
  if (contactId && expiryNotedFor !== contactId && Date.now() > expiresAt) {
    expiryNotedFor = contactId;
    note(`contact ${contactId.slice(0, 8)} is past its hop tokens' expiry; delegated questions fail until New chat`);
  }
}, 15_000);

const suggestions = document.getElementById("suggestions");
for (const { label, prompt } of manifest.suggestions ?? []) {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = label;
  button.title = prompt;
  button.addEventListener("click", () => {
    touchpoint.expanded = true;
    handler().sendText(prompt);
  });
  suggestions.append(button);
}

document.getElementById("new-chat").addEventListener("click", () => {
  note("New chat");
  handler().reset({ clearResponses: true });
});
