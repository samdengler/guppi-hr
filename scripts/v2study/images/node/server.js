// Probe server (Node) for the Runtime V2 cold start study: HTTP on 8080, same telemetry
// as the Python image. No outbound calls.
const http = require("http");
const fs = require("fs");
const os = require("os");
const crypto = require("crypto");

const T0_WALL = Date.now() / 1000;
const T0_MONO = Number(process.hrtime.bigint()) / 1e9;
const FIRST_RANDOM = Math.random();
const BOOT_ID = fs.readFileSync("/proc/sys/kernel/random/boot_id", "utf8").trim();
const START_UPTIME = parseFloat(fs.readFileSync("/proc/uptime", "utf8").split(" ")[0]);
let requests = 0;

function procstat() {
  const rest = fs.readFileSync("/proc/self/stat", "utf8").split(") ").pop().split(" ");
  const mem = {};
  for (const line of fs.readFileSync("/proc/meminfo", "utf8").split("\n")) {
    const [k, v] = line.split(":");
    if (v) mem[k] = parseInt(v.trim().split(" ")[0], 10);
  }
  return { minflt: +rest[7], majflt: +rest[9], rss_mb: Math.round((+rest[21] * 4096) / 1e5) / 10,
    mem_total_mb: Math.round(mem.MemTotal / 1024), mem_available_mb: Math.round(mem.MemAvailable / 1024) };
}

function probe(headers) {
  const reqWall = Date.now() / 1000;
  const reqMono = Number(process.hrtime.bigint()) / 1e9;
  const before = procstat();
  const workStart = process.hrtime.bigint();
  requests += 1;
  const payload = JSON.stringify({ n: requests, ts: reqWall }).repeat(50);
  const after = procstat();
  return {
    variant: process.env.VARIANT || "", mode: "http", language: "node", node: process.version,
    knobs: {},
    start: { wall: T0_WALL, mono: T0_MONO, uptime: START_UPTIME, boot_id: BOOT_ID, first_random: FIRST_RANDOM },
    request: {
      n: requests, wall: reqWall, mono: reqMono,
      uptime: parseFloat(fs.readFileSync("/proc/uptime", "utf8").split(" ")[0]),
      wall_since_start_s: Math.round((reqWall - T0_WALL) * 1000) / 1000,
      mono_since_start_s: Math.round((reqMono - T0_MONO) * 1000) / 1000,
      boot_id: fs.readFileSync("/proc/sys/kernel/random/boot_id", "utf8").trim(),
      kernel_uuid: fs.readFileSync("/proc/sys/kernel/random/uuid", "utf8").trim(),
      random: Math.random(), urandom: crypto.randomBytes(4).toString("hex"), uuid4: crypto.randomUUID(),
      hostname: os.hostname(), pid: process.pid, cpus: os.cpus().length, env_count: Object.keys(process.env).length,
      session_header: headers["x-amzn-bedrock-agentcore-runtime-session-id"] || null,
    },
    before, after, work: { json_len: payload.length },
    work_ms: Math.round(Number(process.hrtime.bigint() - workStart) / 1e4) / 100,
  };
}

http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/ping") {
    res.writeHead(200, { "content-type": "application/json" }); res.end('{"status":"Healthy"}'); return;
  }
  if (req.method === "POST" && req.url.startsWith("/invocations")) {
    let body = ""; req.on("data", (c) => (body += c)); req.on("end", () => {
      res.writeHead(200, { "content-type": "application/json" }); res.end(JSON.stringify(probe(req.headers)));
    }); return;
  }
  res.writeHead(404); res.end();
}).listen(8080, "0.0.0.0");
