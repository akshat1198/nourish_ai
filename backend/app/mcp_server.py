"""MCP server (Stage 4.1, INT-02) — the tool registry over stdio.

Auto-exposes the SAME five tools the Stage-3 agent uses (app.agent.tools.TOOLS)
to any MCP client (Claude Desktop, the MCP inspector). This is an EDGE ADAPTER:
internal callers keep calling the plain Python functions; nothing is rerouted
through MCP. stdio transport only, no auth (local dev tool).

Runs on the same 3.12 venv as the app (needs the DB up for the tools to query):
    cd backend && ../.venv/bin/python -m app.mcp_server
See MCP.md for the Claude Desktop config.
"""
from __future__ import annotations

import asyncio
import json

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from app.agent.tools import TOOLS, call_tool
from app.db import SessionLocal

server = Server("nourishai")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name=t.name, description=t.description, inputSchema=t.input_schema)
        for t in TOOLS.values()
    ]


@server.call_tool()
async def handle_call(name: str, arguments: dict | None) -> list[types.TextContent]:
    # call_tool is synchronous (DB + optionally the embedder); run it off the
    # event loop so the stdio transport isn't blocked.
    def _run():
        with SessionLocal() as session:
            return call_tool(session, name, arguments or {})

    try:
        result = await asyncio.to_thread(_run)
    except KeyError:
        result = {"error": f"unknown tool: {name}"}
    except Exception as e:  # surface tool errors to the client, don't crash
        result = {"error": str(e)}
    return [types.TextContent(type="text", text=json.dumps(result))]


async def _main() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
