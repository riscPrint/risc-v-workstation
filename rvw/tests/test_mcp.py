import json
import os
import sys
import textwrap
import time
from pathlib import Path

import anyio
import pytest

from rvw.mcp.jobs import JobManager
from rvw.mcp.registry import Registry, discover
from rvw.mcp.spec import ToolSpec, schema


ADDED_TOOLS = {
    "regress_list", "regress_run", "regress_compare", "regress_gate", "regress_history",
    "regress_known_list", "regress_known_add", "regress_known_remove", "cosim_check", "cosim_generate",
    "cov_merge", "cov_report", "cov_rank", "cov_select", "cov_functional", "cov_prove", "cov_mutate",
    "perf_report", "perf_compare",
    "wave_info", "wave_list", "wave_changes", "wave_sample", "wave_cut",
    "bundle_make", "reduce_run", "bisect_run",
}


# ------------------------------------------------------------------------------------------- registry
def test_discovery_finds_query_and_job_tools():
    tools, problems = discover()
    names = {t.name for t in tools}
    assert {"query_drivers", "query_path", "query_diff", "query_build_db"} <= names
    assert ADDED_TOOLS <= names
    assert not problems
    reg = Registry(tools)
    assert {"job_status", "job_log", "job_cancel", "job_list"} <= set(reg.tools)
    for t in reg.tools.values():
        assert t.input_schema["type"] == "object" and t.description


def test_registry_call_and_errors(cluster_db):
    reg, _ = Registry.discover()
    text, data, err = reg.call_json("query_drivers", {"db": str(cluster_db), "signal": "units_0.x"})
    assert not err and data["signal"]["path"] == "units_0.x"
    text, data, err = reg.call_json("query_where", {"db": str(cluster_db), "signal": "x"})
    assert err and "ambiguous" in data["error"] and "units_0.x" in data["candidates"]
    text, data, err = reg.call_json("query_where", {"db": str(cluster_db), "bogus": 1})
    assert err and "bad arguments" in data["error"]
    text, data, err = reg.call_json("no_such_tool", {})
    assert err


def test_duplicate_tool_names_rejected():
    t = ToolSpec("x_y", "d", schema({}), lambda: 1)
    with pytest.raises(ValueError):
        Registry([t, t])


def test_long_job_lifecycle():
    def slow(n: int, job):
        for i in range(n):
            job.log(f"step {i}")
            job.check()
            time.sleep(0.01)
        return {"done": n}

    def sub(job):
        job.run([sys.executable, "-c", "import time; print('started', flush=True); time.sleep(30)"])
        return {"never": True}

    reg = Registry([ToolSpec("t_slow", "slow", schema({"n": {"type": "integer"}}), slow, long=True),
                    ToolSpec("t_sub", "sub", schema({}), sub, long=True)], JobManager())
    j = reg.call("t_slow", {"n": 5})
    st = reg.call("job_status", {"job_id": j["job_id"], "wait_s": 10})
    assert st["status"] == "done" and st["result"] == {"done": 5} and "step 4" in st["log_tail"]
    j2 = reg.call("t_sub", {})
    for _ in range(100):
        if "started" in reg.call("job_log", {"job_id": j2["job_id"]})["lines"]:
            break
        time.sleep(0.05)
    t0 = time.time()
    c = reg.call("job_cancel", {"job_id": j2["job_id"]})
    assert c["status"] == "cancelled" and time.time() - t0 < 5
    assert {x["job_id"] for x in reg.call("job_list", {})["jobs"]} == {j["job_id"], j2["job_id"]}


# ------------------------------------------------------------------------------------------- MCP over stdio
PLUGIN = textwrap.dedent('''
    import time
    from rvw.mcp.spec import ToolSpec, schema

    def _count(n, job):
        for i in range(n):
            job.log(f"tick {i}")
            time.sleep(0.02)
        return {"counted": n}

    def mcp_tools():
        return [ToolSpec("plugin_count", "count slowly", schema({"n": {"type": "integer"}}, ["n"]), _count, long=True)]
''')


def test_mcp_stdio_session(cluster_db, gcd_db, buggy_db, tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    (tmp_path / "rvw_test_plugin.py").write_text(PLUGIN)
    env = {**os.environ, "RVW_DESIGNDB": str(cluster_db), "RVW_MCP_PLUGINS": "rvw_test_plugin",
           "PYTHONPATH": os.pathsep.join([str(tmp_path), os.environ.get("PYTHONPATH", "")])}
    params = StdioServerParameters(command=sys.executable, args=["-m", "rvw", "mcp"], env=env)

    def is_error(res):  # SDK 2.x field name, 1.x name
        return getattr(res, "is_error", None) if hasattr(res, "is_error") else res.isError

    def payload(res):
        assert res.content and res.content[0].type == "text"
        return json.loads(res.content[0].text)

    async def session():
        async with stdio_client(params) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as s:
                await s.initialize()
                names = {t.name for t in (await s.list_tools()).tools}
                assert {"query_drivers", "query_fanin", "job_status", "plugin_count"} | ADDED_TOOLS <= names

                r = await s.call_tool("query_drivers", {"signal": "TOP.GcdCluster.units_1.x"})
                assert not is_error(r)
                d = payload(r)
                assert d["register"]["reset"]["value"] == "0" and len(d["assignments"]) == 2

                r = await s.call_tool("query_path", {"a": "io.cmd", "b": "io_rsp_payload", "data_only": True})
                assert payload(r)["found"]

                r = await s.call_tool("query_diff", {"old": str(gcd_db), "new": str(buggy_db)})
                assert [c["path"] for c in payload(r)["assignments"]["changed"]] == ["x"]

                r = await s.call_tool("query_where", {"signal": "x"})
                assert is_error(r) and "ambiguous" in r.content[0].text

                r = await s.call_tool("query_path", {"a": "io.cmd", "b": "io_rsp_payload", "data_only": "false"})
                assert is_error(r) and "data_only" in r.content[0].text

                r = await s.call_tool("plugin_count", {"n": 5})
                job = payload(r)["job_id"]
                r = await s.call_tool("job_status", {"job_id": job, "wait_s": 20})
                st = payload(r)
                assert st["status"] == "done" and st["result"] == {"counted": 5}

    anyio.run(session)


def test_mcp_list_without_sdk_needed(capsys):
    from rvw.cli import main
    assert main(["mcp", "--list", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert any(t["name"] == "query_build_db" and t["long"] for t in out["tools"])
