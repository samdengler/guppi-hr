// Summary of a bench run: per suggestion per arm, median, p90 (linear interpolation),
// min and max of first words and done, in seconds; then the pass mark.
//   node stats.mjs results/main.json
import { readFileSync } from "node:fs";

const { records } = JSON.parse(readFileSync(process.argv[2], "utf8"));
const SUGGESTIONS = ["Update my information", "Change my address", "PTO policy", "Buddy passes"];
const quantile = (xs, q) => {
  const s = [...xs].sort((a, b) => a - b);
  const pos = (s.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return s[lo] + (s[hi] - s[lo]) * (pos - lo);
};
const f = (ms) => (ms / 1000).toFixed(2);
const stats = (xs) => ({ n: xs.length, median: quantile(xs, 0.5), p90: quantile(xs, 0.9), min: Math.min(...xs), max: Math.max(...xs) });
const out = {};
console.log("suggestion | arm | n | first median | p90 | min | max | done median | p90 | min | max | transports");
for (const s of SUGGESTIONS) {
  out[s] = {};
  for (const arm of ["A", "B"]) {
    const rs = records.filter((r) => r.suggestion === s && r.arm === arm && !r.error && r.firstMs !== null);
    const first = stats(rs.map((r) => r.firstMs));
    const done = stats(rs.map((r) => r.doneMs));
    const transports = [...new Set(rs.map((r) => r.transport))].join(",");
    out[s][arm] = { first, done };
    console.log(
      `${s} | ${arm} | ${first.n} | ${f(first.median)} | ${f(first.p90)} | ${f(first.min)} | ${f(first.max)} | ${f(done.median)} | ${f(done.p90)} | ${f(done.min)} | ${f(done.max)} | ${transports}`,
    );
  }
}
const errors = records.filter((r) => r.error || r.firstMs === null);
console.log(`errors or no first text: ${errors.length}`, errors.map((r) => `${r.index}${r.arm} ${r.error}`).join("; "));
console.log("\npass mark (first words medians, B minus A):");
let all = true;
for (const s of SUGGESTIONS) {
  const d = out[s].B.first.median - out[s].A.first.median;
  const ok = d >= 250;
  all &&= ok;
  console.log(`${s}: A ${f(out[s].A.first.median)} B ${f(out[s].B.first.median)} saving ${f(d)} s ${ok ? "pass" : "FAIL"}${d < 0 ? " (slower)" : ""}`);
}
const addr = out["Change my address"];
console.log(`no suggestion slower: ${SUGGESTIONS.every((s) => out[s].A.first.median <= out[s].B.first.median) ? "pass" : "FAIL"}`);
console.log(`Change my address at or under the bridge's median: ${addr.A.first.median <= addr.B.first.median ? "pass" : "FAIL"}`);
console.log(`every suggestion at least 0.25 s lower: ${all ? "pass" : "FAIL"}`);
// Extra evidence per arm: CSP violations, SendEvent calls, report statuses, chat-start waits.
for (const arm of ["A", "B"]) {
  const rs = records.filter((r) => r.arm === arm);
  const csp = rs.reduce((n, r) => n + (r.csp?.length || 0), 0);
  const sendEvent = rs.reduce((n, r) => n + (r.net || []).filter((x) => x.kind === "request" && x.path.includes("/participant/event")).length, 0);
  const reports = rs.flatMap((r) => (r.net || []).filter((x) => x.path.endsWith("/chat/report") && x.kind !== "request").map((x) => x.status ?? x.failure));
  const starts = rs.reduce((n, r) => n + (r.net || []).filter((x) => x.kind === "request" && x.path.endsWith("/chat/start")).length, 0);
  const invocations = rs.reduce((n, r) => n + (r.net || []).filter((x) => x.kind === "request" && x.path.endsWith("/invocations")).length, 0);
  const participant = rs.reduce((n, r) => n + (r.net || []).filter((x) => x.kind === "request" && x.host.startsWith("participant")).length, 0);
  const waited = rs.filter((r) => (r.debug?.notes || []).some((n) => n.includes("waited for the chat start"))).length;
  const reportCounts = reports.reduce((m, s) => ((m[s] = (m[s] || 0) + 1), m), {});
  console.log(`${arm}: presses ${rs.length}, csp ${csp}, SendEvent ${sendEvent}, reports ${JSON.stringify(reportCounts)}, chat/start ${starts}, invocations ${invocations}, participant calls ${participant}, waited for start ${waited}`);
}
