#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zyra demo server 第一轮压测: 基线 / 错误路径 / 并发"""
import json
import statistics
import threading
import time
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8916"
results = []

def req(method, path, body=None, timeout=120):
    t0 = time.time()
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode()), time.time() - t0
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode()), time.time() - t0
        except Exception:
            return e.code, {}, time.time() - t0

def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name + ("  | " + detail if detail else ""))

# ---- 1. health ----
s, j, dt = req("GET", "/health")
check("health", s == 200 and j.get("status") == "ok", "%.1fms" % (dt * 1000))

# ---- 2. 基线: 单条生成 x3 ----
lats = []
ok_all = True
for i in range(3):
    s, j, dt = req("POST", "/v1/generate", {"input": "User: 用一句话介绍第%d次测试\n\nAssistant:" % i})
    lats.append(dt * 1000)
    ok_all = ok_all and s == 200 and j.get("success") and len(j.get("output", "")) > 0
check("baseline x3", ok_all, "median %.0fms max %.0fms" % (statistics.median(lats), max(lats)))

# ---- 3. OpenAI 风格 messages ----
s, j, dt = req("POST", "/v1/generate", {"messages": [
    {"role": "user", "content": "hi"},
    {"role": "assistant", "content": "hello"},
    {"role": "user", "content": "1+1=? 只回答数字"},
]})
check("messages fmt", s == 200 and j.get("success"), "answer=%r" % j.get("output", "")[:30])

# ---- 4. 错误路径 ----
s, _, dt = req("POST", "/v1/generate", {})
check("empty body -> 400", s == 400, "%d" % s)
s, _, dt = req("POST", "/v1/nonexist", {})
check("404 path", s == 404, "%d" % s)

# ---- 5. 并发 x8 ----
lat, errs = [], []
lock = threading.Lock()
def worker(i):
    s, j, dt = req("POST", "/v1/generate", {"input": "User: say %d\n\nAssistant:" % i})
    with lock:
        if s == 200 and j.get("success"):
            lat.append(dt * 1000)
        else:
            errs.append(s)
t0 = time.time()
threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
[t.start() for t in threads]
[t.join() for t in threads]
total = time.time() - t0
check("concurrent x8", len(lat) == 8 and not errs,
      "8/8 ok, total %.1fs, median %.0fms" % (total, statistics.median(lat) if lat else -1))

# ---- 6. /stats 一致性 ----
s, j, dt = req("GET", "/stats")
check("stats consistency", s == 200 and j.get("upstream_calls", 0) >= 12,
      "calls=%d ok=%d err=%d" % (j.get("upstream_calls", 0), j.get("upstream_ok", 0), j.get("upstream_err", 0)))

passed = sum(1 for _, ok, _ in results if ok)
print("\n%d/%d PASS" % (passed, len(results)))
