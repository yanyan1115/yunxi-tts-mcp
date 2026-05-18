# Yunxi TTS MCP

Yunxi TTS MCP is a small MCP server for generating Chinese speech with `edge-tts`.
It defaults to the Microsoft Edge voice `zh-CN-YunxiNeural` with gentle tuning for a lower, steadier sound:

- `voice`: `zh-CN-YunxiNeural`
- `rate`: `-5%`
- `pitch`: `-8Hz`
- `volume`: `+0%`

## Features

- `text_to_speech`: turn text into an MP3 file.
- `text_to_voice_note`: generate an MP3, convert it to OGG/Opus with `ffmpeg`, and optionally send it through Telegram Bot API `sendVoice`.
- stdio MCP support for local clients such as Claude Desktop, Codex, Gemini, and other MCP-compatible tools.
- streamable HTTP MCP support for remote connectors.
- Optional OAuth authorization page for remote MCP connectors. The connection secret is read only from environment variables.
- Optional public media URLs when `TTS_PUBLIC_BASE_URL` is configured.

## Requirements

- Python 3.11 or newer
- `ffmpeg` available on `PATH` for `text_to_voice_note`
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
