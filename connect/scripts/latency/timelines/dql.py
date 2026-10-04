"""Runs a DQL query through the Dynatrace remote MCP server; prints the records as JSON.
The platform token comes from DT_PLATFORM_TOKEN and is never printed."""
import json, os, sys, urllib.request

URL = "https://zfr04910.apps.dynatrace.com/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp"
HDR = {"Authorization": f"Bearer {os.environ['DT_PLATFORM_TOKEN']}", "Content-Type": "application/json",
       "Accept": "application/json, text/event-stream"}

def post(body, session=None):
    h = dict(HDR)
    if session: h["mcp-session-id"] = session
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        sid = r.headers.get("mcp-session-id")
        raw = r.read().decode()
    if raw.lstrip().startswith("event:") or "data:" in raw[:20]:
        datas = [l[5:].strip() for l in raw.splitlines() if l.startswith("data:")]
        raw = datas[-1] if datas else "{}"
    return sid, (json.loads(raw) if raw.strip() else {})

def query(q):
    sid, _ = post({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "lt", "version": "0"}}})
    try: post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    except Exception: pass
    _, res = post({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "execute-dql", "arguments": {"dqlQueryString": q, "includeTypes": False}}}, sid)
    if "error" in res: raise SystemExit(json.dumps(res["error"]))
    content = res["result"]["content"]
    text = "".join(c.get("text", "") for c in content)
    marker = "Query result records:"
    if marker in text:
        return {"records": json.loads(text.split(marker, 1)[1])}
    try:
        return json.loads(text)
    except ValueError:
        raise SystemExit(text[:2000])

if __name__ == "__main__":
    q = sys.stdin.read() if len(sys.argv) < 2 else sys.argv[1]
    out = query(q)
    print(json.dumps(out.get("records", out)))
