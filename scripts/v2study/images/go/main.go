// Probe server (Go) for the Runtime V2 cold start study: HTTP on 8080, same telemetry as
// the Python image. No outbound calls.
package main

import (
	crand "crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	rand2 "math/rand/v2"
	mrand "math/rand"
	"net/http"
	"os"
	"runtime"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
)

var (
	t0Wall      = float64(time.Now().UnixNano()) / 1e9
	t0Mono      = time.Now() // monotonic reading embedded
	firstRandom = mrand.Float64()
	bootID      = readTrim("/proc/sys/kernel/random/boot_id")
	startUptime = uptime()
	requests    atomic.Int64
	variant     = os.Getenv("VARIANT")
)

func readTrim(p string) string { b, _ := os.ReadFile(p); return strings.TrimSpace(string(b)) }
func uptime() float64 {
	f, _ := strconv.ParseFloat(strings.Fields(readTrim("/proc/uptime"))[0], 64)
	return f
}
func procstat() map[string]any {
	s := readTrim("/proc/self/stat")
	rest := strings.Fields(s[strings.LastIndex(s, ") ")+2:])
	mem := map[string]int{}
	for _, line := range strings.Split(readTrim("/proc/meminfo"), "\n") {
		kv := strings.SplitN(line, ":", 2)
		if len(kv) == 2 {
			v, _ := strconv.Atoi(strings.Fields(kv[1])[0])
			mem[kv[0]] = v
		}
	}
	minflt, _ := strconv.Atoi(rest[7])
	majflt, _ := strconv.Atoi(rest[9])
	rss, _ := strconv.Atoi(rest[21])
	return map[string]any{"minflt": minflt, "majflt": majflt, "rss_mb": float64(rss*4096) / 1e6,
		"mem_total_mb": mem["MemTotal"] / 1024, "mem_available_mb": mem["MemAvailable"] / 1024}
}
func hexRand(n int) string { b := make([]byte, n); crand.Read(b); return hex.EncodeToString(b) }

func probe(h http.Header) map[string]any {
	reqWall := float64(time.Now().UnixNano()) / 1e9
	reqMono := time.Since(t0Mono).Seconds()
	before := procstat()
	workStart := time.Now()
	n := requests.Add(1)
	payload := strings.Repeat(fmt.Sprintf(`{"n":%d,"ts":%f}`, n, reqWall), 50)
	after := procstat()
	host, _ := os.Hostname()
	var sess any
	if v := h.Get("X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"); v != "" {
		sess = v
	}
	return map[string]any{
		"variant": variant, "mode": "http", "language": "go", "go": runtime.Version(), "knobs": map[string]any{},
		"start": map[string]any{"wall": t0Wall, "mono": 0.0, "uptime": startUptime, "boot_id": bootID, "first_random": firstRandom},
		"request": map[string]any{
			"n": n, "wall": reqWall, "mono": reqMono, "uptime": uptime(),
			"wall_since_start_s": reqWall - t0Wall, "mono_since_start_s": reqMono,
			"boot_id": readTrim("/proc/sys/kernel/random/boot_id"), "kernel_uuid": readTrim("/proc/sys/kernel/random/uuid"),
			"random": mrand.Float64(), "random_v2": rand2.Float64(), "urandom": hexRand(4), "uuid4": hexRand(16),
			"hostname": host, "pid": os.Getpid(), "cpus": runtime.NumCPU(), "env_count": len(os.Environ()),
			"session_header": sess,
		},
		"before": before, "after": after, "work": map[string]any{"json_len": len(payload)},
		"work_ms": float64(time.Since(workStart).Microseconds()) / 1000,
	}
}

func main() {
	http.HandleFunc("/ping", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("content-type", "application/json")
		io.WriteString(w, `{"status":"Healthy"}`)
	})
	http.HandleFunc("/invocations", func(w http.ResponseWriter, r *http.Request) {
		io.ReadAll(r.Body)
		w.Header().Set("content-type", "application/json")
		json.NewEncoder(w).Encode(probe(r.Header))
	})
	http.ListenAndServe("0.0.0.0:8080", nil)
}
