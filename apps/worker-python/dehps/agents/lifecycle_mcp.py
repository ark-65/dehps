from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from mcp import types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from dehps.agents.lifecycle_adapter import (
    TOOL_INPUT_SCHEMAS,
    TOOL_NAMES,
    AgentLifecycleAdapter,
)
from dehps.agents.repository import AgentRequestRepository

SERVER_NAME = "dehps-lifecycle"
SERVER_VERSION = "1.0.0"
SERVER_INSTRUCTIONS = (
    "Project-scoped typed Agent Request lifecycle only. No shell, SQL, filesystem, "
    "git, supervisor, workload, artifact, hypothesis, promotion, P3, or P4 capability."
)

TOOL_DESCRIPTIONS = {
    TOOL_NAMES[0]: "Read auditable request, decision, and execution metadata under provenance boundaries.",
    TOOL_NAMES[1]: "Create one typed draft through AgentRequestService and authority policy.",
    TOOL_NAMES[2]: "Submit a caller-owned draft for review.",
    TOOL_NAMES[3]: "Begin independent Reviewer review of a submitted request.",
    TOOL_NAMES[4]: "Approve a request currently under review.",
    TOOL_NAMES[5]: "Reject a request currently under review.",
    TOOL_NAMES[6]: "Start one approved execution after execution-time reauthorization.",
    TOOL_NAMES[7]: "Complete the recorded running execution using write-only result inputs.",
    TOOL_NAMES[8]: "Fail the recorded running execution using a write-only error input.",
}


def build_server(
    adapter_factory: Callable[[], AgentLifecycleAdapter] | None = None,
) -> Server[Any]:
    factory = adapter_factory or (
        lambda: AgentLifecycleAdapter(AgentRequestRepository())
    )
    server: Server[Any] = Server(
        SERVER_NAME,
        version=SERVER_VERSION,
        instructions=SERVER_INSTRUCTIONS,
    )

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name=name,
                description=TOOL_DESCRIPTIONS[name],
                inputSchema=TOOL_INPUT_SCHEMAS[name],
                annotations=types.ToolAnnotations(
                    readOnlyHint=name == TOOL_NAMES[0],
                    destructiveHint=False,
                    idempotentHint=name == TOOL_NAMES[0],
                    openWorldHint=False,
                ),
            )
            for name in TOOL_NAMES
        ]

    @server.call_tool(validate_input=True)
    async def call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in TOOL_INPUT_SCHEMAS:
            raise ValueError(f"unknown lifecycle tool: {name}")
        return factory().call(name, arguments)

    return server


async def _run() -> None:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=SERVER_VERSION,
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
                instructions=SERVER_INSTRUCTIONS,
            ),
        )


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
