import json, re, html

import os
S = os.path.join(os.environ.get("LATENCY_WORK", os.getcwd()), "")  # the working folder with the inputs
crit = open(S + "hr-latency-critique.html").read()
head = crit[: crit.index("</style>")]
head = head.replace("<title>HR Assistant Latency Critique</title>", "<title>HR Latency Timelines</title>")

body = open(S + "lt-body.txt").read()
meta, frag = body.split("\n@@\n", 1)
title, *toc = meta.split("\n")
toc = [t.split("\t") for t in toc]
frag = frag.replace(
    "<p>The per-path step tables are in <code>latency-timelines-tables.md</code>, and the waterfall data in <code>latency-timelines.json</code>.</p>",
    "<p>The report, its per-path step tables and the waterfall data are in guppi-hr under <code>docs/latency-timelines-2026-10-04.md</code>.</p>",
)

d = json.load(open(S + "latency-timelines.json"))
keep = ["name", "owner", "start_ms", "end_ms", "p10_ms", "p90_ms", "dur_ms", "dur_p10_ms", "dur_p90_ms", "dur_min_ms", "dur_max_ms", "level", "container", "parallel_group", "n"]
labels = {
    "clarify": "Clarify", "policy-first": "Policy, first", "policy-follow": "Policy, follow-up",
    "profile-first": "Profile, first", "profile-follow": "Profile, follow-up", "travel-first": "Travel, first",
    "travel-follow": "Travel, follow-up", "pay-first": "Pay, first", "pay-follow": "Pay, follow-up",
    "chat-start": "Chat start", "chat-start-cold": "Chat start, cold",
}
paths = []
for k, p in d["paths"].items():
    s = p["summary"]
    paths.append({
        "key": k, "label": labels[k], "title": p["title"],
        "clock": "from navigation" if k.startswith("chat-start") else "from the click",
        "n": s.get("turns") or s.get("page_loads"),
        "fw": s.get("first_words_ms"), "done": (s.get("done_ms") or {}).get("median"),
        "owners": s.get("owner_ms_median"),
        "steps": [{x: st.get(x) for x in keep} for st in p["steps"]],
    })
data = json.dumps(paths, separators=(",", ":")).replace("</", "<\\/")

OWNERS = ["connect", "designer", "model", "gateway", "runtime", "identity", "ours", "internet"]
OWN_LABEL = {
    "connect": "Connect", "designer": "Connect designer", "model": "Models", "gateway": "AgentCore Gateway",
    "runtime": "AgentCore Runtime", "identity": "Identity and Okta", "ours": "Our code", "internet": "Network and front door",
    "unattributed": "Unattributed",
}

# Stacked owner bars, server rendered so they show without script.
turns = [p for p in paths if p["owners"]]
scale = 10000
rows = []
for p in turns:
    fw = p["fw"]["median"]
    segs = "".join(
        f'<span class="seg o-{o}" style="width:{p["owners"][o] / scale * 100:.2f}%" title="{OWN_LABEL[o]}: {p["owners"][o]} ms"></span>'
        for o in OWNERS + ["unattributed"] if p["owners"].get(o)
    )
    whisk = f'<span class="whisk" style="left:{p["fw"]["p10"] / scale * 100:.2f}%;width:{(p["fw"]["p90"] - p["fw"]["p10"]) / scale * 100:.2f}%"></span>'
    parts = ", ".join(f'{OWN_LABEL[o]} {p["owners"][o] / 1000:.2f} s' for o in OWNERS if p["owners"].get(o))
    rows.append(
        f'<div class="brow"><div class="bname">{html.escape(p["label"])}<span class="bval">{fw / 1000:.2f} s</span></div>'
        f'<div class="track" role="img" aria-label="{html.escape(p["label"])}: first words {fw / 1000:.2f} s; {parts}">{segs}{whisk}</div></div>'
    )
