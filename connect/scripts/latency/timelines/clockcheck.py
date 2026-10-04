import json, sys, statistics as st
from collections import defaultdict
sys.path.insert(0, sys.argv[1]); import join
d=sys.argv[1]
recs=[r for r in json.load(open(f'{d}/raw/rt-app.json')) if r['runtime']=='hr_super_agent_tools']
sp=[s for s in json.load(open(f'{d}/raw/dt-spans.json')) if s['service.name'].startswith('hr_super_agent_tools') and s['span.name']=='POST /mcp']
for s in sp: s['s']=join.iso(s['start_time']); s['e']=join.iso(s['end_time'])
byt=defaultdict(list)
for s in sp: byt[s['trace.id']].append(s)
sess=defaultdict(list)
for r in recs: r['recv']=int(r['received_ns'])/1e6; sess[r['session_id']].append(r)
off=defaultdict(list); n=0
for sid,v in sess.items():
    v.sort(key=lambda r:r['recv'])
    if len(v)!=3: continue
    cand=sorted([s for s in byt.get(v[0]['trace_id'],[]) if abs(s['s']-v[0]['recv'])<5000], key=lambda s:s['s'])
    # pick the 3 spans closest in order: choose window of 3 consecutive minimizing spread vs recv
    best=None
    for i in range(len(cand)-2):
        w=cand[i:i+3]; err=sum(abs((w[k]['s']-w[0]['s'])-(v[k]['recv']-v[0]['recv'])) for k in range(3))
        if best is None or err<best[0]: best=(err,w)
    if not best: continue
    n+=1
    for k in range(3): off[k].append(round(best[1][k]['s']-v[k]['recv']))
    off['end'].append(round(best[1][2]['e']-v[2]['logged_ms']))
print(d, 'sessions', n)
for k,x in off.items(): print(' ', k, 'median', st.median(x), 'range', min(x), max(x))
