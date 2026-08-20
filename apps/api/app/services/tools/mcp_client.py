"""Thin client over external MCP servers (SSE or Streamable HTTP transport).

HTTP handlers are stateless, so a session is opened per operation: connect,
initialize, act, close. Tool lists used at chat time come from the row's
cached_tools column (refreshed on save/test-connection), never from a live
list_tools call.
"""

import asyncio
import json
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from ...models import AgentTool
from ...security import decrypt_secret

CONNECT_TIMEOUT_SECONDS = 20
CALL_TIMEOUT_SECONDS = 60


@asynccontextmanager
async def open_mcp_session(url: str, transport: str, headers: dict[str, str] | None):
    if transport == "sse":
        async with sse_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    else:
        async with streamablehttp_client(url, headers=headers) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def discover_mcp_tools(url: str, transport: str, headers: dict[str, str] | None) -> list[dict]:
    """Connect and list the server's tools. Raises on failure — callers turn
    that into a 502 (create/test-connection must not save unreachable servers)."""

    async def _discover() -> list[dict]:
        async with open_mcp_session(url, transport, headers) as session:
            result = await session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema or {"type": "object", "properties": {}},
                }
                for tool in result.tools
            ]

    return await asyncio.wait_for(_discover(), CONNECT_TIMEOUT_SECONDS)


async def call_mcp_tool(tool: AgentTool, tool_name: str, args: dict) -> tuple[str, bool]:
    """Proxy a tool call to the MCP server. Never raises: failures become
    (error_text, True) handed back to the LLM."""
    headers = None
    if tool.encrypted_headers:
        try:
            headers = json.loads(decrypt_secret(tool.encrypted_headers))
        except Exception:
            return "Error: the server's stored headers could not be decrypted", True
    try:
        async def _call():
            async with open_mcp_session(tool.url, tool.transport, headers) as session:
                return await session.call_tool(tool_name, args)

        result = await asyncio.wait_for(_call(), CALL_TIMEOUT_SECONDS)
    except Exception as exc:
        return f"Error: MCP call failed ({type(exc).__name__})", True

    parts = [block.text for block in result.content if getattr(block, "type", "") == "text"]
    text = "\n".join(parts).strip() or "(empty result)"
    return text, bool(result.isError)
