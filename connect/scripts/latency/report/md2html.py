import html, re, sys
src = open(sys.argv[1]).read()
for a, b in [("the canvas's greeting", "the designer's greeting"), ("leaves the canvas out of the turn", "leaves the Connect designer out of the turn"),
             ("pass through the canvas (D39)", "pass through the Connect designer (D39)"), ("the canvas", "the Connect designer")]:
    src = src.replace(a, b)
def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return t
lines = src.splitlines(); out = []; i = 0; title = ""
def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
toc = []
while i < len(lines):
    l = lines[i]
    if l.startswith("```"):
        i += 1; buf = []
        while i < len(lines) and not lines[i].startswith("```"):
            buf.append(html.escape(lines[i], quote=False)); i += 1
        i += 1
        out.append("<pre><code>" + "\n".join(buf) + "</code></pre>"); continue
    if l.startswith("# "):
        title = l[2:]; i += 1; continue
    if l.startswith("## "):
        h = l[3:]; toc.append((slug(h), h)); out.append(f'<h2 id="{slug(h)}">{inline(h)}</h2>'); i += 1; continue
    if l.startswith("### "):
        out.append(f"<h3>{inline(l[4:])}</h3>"); i += 1; continue
    if l.startswith("| "):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
        head, body = rows[0], rows[2:]
        t = ['<div class="table-wrap"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"]
        for r in body:
            t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
        out.append("".join(t) + "</tbody></table></div>"); continue
    if re.match(r"^(- |\d+\. )", l):
        ordered = bool(re.match(r"^\d+\. ", l)); items = []
        while i < len(lines) and (re.match(r"^(- |\d+\. )", lines[i]) or (lines[i].startswith("  ") and items)):
            if re.match(r"^(- |\d+\. )", lines[i]): items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
            else: items[-1] += " " + lines[i].strip()
            i += 1
        tag = "ol" if ordered else "ul"
        out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>"); continue
    if not l.strip():
        i += 1; continue
    para = []
    while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||- |\d+\. |```)", lines[i]):
        para.append(lines[i].strip()); i += 1
    out.append(f"<p>{inline(' '.join(para))}</p>")
open(sys.argv[2], "w").write(title + "\n" + "\n".join(f"{a}\t{b}" for a, b in toc) + "\n@@\n" + "\n".join(out))
