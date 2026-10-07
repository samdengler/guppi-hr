// The chat start and the greeting replay, shared by the experiment page (main.js) and the
// /p/hr-widget/ extension (widget.js). Touchpoint calls `details` when it opens a chat and on
// every restart, its own restart button included, so the greeting replay starts from there.

import { chatDetails, greetingLines, greetingToAdd } from "./hr.js";

const GREETING_WAIT_MS = 12_000; // the chat start's own greeting limit
const LAST_CONTACT = "hr-touchpoint-contact";

const sleep = (delay) => new Promise((resolve) => setTimeout(resolve, delay));
const ms = (value) => (typeof value === "number" ? `${Math.round(value).toLocaleString("en-US")} ms` : "n/a");
const short = (id) => (id ? id.slice(0, 8) : "none");

// The last contact, so the next start ends it (E9), across a reload as on /p/hr/.
function lastContact() {
  try {
    return sessionStorage.getItem(LAST_CONTACT);
  } catch {
    return null;
  }
}

function rememberContact(id) {
  try {
    sessionStorage.setItem(LAST_CONTACT, id);
  } catch {
    /* the next start leaves the old contact to its 60 minute limit */
  }
}

/**
 * Touchpoint's `details` option over the /p/hr/ chat start. Its own `chatEndpoint` cannot
 * be used: that request carries no Authorization header (aws-feedback C21). `bearer`
 * returns the employee's Okta access token (or a promise of it); `handler` returns
 * Touchpoint's conversation handler once the widget exists; `note` takes one plain-text
 * line per step. `current` holds the contact the widget is on.
 */
export function chatStarter({ bearer, rules, handler, note, fetchImpl = (...args) => fetch(...args) }) {
  const current = { contactId: null, expiresAt: null };
  let responses = [];

  async function replayGreeting(contactId) {
    // The chat start received the greeting on its own socket before it answered, and
    // Touchpoint shows only what arrives on its socket (aws-feedback C22).
    const started = performance.now();
    while (performance.now() - started < GREETING_WAIT_MS) {
      const h = handler();
      if (current.contactId !== contactId) return;
      const lines = h ? greetingLines(await h.getConnectTranscript(), rules) : [];
      if (lines.length > 0) {
        const missing = greetingToAdd(lines, responses, contactId);
        if (missing.length > 0) {
          h.appendMessageToTranscript({
            type: "bot",
            receivedAt: Date.now(),
            payload: {
              conversationId: contactId,
              messages: missing.map((text) => ({ text, choices: [] })),
              metadata: { uploadUrls: [] },
            },
          });
        }
        h.setInterimMessage(undefined);
        note(`greeting read from the transcript after ${ms(performance.now() - started)}; ${missing.length} of ${lines.length} line(s) added`);
        return;
      }
      await sleep(250);
    }
    note(`no greeting in the transcript after ${ms(GREETING_WAIT_MS)}`);
  }

  async function details() {
    const started = performance.now();
    const previousContactId = lastContact();
    note(previousContactId ? `chat start requested, ending contact ${short(previousContactId)}` : "chat start requested");
    try {
      const token = await bearer();
      const res = await fetchImpl(rules.start, {
        method: "POST",
        headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
        body: JSON.stringify(previousContactId ? { previousContactId } : {}),
      });
      const answer = chatDetails(res.status, await res.json().catch(() => null), rules.lines);
      current.contactId = answer.details.contactId;
      current.expiresAt = answer.expiresAt;
      rememberContact(answer.details.contactId);
      note(
        `chat start answered after ${ms(performance.now() - started)} (inside the function ${ms(answer.functionMs)}): ` +
          `contact ${short(answer.details.contactId)}, good until ${new Date(answer.expiresAt).toLocaleTimeString()}`,
      );
      replayGreeting(answer.details.contactId);
      return answer.details;
    } catch (error) {
      note(`chat start failed: ${error.message}`);
      throw error;
    }
  }

  return {
    details,
    current,
    /** Keeps the widget's latest response list, for the greeting replay's dedupe. */
    track(all) {
      responses = all;
    },
  };
}