axis = "".join(f'<span style="left:{i / 10 * 100:.2f}%">{i} s</span>' for i in range(0, 11, 2))
legend = "".join(f'<span><i class="sw o-{o}"></i>{OWN_LABEL[o]}</span>' for o in OWNERS)
owner_fig = (
    '<figure class="budget" aria-labelledby="own-cap"><figcaption id="own-cap">Each path\'s median turn split by owner, '
    "measured from the click to first words. The thin line under each bar is the p10 to p90 range of first words. Each owner's "
    "share is its own median across the path's turns, so a stack can differ from the median first words by up to 0.13 s.</figcaption>"
    f'<div class="axis" aria-hidden="true">{axis}</div>' + "\n".join(rows) + f'<div class="legend">{legend}</div></figure>'
)
k = frag.index("</p>") + 4
frag = frag[:k] + '<p>The ids behind every number (contacts, request ids, trace and span ids, runtime sessions, the log stream of each microVM, ARNs) are on the <a href="evidence.html">evidence page</a>, and every step of every turn in <a href="evidence.json">evidence.json</a>.</p>' + frag[k:]
i = frag.index("</table></div>") + len("</table></div>")
frag = frag[:i] + owner_fig + frag[i:]

wf_section = """<h2 id="waterfalls">Waterfalls</h2>
<p>One path at a time. Each row is a step at its median start and end; nested rows sit inside the outlined row above them, and rows marked with a dot run at the same time as their neighbours with the same mark. The thin line past a bar spans the p10 to p90 of that step's end. The dashed line is the median first words. Select a row for its numbers. The turn paths are measured from the click, the chat start from the page's navigation.</p>
<div class="wf" id="wf">
<div class="wf-tabs" role="tablist" aria-label="Path"></div>
<p class="wf-head" id="wf-head"></p>
<div class="wf-legend legend">LEGEND</div>
<div class="wf-axis" aria-hidden="true"></div>
<div class="wf-rows" role="list"></div>
</div>
""".replace("LEGEND", legend)
j = frag.index('<h2 id="how-it-was-measured">')
frag = frag[:j] + wf_section + frag[j:]
toc.insert(1, ["waterfalls", "Waterfalls"])

