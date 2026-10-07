// The stand-in HR portal the widget sits on at /p/hr-widget/. Plain text only: the
// platform's plain-text rule holds for everything outside the widget (D62).

const TILES = [
  ["Profile", "Home address and emergency contact."],
  ["Pay", "Direct deposit and pay statements."],
  ["Time off", "Paid time off and how it accrues."],
  ["Travel", "Pass travel and buddy passes."],
];

function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

/**
 * Draws the portal into `surface`. Each of `suggestions` ({label, prompt}) becomes a
 * button that calls `ask(prompt)`, which opens the widget and sends the question.
 */
export function renderPortal(surface, { suggestions, ask }) {
  const root = el("div", "hrw-portal");
  root.append(
    el("h1", "hrw-title", "Employee HR portal"),
    el(
      "p",
      "hrw-lead",
      "A stand-in for an HR portal. The HR Assistant opens from the button in the lower right corner, or from a question below.",
    ),
  );
  const tiles = el("div", "hrw-tiles");
  for (const [title, text] of TILES) {
    const tile = el("section", "hrw-tile");
    tile.append(el("h2", "hrw-tile-title", title), el("p", "hrw-tile-text", text));
    tiles.append(tile);
  }
  root.append(tiles, el("h2", "hrw-section", "Ask the HR Assistant"));
  const asks = el("div", "hrw-asks");
  for (const { label, prompt } of suggestions) {
    const button = el("button", "hrw-ask", label);
    button.type = "button";
    button.title = prompt;
    button.addEventListener("click", () => ask(prompt));
    asks.append(button);
  }
  root.append(asks);
  surface.replaceChildren(root);
}
