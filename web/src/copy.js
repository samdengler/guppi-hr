// The page's privacy notice, in one place because two switches decide what it may claim.
// history would keep chats in browser storage; logging records threads in the conversation
// log bucket. Both are off until the feature behind them ships.

const KEYS = "Enter to send, Shift+Enter for a new line.";

export function noticeSentence(history, logging) {
  if (history && logging) return "Chats are saved on this device and logged for troubleshooting.";
  if (history) return "Chats are saved on this device only.";
  if (logging) return "Conversations are logged for troubleshooting.";
  return null;
}

export function hintText(history, logging) {
  return `${KEYS} ${noticeSentence(history, logging) ?? "Nothing is saved."}`;
}

export function emptyStateText(history, logging) {
  const sentence = noticeSentence(history, logging);
  return sentence ? `Ask anything. ${sentence}` : "Ask anything. This conversation is not saved.";
}

// The status line during a tool call: what is happening while it runs, and what happened
// once it ends. Gateway tool names carry the target prefix (docs___, hr___).
const TOOL_STATUS = [
  [/___Retrieve$|___AgenticRetrieveStream$/, "Searching the HR policies", "Searched the HR policies"],
  [/___propose_/, "Preparing the change", "Prepared the change"],
  [/___commit_change$/, "Saving the change", "Saved the change"],
  [/___open_ticket$/, "Opening a ticket", "Opened a ticket"],
  [/___list_pay_statements$/, "Looking up pay statements", "Looked up pay statements"],
  [/^hr___/, "Checking your HR records", "Checked your HR records"],
];

export function toolStatus(toolName) {
  for (const [pattern, running, done] of TOOL_STATUS) {
    if (pattern.test(toolName || "")) return { running: `${running}…`, done };
  }
  return { running: "Working…", done: "Done" };
}
