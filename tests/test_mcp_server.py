from __future__ import annotations

import pytest

from plainweave.mcp_surface import MCP_RESOURCE_URIS, MCP_TOOL_METADATA


@pytest.mark.anyio
async def test_fastmcp_server_registers_agentic_read_surface() -> None:
    from plainweave.mcp_server import create_mcp_server

    server = create_mcp_server()

    tools = await server.list_tools()
    resources = await server.list_resources()

    assert {tool.name for tool in tools} == set(MCP_TOOL_METADATA)
    assert {str(resource.uri) for resource in resources} == set(MCP_RESOURCE_URIS)
    for tool in tools:
        assert "read" in (tool.description or "").lower() or "list" in (tool.description or "").lower()
