from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


BASE_DIR = Path(__file__).resolve().parent


async def main() -> None:
    python_bin = os.getenv("PYTHON")
    if not python_bin:
        if sys.platform.startswith("win"):
            python_bin = str(BASE_DIR / ".venv" / "Scripts" / "python.exe")
        else:
            python_bin = str(BASE_DIR / ".venv" / "bin" / "python")
    if not Path(python_bin).exists():
        python_bin = shutil.which("python") or sys.executable

    params = StdioServerParameters(
        command=python_bin,
        args=[str(BASE_DIR / "tts_mcp_server.py")],
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", ", ".join(tool.name for tool in tools.tools))

            result = await session.call_tool(
                "text_to_speech",
                {
                    "text": "你好，我是云希。MCP 测试成功。",
                    "filename": "mcp-smoke.mp3",
                },
            )
            print(json.dumps(result.model_dump(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
