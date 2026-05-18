# Yunxi TTS MCP

Yunxi TTS MCP 是一个基于 `edge-tts` 的 MCP server，用来把文本生成中文语音文件。默认声线是 `zh-CN-YunxiNeural`，默认参数如下：

- `voice`: `zh-CN-YunxiNeural`
- `rate`: `-5%`
- `pitch`: `-8Hz`
- `volume`: `+0%`

## 功能

- `text_to_speech`: 输入文字，生成 MP3。
- `text_to_voice_note`: 生成 MP3，再用 `ffmpeg` 转成 OGG/Opus，可选调用 Telegram Bot API `sendVoice` 发送语音条。
- 支持 stdio MCP，适合本地 Claude Desktop、Codex、Gemini 等 MCP 客户端。
- 支持 streamable HTTP remote MCP。
- 支持可选 OAuth 授权页，连接密钥只从环境变量读取。
- 设置 `TTS_PUBLIC_BASE_URL` 后，工具结果会返回可访问的音频 URL。

## 安装

```bash
git clone https://github.com/yanyan1115/yunxi-tts-mcp.git
cd yunxi-tts-mcp
python -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
git clone https://github.com/yanyan1115/yunxi-tts-mcp.git
cd yunxi-tts-mcp
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

`text_to_voice_note` 需要系统里有 `ffmpeg`，并且可以从 `PATH` 调用。

## stdio MCP

启动：

```bash
./.venv/bin/python tts_mcp_server.py
```

Claude Desktop 示例：

```json
{
  "mcpServers": {
    "yunxi-tts": {
      "command": "/opt/yunxi-tts-mcp/.venv/bin/python",
      "args": ["/opt/yunxi-tts-mcp/tts_mcp_server.py"],
      "env": {
        "TTS_OUTPUT_DIR": "/opt/yunxi-tts-mcp/output",
        "TTS_TELEGRAM_BOT_TOKEN": "YOUR_BOT_TOKEN"
      }
    }
  }
}
```

Codex / Gemini 等 MCP 客户端也使用同样的 command、args、env 思路，按各自配置格式填写即可。

本地 smoke test：

```bash
./.venv/bin/python smoke_test.py
```

这个测试只生成本地 MP3，不会调用 Telegram。

## Streamable HTTP Remote MCP

本地启动：

```bash
MCP_HOST=127.0.0.1 MCP_PORT=8891 ./.venv/bin/python tts_mcp_server.py --transport streamable-http
```

远程 HTTPS 连接器示例：

```bash
export TTS_PUBLIC_BASE_URL="https://example.com"
export MCP_OAUTH_ENABLED=1
export MCP_OAUTH_CONNECT_SECRET="YOUR_CONNECT_SECRET"
export MCP_ALLOWED_HOSTS="example.com,example.com:*"
export MCP_ALLOWED_ORIGINS="https://example.com"
./run_tts_mcp_http.sh
```

Claude custom connector 示例：

```text
Name: Yunxi TTS
Remote MCP server URL: https://example.com/mcp
OAuth Client ID: leave empty
OAuth Client Secret: leave empty
```

授权页里输入 `MCP_OAUTH_CONNECT_SECRET` 的值。

## Telegram sendVoice

设置 bot token：

```bash
export TTS_TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
```

工具调用示例：

```json
{
  "text": "这是一条 Telegram 语音条测试。",
  "chat_id": "YOUR_CHAT_ID",
  "filename": "telegram-test"
}
```

不传 `chat_id` 时，`text_to_voice_note` 只生成 MP3 和 OGG 文件，不会发送消息。

## 环境变量

参考 `.env.example`。不要提交真实 token、chat_id、OAuth secret、服务器 IP、真实域名、私人路径或部署日志。

常用变量：

- `TTS_OUTPUT_DIR`: 输出目录，默认 `./output`。
- `TTS_PUBLIC_BASE_URL`: 生成 `audio_url` / `voice_url` 的公开 URL，例如 `https://example.com`。
- `TTS_TELEGRAM_BOT_TOKEN`: Telegram bot token。
- `MCP_OAUTH_ENABLED`: 设为 `1` 启用 OAuth。
- `MCP_OAUTH_CONNECT_SECRET`: remote connector 授权页使用的连接密钥。
- `MCP_ALLOWED_HOSTS` / `MCP_ALLOWED_ORIGINS`: remote MCP 的 host 和 origin 白名单。

## 安全注意事项

- 不要提交真实 Telegram token、chat_id、OAuth secret、服务器 IP、真实域名、个人路径或部署日志。
- `.env`、`oauth_store.json`、`output/`、`*.mp3`、`*.ogg` 都应保持在 git 之外。
- HTTP 默认绑定到 `127.0.0.1`，公开访问时请放在可信 HTTPS 反向代理后面。
- remote connector 的 `MCP_OAUTH_CONNECT_SECRET` 应使用高强度随机值。

## 致谢

感谢 Claude 参与功能构思、声线选择、测试思路和 Telegram voice-note 流程设计。

感谢 GPT / Codex 负责实现、调试、本地与服务器部署验证、OAuth remote MCP 和 Telegram voice-note 集成。

## License

MIT
