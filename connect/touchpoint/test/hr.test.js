import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { ChatStartError, chatDetails, greetingLines, hiddenLinesShown, turnTimes, visibleText } from "../src/hr.js";

const manifest = JSON.parse(readFileSync(new URL("../../web/manifest.json", import.meta.url), "utf8"));
const rules = manifest.connectChat;
const END = rules.endMark;
const CLOSED = rules.closedMark;

const CONTACT = "11111111-2222-3333-4444-555555555555";
const PARTICIPANT = "66666666-7777-8888-9999-000000000000";
const answer = {
  data: { startChatResult: { ContactId: CONTACT, ParticipantId: PARTICIPANT, ParticipantToken: "participant-token" } },
  region: "us-east-1",
  startedAt: 1_000,
  expiresAt: 3_600_000,
  restarted: false,
  timing: { steps: [], total_ms: 1990, ids: { contact: CONTACT }, notes: [] },
};

test("chatDetails turns the chat start's answer into Touchpoint's chat details", () => {
  assert.deepEqual(chatDetails(200, answer, rules.lines), {
    details: { contactId: CONTACT, participantId: PARTICIPANT, participantToken: "participant-token" },
    region: "us-east-1",
    expiresAt: 3_600_000,
    restarted: false,
    functionMs: 1990,
  });
});

test("chatDetails refuses each failure the chat start answers, with its kind", () => {
  const kind = (status, body) => {
    try {
      chatDetails(status, body, rules.lines);
    } catch (error) {
      assert.ok(error instanceof ChatStartError);
      return error.kind;
    }
    return "accepted";
  };
  assert.equal(kind(401, { error: "unauthorized" }), "unauthorized");
  assert.equal(kind(200, { error: "signin" }), "signin");
  assert.equal(kind(200, { error: "unavailable" }), "unavailable");
  assert.equal(kind(429, { message: "Too Many Requests" }), "status");
  assert.equal(kind(200, null), "status");
  assert.equal(kind(200, { data: { startChatResult: { ContactId: CONTACT } } }), "shape");
  assert.equal(kind(200, { data: { startChatResult: { ...answer.data.startChatResult, ContactId: "../x" } } }), "shape");
});

test("chatDetails shows the manifest's sign-in line", () => {
  assert.throws(() => chatDetails(200, { error: "signin" }, rules.lines), { message: rules.lines.signin });
});

test("visibleText strips the canvas's marks and hides flow lines", () => {
  assert.equal(visibleText(`Hi, I can help with HR.${END}`, rules), "Hi, I can help with HR.");
  assert.equal(visibleText(`Goodbye.${CLOSED}`, rules), "Goodbye.");
  assert.equal(visibleText(END, rules), null);
  assert.equal(visibleText(`${rules.escalationPrefix}: queue`, rules), null);
  assert.equal(visibleText(undefined, rules), null);
});

const item = (role, content, type = "MESSAGE") => ({ Type: type, ParticipantRole: role, Content: content });

test("greetingLines takes the canvas's lines before the employee's first message", () => {
  const transcript = [
    item("SYSTEM", "", "EVENT"),
    item("CUSTOM_BOT", `${rules.hiddenPrefix} flow started`),
    item("CUSTOM_BOT", "Hi, I'm the HR Assistant."),
    item("CUSTOM_BOT", `What can I help with?${END}`),
    item("CUSTOMER", "Change my address"),
    item("CUSTOM_BOT", "Sure."),
  ];
  assert.deepEqual(greetingLines(transcript, rules), ["Hi, I'm the HR Assistant.", "What can I help with?"]);
});

test("greetingLines is empty until the transcript has the greeting", () => {
  assert.deepEqual(greetingLines([], rules), []);
  assert.deepEqual(greetingLines(undefined, rules), []);
  assert.deepEqual(greetingLines([item("SYSTEM", "", "EVENT")], rules), []);
});

const user = (text, at) => ({ type: "user", receivedAt: at, payload: { type: "text", text } });
const bot = (text, at) => ({ type: "bot", receivedAt: at, payload: { messages: [{ text, choices: [] }] } });

test("turnTimes pairs each question with its first reply and skips the greeting", () => {
  const responses = [
    bot("Hi", 0),
    user("Change my address", 1_000),
    bot("To what?", 4_200),
    bot("I can also update your emergency contact.", 4_900),
    user("25 Ponce de Leon Ave", 10_000),
  ];
  assert.deepEqual(turnTimes(responses), [
    { askedAt: 1_000, text: "Change my address", firstReplyMs: 3_200 },
    { askedAt: 10_000, text: "25 Ponce de Leon Ave", firstReplyMs: null },
  ]);
});

test("hiddenLinesShown finds flow lines the widget rendered", () => {
  const responses = [bot("Hi", 0), bot(`${rules.errorPrefix}.`, 5), user("x", 6)];
  assert.deepEqual(hiddenLinesShown(responses, rules), [`${rules.errorPrefix}.`]);
});
