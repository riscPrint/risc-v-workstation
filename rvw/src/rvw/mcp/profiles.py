"""Small tool sets and workflow selection, shared by CLI and registry."""
PROFILES = {
    "core": {"agent", "doctor", "init", "plan", "evidence"},
    "verification": {"regress", "cosim", "cov", "stimulus", "csr", "privilege",
                     "memory", "verification", "verification_plan", "uvm", "vip", "checks", "sec", "fault"},
    "formal": {"formal", "equiv", "connectivity"},
    "arch": {"arch", "csim", "ooo", "workloads", "perf"},
    "debug": {"wave", "query", "trace", "debug", "bundle", "reduce", "bisect", "bugmem", "lsp"},
    "soc": {"soc", "sim", "server", "farm", "lint", "probes"},
}


def profile_for(name):
    if name.startswith(("job_", "rvw_tools_")):
        return "core"
    prefix = name.removeprefix("rvw_").split("_", 1)[0]
    return next((p for p, packages in PROFILES.items() if prefix in packages), "all")


def workflow_names(workflow):
    from rvw.agent.guide import load, select
    return {s["mcp"]["tool"] for w in select(load(), workflow)["workflows"]
            for s in w["steps"] if s.get("mcp")}


def select_tools(tools, profile="all", workflow=None):
    names = workflow_names(workflow) if workflow else None
    return [t for t in tools if (profile == "all" or profile_for(t.name) in ("core", profile))
            and (names is None or t.name in names or profile_for(t.name) == "core")]


def describe(tool):
    return {"name": tool.name, "description": tool.description,
            "profile": profile_for(tool.name), "input_schema": tool.input_schema,
            "long": tool.long, "side_effects": tool.side_effects,
            "native_tools": tool.native_tools}
