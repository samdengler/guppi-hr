"""Dynatrace spans of the HR runtimes for a window, in chunks small enough that the MCP
server's record cap (about 100) never truncates one."""
import json, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
HERE = Path(__file__).parent

def q(a, b):
    f = lambda t: t.isoformat().replace("+00:00", "Z")
    query = (f'fetch spans, from: "{f(a)}", to: "{f(b)}" | filter startsWith(service.name, "hr_super_agent") '
             '| filter not startsWith(span.name, "a2a.") '
             '| filter not (span.name == "POST /mcp" and http.url == "http://localhost:8000/mcp") '
             '| fieldsRemove system_prompt, span.events | limit 1000')
    out = subprocess.run([sys.executable, str(HERE / "dql.py"), query], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)

def grab(a, b, depth=0):
    rows = q(a, b)
    if len(rows) >= 95 and (b - a) > timedelta(seconds=2):
        m = a + (b - a) / 2
        return grab(a, m, depth + 1) + grab(m, b, depth + 1)
    return rows

lo = datetime.fromisoformat(sys.argv[1].replace("Z", "+00:00"))
hi = datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
spans, t = [], lo
while t < hi:
    u = min(t + timedelta(seconds=30), hi)
    spans.extend(grab(t, u))
    t = u
seen, out = set(), []
for s in spans:
    k = (s["trace.id"], s["span.id"])
    if k not in seen:
        seen.add(k); out.append(s)
(HERE / "raw" / "dt-spans.json").write_text(json.dumps(out))
print(len(out))
