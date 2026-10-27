# Zyra → new-api 渠道集成备忘（待实施）

## 协议摘要

上游 Firebase CFN, OpenAI 不兼容, 需要自定义渠道 adapter (参考 type 60s 系列的自定义渠道写法):

```
POST https://us-central1-llmchat-22d7a.cloudfunctions.net/generate
Headers:
  Content-Type: application/json
  QtcY6-KEY: bOBHq59mhSJ7aPK5Ut4k
Body:
  {"input": "<对话文本>", "app-name": "notebook", "version": "1", "platform": "mobile"}
Response:
  200 {"output": "...", "success": true}
  4xx {"error": "...", "success": false}
```

- input 构造: 多轮时 `User: ...\n\nAssistant: ...\n\nUser: ...\n\nAssistant:` (结尾追加 Assistant: 触发续写)
- 无流式: 上游一次性返回完整 JSON, 需网关侧伪流式
- 超时建议 90s, 重试 1 次

## new-api 对接要点

1. **渠道类型**: 自定义 OpenAI 兼容渠道 + 本地 2API 中转 (demo_server.py), 或写原生 adapter
2. **模型名**: 上游后端自报 Qwen3.5, 但模型名是 app 固定的, 无模型参数可选 → 单模型渠道
3. **密钥**: 单静态 key, 渠道密钥栏直接填 `bOBHq59mhSJ7aPK5Ut4k`
4. **无鉴权风险**: 上游无设备级校验, 网关侧必须自己加用户鉴权 + 限流, 否则被打死
5. **计费**: 按 output token 计费, 建议与 Qwen 系列同价

## 待用户决策

- [ ] 原生 adapter vs 中转 demo_server (中转简单但多一跳)
- [ ] 模型名命名 (如 `zyra-chat`)
- [ ] 是否需要伪流式
