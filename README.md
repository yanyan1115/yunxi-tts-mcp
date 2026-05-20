# Yunxi TTS MCP

English | [中文](#中文)

Yunxi TTS MCP is a small MCP server for generating Chinese speech with `edge-tts`.
It defaults to the Microsoft Edge voice `zh-CN-YunxiNeural` with gentle tuning for a lower, steadier sound:

- `voice`: `zh-CN-YunxiNeural`
- `rate`: `-5%`
- `pitch`: `-8Hz`
- `volume`: `+0%`

## Features

- `text_to_speech`: turn text into an MP3 file.
- `text_to_voice_note`: generate an MP3, convert it to OGG/Opus with `ffmpeg`, and optionally send it through Telegram Bot API `sendVoice`.
- Browser-friendly MP3 output: when `ffmpeg` is available, raw `edge-tts` MP3 files are re-encoded with `libmp3lame` before they are served through `/audio`.
- stdio MCP support for local clients such as Claude Desktop, Codex, Gemini, and other MCP-compatible tools.
- streamable HTTP MCP support for remote connectors.
- Optional OAuth authorization page for remote MCP connectors. The connection secret is read only from environment variables.
- Optional public media URLs when `TTS_PUBLIC_BASE_URL` is configured.

## Requirements

- Python 3.11 or newer
- `ffmpeg` available on `PATH` for `text_to_voice_note` and recommended for browser-friendly MP3 output
- A Telegram bot token only if you want to use `sendVoice`

## Install

```bash
git clone https://github.com/yanyan1115/yunxi-tts-mcp.git
cd yunxi-tts-mcp
python -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
git clone https://github.com/yanyan1115/yunxi-tts-mcp.git
cd yunxi-tts-mcp
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Quick Test

```bash
./.venv/bin/edge-tts --voice zh-CN-YunxiNeural --text "你好，我是云希。" --write-media output/test.mp3
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\edge-tts --voice zh-CN-YunxiNeural --text "你好，我是云希。" --write-media output\test.mp3
```

## Tools

### text_to_speech

Required:

- `text`: text to speak

Optional:

- `voice`: defaults to `zh-CN-YunxiNeural`
- `rate`: defaults to `-5%`
- `volume`: defaults to `+0%`
- `pitch`: defaults to `-8Hz`
- `output_dir`: defaults to `./output`
- `filename`: optional MP3 filename

Example:

```json
{
  "text": "你好，我是云希。",
  "filename": "hello-yunxi.mp3"
}
```

When `ffmpeg` is available, `text_to_speech` writes the raw `edge-tts` MP3 to a temporary file and re-encodes the final MP3 with:

```text
codec: libmp3lame
sample rate: 44100 Hz
channels: 1
bitrate: 96k
```

The result includes re-encode metadata:

```json
{
  "mp3_reencoded": true,
  "mp3_codec": "libmp3lame",
  "mp3_sample_rate": 44100,
  "mp3_channels": 1,
  "mp3_bitrate": "96k"
}
```

If `ffmpeg` is not available, the tool falls back to the raw `edge-tts` MP3 and returns `mp3_reencoded: false`.

### text_to_voice_note

Required:

- `text`: text to speak

Optional:

- `chat_id`: Telegram chat ID. If omitted, the server only generates the MP3 and OGG files.
- `caption`: optional Telegram voice caption.
- `voice`, `rate`, `volume`, `pitch`, `output_dir`, `filename`: same meaning as `text_to_speech`.

The tool converts MP3 to Telegram voice-note friendly OGG/Opus:

```bash
ffmpeg -i input.mp3 -c:a libopus output.ogg
```

It uses Telegram `sendVoice`, not `sendAudio`, so Telegram displays the result as a voice message.

## Environment Variables

Copy `.env.example` and fill in your own values, or export variables in your shell.

| Variable | Purpose |
| --- | --- |
| `TTS_OUTPUT_DIR` | Directory for generated MP3/OGG files. Defaults to `./output`. |
| `TTS_PUBLIC_BASE_URL` | Public base URL used to return `audio_url` and `voice_url`, for example `https://example.com`. |
| `FFMPEG` | ffmpeg executable name or path. Defaults to `ffmpeg`. |
| `TTS_TELEGRAM_BOT_TOKEN` | Telegram bot token for `sendVoice`. |
| `TTS_TELEGRAM_BOT_TOKEN_ENV` | Name of the environment variable that contains the bot token. Defaults to `TTS_TELEGRAM_BOT_TOKEN`. |
| `MCP_HOST` | HTTP bind host. Defaults to `127.0.0.1`. |
| `MCP_PORT` | HTTP bind port. Defaults to `8891`. |
| `MCP_ALLOWED_HOSTS` | Comma-separated allowed hosts for transport security. |
| `MCP_ALLOWED_ORIGINS` | Comma-separated allowed origins for transport security. |
| `MCP_OAUTH_ENABLED` | Set to `1` to enable OAuth for remote MCP. |
| `MCP_OAUTH_CONNECT_SECRET` | Secret typed into the OAuth authorization page. |
| `MCP_OAUTH_ISSUER_URL` | OAuth issuer URL, usually `https://example.com`. |
| `MCP_OAUTH_RESOURCE_URL` | OAuth resource URL, usually `https://example.com/mcp`. |
| `MCP_OAUTH_STORE` | Path for the local OAuth token store. Defaults to `./oauth_store.json`. |

## stdio MCP

Run the server over stdio:

```bash
./.venv/bin/python tts_mcp_server.py
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\python .\tts_mcp_server.py
```

Claude Desktop config example:

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

Windows example:

```json
{
  "mcpServers": {
    "yunxi-tts": {
      "command": "C:\\path\\to\\yunxi-tts-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\yunxi-tts-mcp\\tts_mcp_server.py"]
    }
  }
}
```

Codex or Gemini MCP registration uses the same command-and-args pattern. Adapt the JSON shape to your client:

```json
{
  "name": "yunxi-tts",
  "command": "/opt/yunxi-tts-mcp/.venv/bin/python",
  "args": ["/opt/yunxi-tts-mcp/tts_mcp_server.py"],
  "env": {
    "TTS_OUTPUT_DIR": "/opt/yunxi-tts-mcp/output"
  }
}
```

Run the included stdio smoke test:

```bash
./.venv/bin/python smoke_test.py
```

The smoke test generates a local MP3 only. It does not call Telegram.

## Streamable HTTP MCP

Run locally without OAuth:

```bash
MCP_HOST=127.0.0.1 MCP_PORT=8891 ./.venv/bin/python tts_mcp_server.py --transport streamable-http
```

Or use the wrapper:

```bash
./run_tts_mcp_http.sh
```

For a remote connector behind HTTPS, set your own domain and secret:

```bash
export TTS_PUBLIC_BASE_URL="https://example.com"
export MCP_OAUTH_ENABLED=1
export MCP_OAUTH_CONNECT_SECRET="YOUR_CONNECT_SECRET"
export MCP_ALLOWED_HOSTS="example.com,example.com:*"
export MCP_ALLOWED_ORIGINS="https://example.com"
./run_tts_mcp_http.sh
```

Example reverse proxy config is in `deploy/nginx-tts-mcp.conf`. Replace `example.com` with your domain and make sure TLS is handled by your reverse proxy or tunnel.

Claude custom connector example:

```text
Name: Yunxi TTS
Remote MCP server URL: https://example.com/mcp
OAuth Client ID: leave empty
OAuth Client Secret: leave empty
```

When the connector opens the authorization page, enter the value of `MCP_OAUTH_CONNECT_SECRET`.

## Telegram sendVoice

Create a bot with BotFather, put the token in an environment variable, and pass `chat_id` only when you actually want to send a voice message:

```bash
export TTS_TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
```

Tool call example:

```json
{
  "text": "这是一条 Telegram 语音条测试。",
  "chat_id": "YOUR_CHAT_ID",
  "filename": "telegram-test"
}
```

If `chat_id` is omitted, `text_to_voice_note` only creates local files and optional public URLs.

## Security Notes

- Never commit real Telegram tokens, chat IDs, OAuth secrets, server IPs, private domains, deployment logs, or personal filesystem paths.
- Keep `.env`, `oauth_store.json`, `output/`, `*.mp3`, and `*.ogg` out of git.
- Bind HTTP to `127.0.0.1` unless you are deliberately exposing it behind a trusted HTTPS reverse proxy.
- Use a long random `MCP_OAUTH_CONNECT_SECRET` for remote connectors.
- Treat generated audio as user content. Do not serve `output/` publicly unless you intend to expose those files.
- Keep `ffmpeg`, Python dependencies, and your reverse proxy updated.

## Acknowledgements

Thanks to Claude for helping shape the feature ideas, voice selection, testing approach, and Telegram voice-note flow.

Thanks to GPT / Codex for implementation, debugging, local and server deployment validation, OAuth remote MCP support, and Telegram voice-note integration.

## License

MIT

---

# 中文

[English](#yunxi-tts-mcp) | 中文

Yunxi TTS MCP 是一个基于 `edge-tts` 的 MCP server，用来把文本生成中文语音文件。默认声线是 `zh-CN-YunxiNeural`，默认参数如下：

- `voice`: `zh-CN-YunxiNeural`
- `rate`: `-5%`
- `pitch`: `-8Hz`
- `volume`: `+0%`

## 功能

- `text_to_speech`: 输入文字，生成 MP3。
- `text_to_voice_note`: 生成 MP3，再用 `ffmpeg` 转成 OGG/Opus，可选调用 Telegram Bot API `sendVoice` 发送语音条。
- 浏览器友好的 MP3 输出：当系统里有 `ffmpeg` 时，服务会先把 raw `edge-tts` MP3 重编码为 `libmp3lame` MP3，再通过 `/audio` 返回。
- 支持 stdio MCP，适合本地 Claude Desktop、Codex、Gemini 等 MCP 客户端。
- 支持 streamable HTTP remote MCP。
- 支持可选 OAuth 授权页，连接密钥只从环境变量读取。
- 设置 `TTS_PUBLIC_BASE_URL` 后，工具结果会返回可访问的音频 URL。

## 环境要求

- Python 3.11 或更新版本
- 系统里可以从 `PATH` 调用 `ffmpeg`，用于 `text_to_voice_note`，并推荐用于浏览器友好的 MP3 输出
- 只有需要 Telegram `sendVoice` 时，才需要 Telegram bot token

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

## 快速测试

```bash
./.venv/bin/edge-tts --voice zh-CN-YunxiNeural --text "你好，我是云希。" --write-media output/test.mp3
```

Windows PowerShell:

```powershell
.\.venv\Scripts\edge-tts --voice zh-CN-YunxiNeural --text "你好，我是云希。" --write-media output\test.mp3
```

## 工具

### text_to_speech

必填：

- `text`: 要合成语音的文本

可选：

- `voice`: 默认 `zh-CN-YunxiNeural`
- `rate`: 默认 `-5%`
- `volume`: 默认 `+0%`
- `pitch`: 默认 `-8Hz`
- `output_dir`: 默认 `./output`
- `filename`: 可选 MP3 文件名

示例：

```json
{
  "text": "你好，我是云希。",
  "filename": "hello-yunxi.mp3"
}
```

当 `ffmpeg` 可用时，`text_to_speech` 会先把 raw `edge-tts` MP3 写入临时文件，再把最终 MP3 重编码为：

```text
codec: libmp3lame
sample rate: 44100 Hz
channels: 1
bitrate: 96k
```

返回结果会包含重编码元数据：

```json
{
  "mp3_reencoded": true,
  "mp3_codec": "libmp3lame",
  "mp3_sample_rate": 44100,
  "mp3_channels": 1,
  "mp3_bitrate": "96k"
}
```

如果 `ffmpeg` 不可用，工具会回退到 raw `edge-tts` MP3，并返回 `mp3_reencoded: false`。

### text_to_voice_note

必填：

- `text`: 要合成语音的文本

可选：

- `chat_id`: Telegram chat ID。不传时只生成 MP3 和 OGG 文件。
- `caption`: 可选 Telegram 语音条说明。
- `voice`、`rate`、`volume`、`pitch`、`output_dir`、`filename`: 含义同 `text_to_speech`。

工具会把 MP3 转成适合 Telegram voice-note 的 OGG/Opus：

```bash
ffmpeg -i input.mp3 -c:a libopus output.ogg
```

它调用的是 Telegram `sendVoice`，不是 `sendAudio`，所以 Telegram 会显示为语音消息。

## 环境变量

复制 `.env.example` 后填写你自己的值，或者在 shell 里导出环境变量。

| 变量 | 用途 |
| --- | --- |
| `TTS_OUTPUT_DIR` | 生成 MP3/OGG 的输出目录，默认 `./output`。 |
| `TTS_PUBLIC_BASE_URL` | 用于返回 `audio_url` 和 `voice_url` 的公开 URL，例如 `https://example.com`。 |
| `FFMPEG` | ffmpeg 可执行文件名或路径，默认 `ffmpeg`。 |
| `TTS_TELEGRAM_BOT_TOKEN` | Telegram `sendVoice` 使用的 bot token。 |
| `TTS_TELEGRAM_BOT_TOKEN_ENV` | 存放 bot token 的环境变量名，默认 `TTS_TELEGRAM_BOT_TOKEN`。 |
| `MCP_HOST` | HTTP 绑定地址，默认 `127.0.0.1`。 |
| `MCP_PORT` | HTTP 绑定端口，默认 `8891`。 |
| `MCP_ALLOWED_HOSTS` | 传输安全使用的 host 白名单，多个值用英文逗号分隔。 |
| `MCP_ALLOWED_ORIGINS` | 传输安全使用的 origin 白名单，多个值用英文逗号分隔。 |
| `MCP_OAUTH_ENABLED` | 设为 `1` 时启用 remote MCP OAuth。 |
| `MCP_OAUTH_CONNECT_SECRET` | OAuth 授权页里输入的连接密钥。 |
| `MCP_OAUTH_ISSUER_URL` | OAuth issuer URL，通常是 `https://example.com`。 |
| `MCP_OAUTH_RESOURCE_URL` | OAuth resource URL，通常是 `https://example.com/mcp`。 |
| `MCP_OAUTH_STORE` | 本地 OAuth token store 路径，默认 `./oauth_store.json`。 |

## stdio MCP

通过 stdio 启动：

```bash
./.venv/bin/python tts_mcp_server.py
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python .\tts_mcp_server.py
```

Claude Desktop 配置示例：

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

Windows 示例：

```json
{
  "mcpServers": {
    "yunxi-tts": {
      "command": "C:\\path\\to\\yunxi-tts-mcp\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\yunxi-tts-mcp\\tts_mcp_server.py"]
    }
  }
}
```

Codex 或 Gemini MCP 注册也使用同样的 command 和 args 思路，按客户端自己的配置格式调整即可：

```json
{
  "name": "yunxi-tts",
  "command": "/opt/yunxi-tts-mcp/.venv/bin/python",
  "args": ["/opt/yunxi-tts-mcp/tts_mcp_server.py"],
  "env": {
    "TTS_OUTPUT_DIR": "/opt/yunxi-tts-mcp/output"
  }
}
```

运行内置 stdio smoke test：

```bash
./.venv/bin/python smoke_test.py
```

这个测试只生成本地 MP3，不会调用 Telegram。

## Streamable HTTP MCP

本地无 OAuth 启动：

```bash
MCP_HOST=127.0.0.1 MCP_PORT=8891 ./.venv/bin/python tts_mcp_server.py --transport streamable-http
```

也可以使用 wrapper：

```bash
./run_tts_mcp_http.sh
```

如果要放在 HTTPS 后面作为 remote connector 使用，请设置你自己的域名和密钥：

```bash
export TTS_PUBLIC_BASE_URL="https://example.com"
export MCP_OAUTH_ENABLED=1
export MCP_OAUTH_CONNECT_SECRET="YOUR_CONNECT_SECRET"
export MCP_ALLOWED_HOSTS="example.com,example.com:*"
export MCP_ALLOWED_ORIGINS="https://example.com"
./run_tts_mcp_http.sh
```

反向代理示例在 `deploy/nginx-tts-mcp.conf`。请把 `example.com` 换成你的域名，并确保 TLS 由反向代理或隧道处理。

Claude custom connector 示例：

```text
Name: Yunxi TTS
Remote MCP server URL: https://example.com/mcp
OAuth Client ID: leave empty
OAuth Client Secret: leave empty
```

连接器打开授权页后，输入 `MCP_OAUTH_CONNECT_SECRET` 的值。

## Telegram sendVoice

用 BotFather 创建 bot，把 token 放进环境变量，只在确实要发送语音消息时传 `chat_id`：

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

不传 `chat_id` 时，`text_to_voice_note` 只生成本地文件和可选公开 URL。

## 安全注意事项

- 不要提交真实 Telegram token、chat_id、OAuth secret、服务器 IP、真实域名、私人路径或部署日志。
- `.env`、`oauth_store.json`、`output/`、`*.mp3`、`*.ogg` 都应保持在 git 之外。
- HTTP 默认绑定到 `127.0.0.1`。公开访问时请放在可信 HTTPS 反向代理后面。
- remote connector 的 `MCP_OAUTH_CONNECT_SECRET` 应使用高强度随机值。
- 生成的音频属于用户内容。除非你确实想公开这些文件，否则不要公开服务整个 `output/` 目录。
- 请保持 `ffmpeg`、Python 依赖和反向代理更新。

## 致谢

感谢 Claude 参与功能构思、声线选择、测试思路和 Telegram voice-note 流程设计。

感谢 GPT / Codex 负责实现、调试、本地与服务器部署验证、OAuth remote MCP 和 Telegram voice-note 集成。

## 许可证

MIT
