"""Load a profile into a running MCP server without a restart."""
import json
import os
import sys
import anyio
import pytest
from rvw.mcp.registry import Registry, ToolError
from rvw.mcp.spec import ToolSpec, schema

pytestmark = pytest.mark.fast


def tool(name):
    return ToolSpec(name, name, schema({}, []), lambda: {"ok": name}, side_effects="read-only", native_tools=())


def test_load_profile_adds_only_new_tools_and_refuses_unknown():
    r = Registry([tool("cov_report"), tool("query_drivers"), tool("agent_guide")], profile="core")
    assert "cov_report" not in r.tools and "agent_guide" in r.tools
    assert r.load_profile("verification") == ["cov_report"]
    assert r.load_profile("verification") == []
    assert r.call("cov_report", {}) == {"ok": "cov_report"}
    out = json.loads(r.call_json("rvw_tools_load", {"profile": "debug"})[0])
    assert out["added"] == ["query_drivers"] or out.get("data", {}).get("added") == ["query_drivers"]
    with pytest.raises(ToolError, match="unknown profile"):
        r.load_profile("nope")


def test_stdio_core_profile_loads_verification_and_notifies():
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=["-m", "rvw", "mcp", "--profile", "core"],
                                   env=dict(os.environ))
    seen = []

    async def on_message(message):
        seen.append(getattr(getattr(message, "root", message), "method", None) or type(message).__name__)

    async def session():
        async with stdio_client(params) as streams:
            async with ClientSession(streams[0], streams[1], message_handler=on_message) as s:
                init = await s.initialize()
                caps = init.capabilities.tools
                assert caps and (getattr(caps, "list_changed", None) or getattr(caps, "listChanged", None))
                before = {t.name for t in (await s.list_tools()).tools}
                assert "rvw_tools_load" in before and "cov_report" not in before
                await s.call_tool("rvw_tools_load", {"profile": "verification"})
                after = {t.name for t in (await s.list_tools()).tools}
                assert "cov_report" in after and "cosim_check" in after
    anyio.run(session)
    assert any("tools/list_changed" in str(m) or "ToolListChanged" in str(m) for m in seen), seen
