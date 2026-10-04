import html
import os
S = os.path.join(os.environ.get("LATENCY_WORK", os.getcwd()), "")  # the working folder with the inputs
crit = open(S + "hr-latency-critique.html").read()
head = crit[: crit.index("</style>")].replace("<title>HR Assistant Latency Critique</title>", "<title>HR Latency Evidence</title>")
meta, frag = open(S + "ev-body.txt").read().split("\n@@\n", 1)
title, *toc = meta.split("\n")
toc = [t.split("\t") for t in toc]
css = """
main { max-width: 110rem; }
p, li { max-width: 80ch; }
th, td { min-width: 4.5rem; padding: .4rem .55rem; }
table { font-size: .8rem; }
td code { font-size: .74rem; background: none; padding: 0; }
pre { background: var(--code-bg); border: 1px solid var(--line); border-radius: 6px; padding: .8rem 1rem; overflow-x: auto; font: .82rem/1.5 var(--mono); }
pre code { background: none; padding: 0; }
.back { font-size: .9rem; }
"""
toc_html = '<nav class="toc" aria-label="Contents"><span class="toc-label">Contents</span><ol>' + "".join(f'<li><a href="#{a}">{html.escape(b)}</a></li>' for a, b in toc) + "</ol></nav>"
page = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        + head + css + "</style></head><body>\n<main>\n"
        '<div class="eyebrow">guppi-hr · /p/hr/ · 4 October 2026</div>\n'
        "<h1>" + html.escape(title) + "</h1>\n"
        '<p class="back"><a href="./">Back to the latency timelines</a> · <a href="evidence.json">evidence.json</a> (every step of every turn, 350 KB)</p>\n'
        + toc_html + "\n" + frag + "\n</main></body></html>")
assert "—" not in page and "–" not in page
open(S + "evidence.html", "w").write(page)
print(len(page))
