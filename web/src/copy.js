// The wording the HR extension (ext.js) puts on the platform page: the status line for
// each tool call and each delegation, and the label above a reply. Pure functions, so
// web/test/copy.test.js covers them without a DOM.

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

// The product name, in one place (D15). web/manifest.json's label carries the same text,
// and web/test/copy.test.js holds them to it.
export const BRAND = "HR Assistant";

// The sub-agents the orchestrator can hand a turn to, by the step name it sends (D4).
const AGENT_NAMES = { profile: "Profile", pay: "Pay", travel: "Travel" };

export function agentName(stepName) {
  return AGENT_NAMES[stepName] || null;
}

// The status line while the orchestrator waits on a sub-agent, and once it has answered.
export function stepStatus(stepName) {
  const name = agentName(stepName);
  if (!name) return { running: "Working…", done: "Done" };
  return { running: `Asking the ${name} agent…`, done: `${name} agent answered` };
}

// The label above a reply: the brand, tagged with the agent that answered it.
export function replyLabel(stepName) {
  const name = agentName(stepName);
  return name ? `${BRAND} · ${name}` : BRAND;
}
