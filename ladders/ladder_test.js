// 阶梯压测脚本 — 上游限流/封禁探测
// 用法: node ladder_test.js   (需走本地代理 127.0.0.1:10808)
const {setGlobalDispatcher, ProxyAgent} = require('undici');
setGlobalDispatcher(new ProxyAgent('http://127.0.0.1:10808'));
const u = 'https://us-central1-llmchat-22d7a.cloudfunctions.net/generate';
const KEY = 'bOBHq59mhSJ7aPK5Ut4k';

async function call(i) {
  const t0 = Date.now();
  try {
    const r = await fetch(u, {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'QtcY6-KEY': KEY},
      body: JSON.stringify({input: 'User: reply with just OK\n\nAssistant:',
                            'app-name': 'notebook', version: '1', platform: 'mobile'}),
      signal: AbortSignal.timeout(90000),
    });
    const t = await r.text();
    return {code: r.status, ms: Date.now() - t0, ok: r.status === 200 && t.includes('"success"')};
  } catch (e) {
    return {code: 'ERR', ms: Date.now() - t0, ok: false, err: e.message.slice(0, 60)};
  }
}

function summarize(rs) {
  const codes = {};
  rs.forEach(r => codes[r.code] = (codes[r.code] || 0) + 1);
  const okms = rs.filter(r => r.ok).map(r => r.ms).sort((a, b) => a - b);
  return {codes, total: rs.length,
    median: okms.length ? okms[Math.floor(okms.length / 2)] : null,
    p95: okms.length ? okms[Math.floor(okms.length * 0.95)] : null};
}

(async () => {
  for (const n of [10, 30, 60, 100]) {
    const t0 = Date.now();
    const rs = await Promise.all(Array.from({length: n}, (_, i) => call(i)));
    const s = summarize(rs);
    console.log(`burst ${n}:`, JSON.stringify(s.codes), `total ${Date.now() - t0}ms`,
      s.median ? `median ${s.median}ms p95 ${s.p95}ms` : '');
    await new Promise(r => setTimeout(r, 3000));
  }
  console.log('--- serial x60 no-delay ---');
  const t0 = Date.now(); const ser = [];
  for (let i = 0; i < 60; i++) ser.push(await call(i));
  console.log('serial:', JSON.stringify(summarize(ser)), `total ${Date.now() - t0}ms`);
})();
