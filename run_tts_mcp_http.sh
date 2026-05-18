#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -n "${TTS_MCP_OAUTH_CONNECT_SECRET:-}" ]; then
  export MCP_OAUTH_CONNECT_SECRET="$TTS_MCP_OAUTH_CONNECT_SECRET"
fi

export TTS_OUTPUT_DIR="${TTS_OUTPUT_DIR:-$SCRIPT_DIR/output}"
export TTS_TELEGRAM_BOT_TOKEN_ENV="${TTS_TELEGRAM_BOT_TOKEN_ENV:-TTS_TELEGRAM_BOT_TOKEN}"
export MCP_HOST="${MCP_HOST:-127.0.0.1}"
export MCP_PORT="${MCP_PORT:-8891}"
export MCP_ALLOWED_HOSTS="${MCP_ALLOWED_HOSTS:-127.0.0.1,localhost}"
export MCP_ALLOWED_ORIGINS="${MCP_ALLOWED_ORIGINS:-http://127.0.0.1:$MCP_PORT,http://localhost:$MCP_PORT}"
export MCP_OAUTH_ENABLED="${MCP_OAUTH_ENABLED:-0}"
export MCP_OAUTH_STORE="${MCP_OAUTH_STORE:-$SCRIPT_DIR/oauth_store.json}"

if [ -n "${TTS_PUBLIC_BASE_URL:-}" ]; then
  export MCP_OAUTH_ISSUER_URL="${MCP_OAUTH_ISSUER_URL:-$TTS_PUBLIC_BASE_URL}"
  export MCP_OAUTH_RESOURCE_URL="${MCP_OAUTH_RESOURCE_URL:-$TTS_PUBLIC_BASE_URL/mcp}"
fi

mkdir -p "$TTS_OUTPUT_DIR"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON:-$SCRIPT_DIR/.venv/bin/python}"
exec "$PYTHON_BIN" tts_mcp_server.py --transport streamable-http
