import { readFileSync } from "node:fs";
const { records } = JSON.parse(readFileSync(process.argv[2], "utf8"));
const med = (xs) => { const s = xs.filter(x=>x!=null).sort((a,b)=>a-b); if(!s.length) return null; const p=(s.length-1)/2; return (s[Math.floor(p)]+s[Math.ceil(p)])/2; };
const ms = (t) => { const m=/([\d.]+)\s*(ms|s)/.exec(t||""); return m? (m[2]==="s"?+m[1]*1000:+m[1]) : null; };
for (const s of ["Update my information","Change my address","PTO policy","Buddy passes"]) {
  const A = records.filter(r=>r.arm==="A"&&r.suggestion===s), B = records.filter(r=>r.arm==="B"&&r.suggestion===s);
  const conn = A.map(r=>{const n=(r.debug.notes||[]).find(x=>x.startsWith("Connect time")); return n? +/first reply (\d+)/.exec(n)[1]:null;});
  const send = A.map(r=>ms((r.debug.steps||[]).find(x=>x.name==="SendMessage")?.dur));
  const wait = A.map(r=>ms((r.debug.steps||[]).find(x=>x.name==="waiting for the chat start")?.dur));
  const ends = A.map(r=>(r.debug.steps||[]).find(x=>/end mark|quiet|turn limit|closing/.test(x.name))?.name);
  const bsteps = B[0]?.debug.steps.map(x=>x.name).slice(0,12);
  const bfirstDelta = B.map(r=>ms((r.debug.steps||[]).find(x=>/first delta|first reply/i.test(x.name))?.start));
  const bsend = B.map(r=>ms((r.debug.steps||[]).find(x=>x.name==="SendMessage")?.start));
  console.log(s, {connectFirstMed: med(conn), sendMed: med(send), waitMed: med(wait), ends:[...new Set(ends)], bridgeSendStartMed: med(bsend), bridgeFirstMed: med(bfirstDelta), loadA: med(A.map(r=>r.loadMs)), loadB: med(B.map(r=>r.loadMs))});
  if (process.argv[3]) console.log("  B steps:", bsteps);
}
