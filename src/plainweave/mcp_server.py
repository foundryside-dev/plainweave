from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from plainweave.mcp_surface import MCP_RESOURCE_URIS, PlainweaveMcpSurface


def create_mcp_server(surface: PlainweaveMcpSurface | None = None) -> FastMCP:
    active_surface = surface or PlainweaveMcpSurface()
    mcp = FastMCP("plainweave", json_response=True)

    @mcp.tool()
    def plainweave_project_context_get(include_contracts: bool = False) -> dict[str, Any]:
        """Read local Plainweave project context, capabilities, and authority boundaries. This tool is read-only."""
        return active_surface.plainweave_project_context_get(include_contracts=include_contracts)

    @mcp.tool()
    def plainweave_requirement_search(
        query: str | None = None,
        status_filter: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Search local Plainweave requirements. This read-only tool preserves requirement authority state."""
        return active_surface.plainweave_requirement_search(
            query=query,
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )

    @mcp.tool()
    def plainweave_requirement_get(requirement_id: str) -> dict[str, Any]:
        """Read one local Plainweave requirement without collapsing active drafts into approved truth."""
        return active_surface.plainweave_requirement_get(requirement_id)

    @mcp.tool()
    def plainweave_requirement_dossier_get(requirement_id: str) -> dict[str, Any]:
        """Read the local computed requirement dossier. No live peer calls are made in P0."""
        return active_surface.plainweave_requirement_dossier_get(requirement_id)

    @mcp.tool()
    def plainweave_trace_link_list(
        requirement_id: str | None = None,
        state_filter: str | None = None,
        relation_filter: str | None = None,
        direction: str = "both",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List local trace links while preserving trace state, authority, and freshness."""
        return active_surface.plainweave_trace_link_list(
            requirement_id=requirement_id,
            state_filter=state_filter,
            relation_filter=relation_filter,
            direction=direction,
            limit=limit,
            offset=offset,
        )

    @mcp.tool()
    def plainweave_baseline_list(limit: int = 25, offset: int = 0) -> dict[str, Any]:
        """List local immutable Plainweave baselines. This tool is read-only."""
        return active_surface.plainweave_baseline_list(limit=limit, offset=offset)

    @mcp.tool()
    def plainweave_baseline_get(baseline_id: str) -> dict[str, Any]:
        """Read one local immutable Plainweave baseline snapshot."""
        return active_surface.plainweave_baseline_get(baseline_id)

    @mcp.tool()
    def plainweave_baseline_diff(baseline_id: str) -> dict[str, Any]:
        """Read local baseline drift facts. This tool does not make release-readiness decisions."""
        return active_surface.plainweave_baseline_diff(baseline_id)

    @mcp.tool()
    def plainweave_verification_status_get(requirement_id: str) -> dict[str, Any]:
        """Read derived local verification status with reason codes and evidence freshness."""
        return active_surface.plainweave_verification_status_get(requirement_id)

    @mcp.tool()
    def plainweave_verification_status_list(status_filter: str, limit: int = 25, offset: int = 0) -> dict[str, Any]:
        """List local unverified or stale verification statuses. This tool records no evidence."""
        return active_surface.plainweave_verification_status_list(
            status_filter=status_filter, limit=limit, offset=offset
        )

    def register_resource(uri: str) -> None:
        @mcp.resource(uri)
        def plainweave_resource() -> str:
            """Read stable Plainweave MCP resource content."""
            return json.dumps(active_surface.read_resource(uri))

    for uri in MCP_RESOURCE_URIS:
        register_resource(uri)

    return mcp


def main() -> None:
    create_mcp_server().run()


if __name__ == "__main__":
    main()
