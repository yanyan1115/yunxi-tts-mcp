#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export TTS_OUTPUT_DIR="${TTS_OUTPUT_DIR:-$SCRIPT_DIR/output}"
export TTS_TELEGRAM_BOT_TOKEN_ENV="${TTS_TELEGRAM_BOT_TOKEN_ENV:-TTS_TELEGRAM_BOT_TOKEN}"

mkdir -p "$TTS_OUTPUT_DIR"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON:-$SCRIPT_DIR/.venv/bin/python}"
exec "$PYTHON_BIN" tts_mcp_server.py "$@"
