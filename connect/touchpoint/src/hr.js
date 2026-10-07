// The parts of the Touchpoint experiment that do not need a browser: reading the chat
// start's answer, choosing the greeting to replay from a Connect transcript, and timing
// each question to its first reply. The rules (marks, the hidden prefix) come from the
// /p/hr/ manifest, so this page and the platform page read the canvas the same way.

/** A failed chat start, with the manifest line the page shows for it. */
export class ChatStartError extends Error {
  constructor(kind, message) {
    super(message);
    this.name = "ChatStartError";
    this.kind = kind;
  }
}

const ID = /^[0-9a-f-]{36}$/;

/**
 * Touchpoint's chat details from the chat start's answer (D57): 200
 * `{data: {startChatResult}, region, startedAt, expiresAt, restarted, timing}`, 200
 * `{error: "signin" | "unavailable"}`, or 401 `{error: "unauthorized"}`.
 */
export function chatDetails(status, body, lines = {}) {
  if (status === 401) {
    throw new ChatStartError("unauthorized", lines.signin ?? "The sign-in was refused.");
  }
  if (status !== 200 || body == null || typeof body !== "object") {
    throw new ChatStartError("status", `The chat start answered ${status}.`);
  }
  if (body.error === "signin") {
    throw new ChatStartError("signin", lines.signin ?? "HR could not confirm the sign-in.");
  }
  if (body.error) {
    throw new ChatStartError("unavailable", `The chat start answered "${body.error}".`);
  }
  const result = body.data?.startChatResult ?? {};
  const details = {
    contactId: result.ContactId,
    participantId: result.ParticipantId,
    participantToken: result.ParticipantToken,
  };
  if (!ID.test(details.contactId ?? "") || !ID.test(details.participantId ?? "") || !details.participantToken) {
    throw new ChatStartError("shape", "The chat start's answer has no participant credentials.");
  }
  return {
    details,
    region: body.region,
    expiresAt: body.expiresAt,
    restarted: body.restarted === true,
    functionMs: typeof body.timing?.total_ms === "number" ? body.timing.total_ms : undefined,
  };
}

/** A canvas line with its end or closed mark removed, or null for a hidden flow line. */
export function visibleText(content, rules) {
  if (typeof content !== "string") return null;
  if (content.startsWith(rules.hiddenPrefix)) return null;
  let text = content;
  while (text.endsWith(rules.endMark) || text.endsWith(rules.closedMark)) text = text.slice(0, -1);
  text = text.trim();
  return text === "" ? null : text;
}

/**
 * The greeting the chat start already received on its own socket (D57, E4), from the
 * transcript the widget's session can read: every canvas message before the customer's
 * first one, hidden flow lines left out, marks stripped.
 */
export function greetingLines(transcript, rules) {
  const lines = [];
  for (const item of transcript ?? []) {
    if (item?.Type !== "MESSAGE") continue;
    if (item.ParticipantRole === "CUSTOMER") break;
    const text = visibleText(item.Content, rules);
    if (text != null) lines.push(text);
  }
  return lines;
}

/**
 * The greeting lines the widget does not yet show for this contact. Only bot responses
 * tagged with the contact's id count, so a restarted chat with the same greeting text
 * still gets its greeting.
 */
export function greetingToAdd(lines, responses, contactId) {
  const shown = new Set(
    (responses ?? [])
      .filter((r) => r?.type === "bot" && r.payload?.conversationId === contactId)
      .flatMap((r) => (r.payload?.messages ?? []).map((m) => m.text)),
  );
  return lines.filter((line) => !shown.has(line));
}

/**
 * Pairs each question with its first reply in Touchpoint's response list (`type` "user"
 * and "bot", each with `receivedAt` in ms). A bot response with no question before it
 * (the replayed greeting) is not a reply.
 */
export function turnTimes(responses) {
  const turns = [];
  let open = null;
  for (const response of responses ?? []) {
    if (response?.type === "user") {
      open = { askedAt: response.receivedAt, text: questionText(response), firstReplyMs: null };
      turns.push(open);
    } else if (response?.type === "bot" && open != null && open.firstReplyMs == null) {
      open.firstReplyMs = response.receivedAt - open.askedAt;
      open = null;
    }
  }
  return turns;
}

function questionText(response) {
  const payload = response.payload ?? {};
  if (payload.type === "text") return payload.text ?? "";
  return payload.type ?? "";
}

/** Bot texts in the response list that a /p/hr/ page would have hidden. */
export function hiddenLinesShown(responses, rules) {
  const shown = [];
  for (const response of responses ?? []) {
    if (response?.type !== "bot") continue;
    for (const message of response.payload?.messages ?? []) {
      if (typeof message?.text === "string" && message.text.startsWith(rules.hiddenPrefix)) shown.push(message.text);
    }
  }
  return shown;
}
