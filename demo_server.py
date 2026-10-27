#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zyra v1.1.5 (gpt.text.ai.newchatbot) demo server — 第一轮压测配套
上游: https://us-central1-llmchat-22d7a.cloudfunctions.net/generate (Firebase CFN)
鉴权: header QtcY6-KEY = bOBHq59mhSJ7aPK5Ut4k (静态, 硬编码在 classes5.dex)
请求体: {"input": "<flattened chat>", "app-name": "notebook", "version": "1", "platform": "mobile"}
响应: {"output": "...", "success": true}
端口: 8916
"""
import json
import time
import threading
import statistics
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request

UPSTREAM = "https://us-central1-llmchat-22d7a.cloudfunctions.net/generate"
API_KEY = "bOBHq59mhSJ7aPK5Ut4k"
PORT = 8916

stats = {"upstream_calls": 0, "upstream_ok": 0, "upstream_err": 0, "errors": {}, "latencies": []}
stats_lock = threading.Lock()

def record(lat, ok):
    with stats_lock:
        stats["upstream_calls"] += 1
        if ok:
            stats["upstream_ok"] += 1
            stats["latencies"].append(lat)
        else:
            stats["upstream_err"] += 1

def upstream_generate(text, timeout=90):
    """透传上游。返回 (status, dict)"""
    body = json.dumps({
        "input": text,
        "app-name": "notebook",
        "version": "1",
        "platform": "mobile",
    }).encode()
    req = urllib.request.Request(
        UPSTREAM, data=body, method="POST",
        headers={"Content-Type": "application/json", "QtcY6-KEY": API_KEY,
                 "User-Agent": "okhttp/4.9.3"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
            record(time.time() - t0, bool(data.get("success")))
            return r.status, data
    except urllib.error.HTTPError as e:
        record(time.time() - t0, False)
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": "upstream http %d" % e.code, "success": False}
    except Exception as e:
        record(time.time() - t0, False)
        return 502, {"error": "upstream unreachable: %s" % e, "success": False}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass  # 压测时静默

    def _send(self, code, obj, raw=None):
        payload = raw if raw is not None else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    # ---------- 路由 ----------
    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"status": "ok", "service": "zyra-demo", "port": PORT})
        elif self.path == "/stats":
            with stats_lock:
                lats = sorted(stats["latencies"])
                n = len(lats)
                s = {
                    "upstream_calls": stats["upstream_calls"],
                    "upstream_ok": stats["upstream_ok"],
                    "upstream_err": stats["upstream_err"],
                }
            if n:
                s["latency_ms"] = {
                    "p50": round(lats[n // 2] * 1000, 1),
                    "p95": round(lats[int(n * 0.95)] * 1000, 1),
                    "max": round(lats[-1] * 1000, 1),
                    "avg": round(sum(lats) / n * 1000, 1),
                }
            self._send(200, s)
        elif self.path == "/" or self.path == "/demo.html":
            try:
                with open("demo.html", "rb") as f:
                    html = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            except FileNotFoundError:
                self._send(404, {"error": "demo.html not found"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode()) if n else {}
        except Exception:
            self._send(400, {"error": "invalid json"})
            return

        if self.path == "/v1/generate":
            # OpenAI 风格入参兼容: messages 数组或直接 prompt
            text = body.get("input")
            if text is None and "messages" in body:
                msgs = body["messages"]
                if len(msgs) == 1:
                    text = msgs[0].get("content", "")
                else:
                    parts = []
                    for m in msgs:
                        who = "Assistant" if m.get("role") in ("model", "assistant") else "User"
                        parts.append("%s: %s" % (who, m.get("content", "")))
                    text = "\n\n".join(parts) + "\n\nAssistant:"
            if not text:
                self._send(400, {"error": "Missing 'input' or 'messages'"})
                return
            code, data = upstream_generate(text)
            if code == 200 and data.get("success"):
                self._send(200, {"output": data.get("output", ""),
                                 "success": True, "upstream_ms": None})
            else:
                self._send(code if code != 200 else 502, data)
        else:
            self._send(404, {"error": "not found"})


if __name__ == "__main__":
    print("Zyra demo server on http://0.0.0.0:%d  (upstream: Firebase CFN)" % PORT)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
