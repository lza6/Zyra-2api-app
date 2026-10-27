# Zyra-2api-app

Zyra v1.1.5 (`gpt.text.ai.newchatbot`, PlatinumMods modded APK, 63MB, 无壳) 协议逆向 + OpenAI 兼容 2API 网关 + 第一轮压测报告。

> 仅供安全研究与协议学习。所有数据来自本地黑盒实测。

## 上游协议（已验证）

| 项 | 值 |
|---|---|
| Endpoint | `POST https://us-central1-llmchat-22d7a.cloudfunctions.net/generate` |
| 鉴权 | 静态 header `QtcY6-KEY: bOBHq59mhSJ7aPK5Ut4k`（硬编码于 classes5.dex `AiApi.kt`，无设备指纹/签名/时间戳校验） |
| 请求体 | `{"input": "<User:/Assistant: 拼接的对话>", "app-name": "notebook", "version": "1", "platform": "mobile"}` |
| 响应 | `{"output": "...", "success": true}` / 错误 `{"error": "...", "success": false}` |
| 后端模型 | 自报 **Qwen3.5** |
| System prompt | 可被注入直接套出（通用无害模板，2058 字，见本地 `sysprompt_leak.txt`） |

### 服务端校验行为（实测）

| 输入 | 响应 |
|---|---|
| 错误 key | 401 Unauthorized: Invalid or missing QtcY6-KEY header |
| 缺 `input` | 400 Missing 'input' or 'prompt' in request body |
| 缺 `app-name`/`version`/`platform` | 400 精确列出缺哪些 |
| `app-name` 任意值 | 200 通过（不校验内容） |
| `prompt` 字段 | 可替代 `input`（别名兼容） |
| 8KB 长输入 | 200 正常 |

客户端把历史压成 `User: ...\n\nAssistant: ...` 纯文本塞进单个 `input`，服务端无会话隔离 → 完整上下文可自控。

## 压测结论（Windows + 本地代理 127.0.0.1:10808 实测）

| 场景 | 结果 |
|---|---|
| 突发 30 并发 | 30/30 全 200，median 2.5s，total 4.4s |
| 突发 60 并发 | 60/60 全 200，median 2.5s，total 4.1s |
| 突发 100 并发 x2 | 第一轮 91/100（9 个本地连接超时，非 429）；第二轮 **100/100 全 200**，median 3.6s |
| 串行无间隔 x60 | 60/60，median 676ms，零失败 |
| 持续 60s @ ~6.5rps | **393/393 全成功**，零 429/403/5xx |
| 10 分钟持续 @ ~8rps | 见下表 |

**结论：上游无 IP 级限流、无封禁窗口、无速率闸。** 唯一瓶颈是 Cloud Functions 冷启动/排队导致的并发毛刺（p95 ~6s），错误表现为客户端侧连接超时而非服务端拒绝。配额只存在于 `QtcY6-KEY` 静态 key 维度，而该 key 人人有份。

## 交付物

| 文件 | 说明 |
|---|---|
| `demo_server.py` | 2API 网关（端口 8916）：`/v1/generate`（OpenAI messages 兼容）+ `/health` `/stats` |
| `demo.html` | 中文聊天 demo 页 |
| `stress_test.py` | 本地压测脚本（7/7 PASS） |
| `ladders/` | 阶梯压测脚本与原始数据 |

## 与 new-api 集成建议

- 渠道类型：OpenAI 兼容自定义渠道，base_url 指向 demo_server，或直接实现该协议的渠道 adapter
- 单 key（`bOBHq59mhSJ7aPK5Ut4k`）即可多并发，无需号池
- 建议网关侧对上游做 90s 超时 + 1 次重试（覆盖偶发并发毛刺）
- 无流式：上游只返回完整 JSON，2API 层可用伪流式（分块下发）改善体验

## Windows 环境坑（复现用）

- `curl.exe`(schannel) 对该域名 TLS 握手 exit 35；直连 TCP 被墙
- 必须 node + `undici.ProxyAgent('http://127.0.0.1:10808')` 走本地代理；Python urllib 走系统代理自动生效
- jadx 1.5.0 路径：`C:/Users/Administrator.DESKTOP-EGNE9ND/Desktop/apk_analysis/jadx`

## 免责声明

本项目仅用于安全研究与学习。请勿用于任何违反当地法律法规或服务条款的用途。使用本项目产生的一切后果由使用者自行承担。
