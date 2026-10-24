"""The MCP server over stdio. Works with the `mcp` SDK 1.x (decorator handlers) and 2.x (constructor
handlers); tool calls run in a worker thread so a slow query does not block the session."""
from __future__ import annotations

import inspect

import anyio

from .registry import Registry

INSTRUCTIONS = (
    "RISC-V Workstation tools. Design questions (what drives a signal, what reads it, paths between "
    "signals, hierarchy, registers, what an edit changed) go to the query_* tools, which read a SpinalDB "
    "design database (argument `db`, default $RVW_DESIGNDB). Names may be Verilog paths, waveform paths "
    "(TOP.<top>....) or Spinal paths (bundle fields, Areas, Vec indexes). Long-running tools return a "
    "job_id: poll job_status (wait_s blocks up to 60 s)."
)


def build_server(registry: Registry):
    from mcp import types
    from mcp.server.lowlevel import Server

    def tool_list():
        out = []
        for t in registry.tools.values():
            kw = {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            if t.annotations:
                kw["annotations"] = types.ToolAnnotations(**t.annotations)
            out.append(types.Tool(**kw))
        return out

    async def run_tool(name: str, arguments: dict | None):
        return await anyio.to_thread.run_sync(registry.call_json, name, arguments)

    def result(text, structured, is_error):
        kw = {"content": [types.TextContent(type="text", text=text)], "isError": is_error}
        if structured is not None:
            kw["structuredContent"] = structured
        return types.CallToolResult(**kw)

    params = inspect.signature(Server.__init__).parameters
    if "on_call_tool" in params:  # SDK 2.x
        async def on_list_tools(ctx, params):
            return types.ListToolsResult(tools=tool_list())

        async def on_call_tool(ctx, params):
            return result(*await run_tool(params.name, params.arguments))

        return Server("rvw", instructions=INSTRUCTIONS, on_list_tools=on_list_tools, on_call_tool=on_call_tool)

    server = Server("rvw", instructions=INSTRUCTIONS) if "instructions" in params else Server("rvw")  # SDK 1.x

    @server.list_tools()
    async def _list_tools():
        return tool_list()

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        text, structured, is_error = await run_tool(name, arguments)
        if is_error:
            raise RuntimeError(text)  # 1.x turns exceptions into isError results
        return [types.TextContent(type="text", text=text)]

    return server


async def serve_stdio(registry: Registry) -> None:
    from mcp.server.stdio import stdio_server

    server = build_server(registry)
    try:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        registry.jobs.shutdown()