css = """
.o-connect { background: var(--c-connect); } .o-designer { background: var(--c-designer); } .o-model { background: var(--c-model); }
.o-gateway { background: var(--c-gateway); } .o-runtime { background: var(--c-runtime); } .o-identity { background: var(--c-identity); }
.o-ours { background: var(--c-ours); } .o-internet { background: var(--c-internet); }
.o-unattributed { background: repeating-linear-gradient(45deg, var(--muted) 0 2px, transparent 2px 5px); }
:root { --c-connect: #2f6fb3; --c-designer: #82acd9; --c-model: #2e8b57; --c-gateway: #8e5bb5; --c-runtime: #c23b4e;
  --c-identity: #1f9a9a; --c-ours: #e07b1e; --c-internet: #9aa4b1; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --c-connect: #5b9be0; --c-designer: #a9c9ec; --c-model: #4fbf80;
  --c-gateway: #b48ad8; --c-runtime: #e5677a; --c-identity: #42c4c4; --c-ours: #f0a050; --c-internet: #7d8794; } }
:root[data-theme="dark"] { --c-connect: #5b9be0; --c-designer: #a9c9ec; --c-model: #4fbf80;
  --c-gateway: #b48ad8; --c-runtime: #e5677a; --c-identity: #42c4c4; --c-ours: #f0a050; --c-internet: #7d8794; }
.track .seg:first-child { border-radius: 3px 0 0 3px; }
.whisk { position: absolute; bottom: -6px; height: 2px; background: var(--fg); opacity: .55; }
.brow .track { margin-bottom: 6px; }
.wf { margin: 1rem 0 .4rem; padding: 1rem 1.1rem 1.1rem; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; display: grid; gap: .7rem; }
.wf-tabs { display: flex; flex-wrap: wrap; gap: .35rem; }
.wf-tabs button { font: 500 .82rem var(--sans); color: var(--fg); background: var(--code-bg); border: 1px solid var(--line); border-radius: 999px; padding: .3rem .75rem; cursor: pointer; }
.wf-tabs button[aria-selected="true"] { background: var(--accent); border-color: var(--accent); color: var(--surface); }
.wf-tabs button:focus-visible, .wf-row:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.wf-head { margin: 0; font-size: .92rem; color: var(--muted); max-width: none; }
.wf-head strong { color: var(--fg); }
.wf-axis, .wf-row { display: grid; grid-template-columns: minmax(0, 23rem) minmax(0, 1fr); gap: .8rem; align-items: center; }
.wf-axis .ticks { position: relative; height: 1rem; font: .7rem var(--mono); color: var(--muted); }
.wf-axis .ticks span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
.wf-axis .ticks span:first-child { transform: none; }
.axis span { white-space: nowrap; }
.wf-rows { display: grid; gap: 1px; }
.wf-row { padding: .18rem .3rem; border-radius: 4px; cursor: pointer; }
.wf-row:hover, .wf-row.open { background: var(--code-bg); }
.wf-name { display: flex; gap: .5rem; justify-content: space-between; font-size: .8rem; line-height: 1.3; min-width: 0; }
.wf-name .nm { overflow-wrap: anywhere; }
.wf-name .ms { font: .76rem var(--mono); color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
.wf-row.l0 .nm { font-weight: 600; }
.wf-row .par::before { content: "\\25CF"; color: var(--accent); margin-right: .3rem; font-size: .6rem; vertical-align: .1rem; }
.wf-bar { position: relative; height: 14px; }
.wf-bar .grid { position: absolute; top: -3px; bottom: -3px; width: 1px; background: var(--line); }
.wf-bar .b { position: absolute; top: 2px; height: 10px; min-width: 2px; border-radius: 2px; }
.wf-bar .b.cont { background: transparent !important; border: 1.5px solid; top: 1px; height: 12px; }
.wf-bar .w { position: absolute; top: 6px; height: 2px; background: var(--fg); opacity: .4; }
.wf-bar .fw { position: absolute; top: -3px; bottom: -3px; width: 0; border-left: 1.5px dashed var(--fg); opacity: .45; }
.wf-detail { grid-column: 1 / -1; font: .76rem/1.5 var(--mono); color: var(--muted); padding: .2rem 0 .3rem; }
@media (max-width: 640px) {
  .wf { padding: .8rem; }
  .wf-axis, .wf-row { grid-template-columns: minmax(0, 1fr); gap: .15rem; }
  .wf-axis > div:first-child { display: none; }
  .wf-axis .ticks span.odd { display: none; }
}
"""

