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
    "(TOP.<top>....) or Spinal paths (bundle fields, Areas, Vec indexes). For workflows, start with agent_guide or the resource rvw://agent/guide. "
    "Long-running tools return a "
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

    def resource_list():
        return [types.Resource(uri=uri, name=name, description=description, mimeType="application/json")
                for uri, (name, description, _) in registry.resources.items()]

    def resource_text(uri):
        return registry.read_resource(str(uri))

    params = inspect.signature(Server.__init__).parameters
    if "on_call_tool" in params:  # SDK 2.x
        async def on_list_tools(ctx, params):
            return types.ListToolsResult(tools=tool_list())

        async def on_call_tool(ctx, params):
            text, structured, is_error = await run_tool(params.name, params.arguments)
            out = result(text, structured, is_error)
            if params.name == "rvw_tools_load" and not is_error:
                await ctx.session.send_tool_list_changed()
            return out

        async def on_list_resources(ctx, params):
            return types.ListResourcesResult(resources=resource_list())

        async def on_read_resource(ctx, params):
            return types.ReadResourceResult(contents=[types.TextResourceContents(
                uri=params.uri, mimeType="application/json", text=resource_text(params.uri))])

        kw = {}
        if registry.resources:
            kw = {"on_list_resources": on_list_resources, "on_read_resource": on_read_resource}
        return Server("rvw", instructions=INSTRUCTIONS, on_list_tools=on_list_tools, on_call_tool=on_call_tool, **kw)

    server = Server("rvw", instructions=INSTRUCTIONS) if "instructions" in params else Server("rvw")  # SDK 1.x

    @server.list_tools()
    async def _list_tools():
        return tool_list()

    if registry.resources:
        @server.list_resources()
        async def _list_resources():
            return resource_list()

        @server.read_resource()
        async def _read_resource(uri):
            return resource_text(uri)

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict):
        text, structured, is_error = await run_tool(name, arguments)
        if is_error:
            raise RuntimeError(text)  # 1.x turns exceptions into isError results
        if name == "rvw_tools_load":
            await server.request_context.session.send_tool_list_changed()
        return [types.TextContent(type="text", text=text)]

    return server


async def serve_stdio(registry: Registry) -> None:
    from mcp.server.stdio import stdio_server

    server = build_server(registry)
    try:
        async with stdio_server() as (read, write):
            from mcp.server.lowlevel import NotificationOptions
            await server.run(read, write, server.create_initialization_options(NotificationOptions(tools_changed=True)))
    finally:
        registry.jobs.shutdown()
