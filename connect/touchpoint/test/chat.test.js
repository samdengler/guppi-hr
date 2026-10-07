import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, test } from "node:test";
import { chatStarter } from "../src/chat.js";
import { greetingToAdd } from "../src/hr.js";

const rules = JSON.parse(readFileSync(new URL("../../web/manifest.json", import.meta.url), "utf8")).connectChat;
const CONTACT_A = "11111111-2222-3333-4444-555555555555";
const CONTACT_B = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
const PARTICIPANT = "66666666-7777-8888-9999-000000000000";
const GREETING = "Hi, I'm the HR assistant.";

function answer(contactId) {
  return {
    status: 200,
    json: async () => ({
      data: { startChatResult: { ContactId: contactId, ParticipantId: PARTICIPANT, ParticipantToken: "participant-token" } },
      region: "us-east-1",
      expiresAt: 3_600_000,
      timing: { total_ms: 2000 },
    }),
  };
}

// A stand-in for Touchpoint's conversation handler: a transcript with the greeting, and
// what the replay adds.
function fakeHandler() {
  const appended = [];
  const interim = [];
  return {
    appended,
    interim,
    getConnectTranscript: async () => [{ Type: "MESSAGE", ParticipantRole: "CUSTOM_BOT", Content: `${GREETING}${rules.endMark}` }],
    appendMessageToTranscript: (response) => appended.push(response),
    setInterimMessage: (value) => interim.push(value),
  };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 20));

let store;
beforeEach(() => {
  store = new Map();
  globalThis.sessionStorage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, String(v)) };
});
afterEach(() => {
  delete globalThis.sessionStorage;
});

test("details posts the bearer to the chat start, then the next start names the previous contact", async () => {
  const calls = [];
  const contacts = [CONTACT_A, CONTACT_B];
  const h = fakeHandler();
  const starter = chatStarter({
    bearer: async () => "okta-access-token",
    rules,
    handler: () => h,
    note: () => {},
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return answer(contacts.shift());
    },
  });

  assert.deepEqual(await starter.details(), { contactId: CONTACT_A, participantId: PARTICIPANT, participantToken: "participant-token" });
  await starter.details();
  assert.equal(calls[0].url, rules.start);
  assert.equal(calls[0].init.headers.authorization, "Bearer okta-access-token");
  assert.deepEqual(JSON.parse(calls[0].init.body), {});
  assert.deepEqual(JSON.parse(calls[1].init.body), { previousContactId: CONTACT_A });
  assert.equal(starter.current.contactId, CONTACT_B);
});

test("each start replays the greeting for its own contact and clears Thinking", async () => {
  const h = fakeHandler();
  const contacts = [CONTACT_A, CONTACT_B];
  const starter = chatStarter({
    bearer: () => "t",
    rules,
    handler: () => h,
    note: () => {},
    fetchImpl: async () => answer(contacts.shift()),
  });

  await starter.details();
  await settle();
  starter.track(h.appended);
  await starter.details();
  await settle();
  assert.deepEqual(
    h.appended.map((r) => [r.payload.conversationId, r.payload.messages.map((m) => m.text)]),
    [
      [CONTACT_A, [GREETING]],
      [CONTACT_B, [GREETING]],
    ],
  );
  assert.deepEqual(h.interim, [undefined, undefined]);
});

test("a refused start throws and replays nothing", async () => {
  const h = fakeHandler();
  const starter = chatStarter({
    bearer: () => "t",
    rules,
    handler: () => h,
    note: () => {},
    fetchImpl: async () => ({ status: 401, json: async () => ({ error: "unauthorized" }) }),
  });

  await assert.rejects(starter.details(), { kind: "unauthorized" });
  await settle();
  assert.deepEqual(h.appended, []);
});

test("greetingToAdd counts only what the widget shows for the same contact", () => {
  const shown = [{ type: "bot", payload: { conversationId: CONTACT_A, messages: [{ text: GREETING }] } }];
  assert.deepEqual(greetingToAdd([GREETING], shown, CONTACT_A), []);
  assert.deepEqual(greetingToAdd([GREETING], shown, CONTACT_B), [GREETING]);
});