js = """
<script>
const PATHS = DATA;
const OWN = OWNLABEL;
const root = document.getElementById('wf');
const tabs = root.querySelector('.wf-tabs'), head = document.getElementById('wf-head');
const axis = root.querySelector('.wf-axis'), rowsEl = root.querySelector('.wf-rows');
const fmt = ms => ms == null ? '' : (ms >= 1000 ? (ms / 1000).toFixed(2) + ' s' : Math.round(ms) + ' ms');
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function show(key) {
  const p = PATHS.find(x => x.key === key);
  tabs.querySelectorAll('button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.key === key)));
  try { localStorage.setItem('wf-path', key); } catch (e) {}
  head.textContent = '';
  head.append(el('strong', null, p.title));
  let line = ' · ' + p.n + (p.key.startsWith('chat-start') ? (p.n === 1 ? ' page load' : ' page loads') : ' turns');
  if (p.fw) line += ' · first words ' + fmt(p.fw.median) + ' (p10 ' + fmt(p.fw.p10) + ', p90 ' + fmt(p.fw.p90) + ')';
  if (p.done && p.fw && p.done - p.fw.median > 100) line += ' · done ' + fmt(p.done);
  line += ' · times ' + p.clock;
  head.append(document.createTextNode(line));
  const maxEnd = Math.max(...p.steps.map(s => Math.max(s.end_ms, s.p90_ms || 0)));
  const step = maxEnd > 6000 ? 1000 : 500;
  const total = Math.ceil(maxEnd / step) * step;
  const pct = v => (Math.max(0, Math.min(v, total)) / total * 100) + '%';
  axis.textContent = '';
  axis.append(el('div'));
  const ticks = el('div', 'ticks');
  for (let t = 0; t <= total; t += step) { if (t % 1000) continue; const s = el('span', (t / 1000) % 2 ? 'odd' : null, (t / 1000) + ' s'); s.style.left = pct(t); if (t === total) s.style.transform = 'translateX(-100%)'; ticks.append(s); }
  axis.append(ticks);
  rowsEl.textContent = '';
  p.steps.forEach(s => {
    const r = el('div', 'wf-row l' + s.level); r.setAttribute('role', 'listitem'); r.tabIndex = 0;
    const nm = el('div', 'wf-name'); nm.style.paddingLeft = (s.level * 0.9) + 'rem';
    const n = el('span', 'nm' + (s.parallel_group ? ' par' : ''), s.name);
    nm.append(n, el('span', 'ms', fmt(s.dur_ms)));
    const bar = el('div', 'wf-bar');
    for (let t = step; t < total; t += step) { const g = el('span', 'grid'); g.style.left = pct(t); bar.append(g); }
    if (s.p10_ms != null && s.p90_ms != null && s.p90_ms > s.p10_ms) { const w = el('span', 'w'); w.style.left = pct(s.p10_ms); w.style.width = 'calc(' + pct(s.p90_ms) + ' - ' + pct(s.p10_ms) + ')'; bar.append(w); }
    const b = el('span', 'b o-' + s.owner + (s.container ? ' cont' : ''));
    b.style.left = pct(s.start_ms); b.style.width = 'calc(' + pct(s.end_ms) + ' - ' + pct(s.start_ms) + ')';
    if (s.container) b.style.borderColor = 'var(--c-' + s.owner + ')';
    bar.append(b);
    if (p.fw) { const f = el('span', 'fw'); f.style.left = pct(p.fw.median); bar.append(f); }
    r.setAttribute('aria-label', s.name + ', ' + (OWN[s.owner] || s.owner) + ', ' + fmt(s.dur_ms) + ' from ' + fmt(s.start_ms) + ' to ' + fmt(s.end_ms));
    r.append(nm, bar);
    const toggle = () => {
      const open = r.classList.toggle('open');
      const old = r.querySelector('.wf-detail'); if (old) old.remove();
      if (!open) return;
      let t = (OWN[s.owner] || s.owner) + ' · start ' + fmt(s.start_ms) + ' · end ' + fmt(s.end_ms);
      if (s.p10_ms != null) t += ' (p10 ' + fmt(s.p10_ms) + ', p90 ' + fmt(s.p90_ms) + ')';
      t += ' · duration ' + fmt(s.dur_ms);
      if (s.dur_p10_ms != null) t += ' (p10 ' + fmt(s.dur_p10_ms) + ', p90 ' + fmt(s.dur_p90_ms) + ', range ' + fmt(s.dur_min_ms) + ' to ' + fmt(s.dur_max_ms) + ')';
      if (s.parallel_group) t += ' · runs alongside: ' + s.parallel_group;
      t += ' · n ' + s.n;
      r.append(el('div', 'wf-detail', t));
    };
    r.addEventListener('click', toggle);
    r.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    rowsEl.append(r);
  });
}
PATHS.forEach(p => { const b = el('button', null, p.label); b.type = 'button'; b.dataset.key = p.key; b.setAttribute('role', 'tab'); b.addEventListener('click', () => show(p.key)); tabs.append(b); });
let first = 'profile-first';
try { const k = localStorage.getItem('wf-path'); if (k && PATHS.some(p => p.key === k)) first = k; } catch (e) {}
show(first);
</script>
""".replace("DATA", data).replace("OWNLABEL", json.dumps(OWN_LABEL))

toc_html = '<nav class="toc" aria-label="Contents"><span class="toc-label">Contents</span><ol>' + "".join(
    f'<li><a href="#{a}">{html.escape(b)}</a></li>' for a, b in toc) + "</ol></nav>"
page = (head + css + "</style>\n<main>\n"
        '<div class="eyebrow">guppi-hr · /p/hr/ · 4 October 2026</div>\n'
        "<h1>HR assistant latency timelines on /p/hr/ after D57</h1>\n" + toc_html + "\n" + frag + "\n</main>\n" + js)
assert "—" not in page and "–" not in page, "dash found"
open(S + "latency-timelines.html", "w").write(page)
print(len(page))
