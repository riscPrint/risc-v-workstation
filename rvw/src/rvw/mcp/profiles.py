"""Small tool sets and workflow selection, shared by CLI and registry."""
PROFILES = {
    "core": {"agent", "doctor", "init"},
    "verification": {"regress", "cosim", "csr", "privilege",
                     "memory", "verification", "checks", "sec", "fault"},
    "formal": {"formal"},
    "arch": {"arch", "csim", "ooo", "workloads", "perf", "sample"},
    "debug": {"wave", "query", "trace", "debug", "bundle", "reduce", "bisect", "lsp", "replay"},
    "soc": {"soc", "sim", "server", "lint", "probes"},
}


# These are the bring-up workflow's cross-package calls.
CORE_CALLS = {'cosim_check', 'query_build_db', 'regress_gate', 'regress_list', 'regress_run'}


def profile_for(name):
    if name in CORE_CALLS or name.startswith(("job_", "rvw_tools_")):
        return "core"
    prefix = name.removeprefix("rvw_").split("_", 1)[0]
    return next((p for p, packages in PROFILES.items() if prefix in packages), "all")


def workflow_names(workflow):
    from rvw.agent.guide import load, select
    workflows = select(load(), workflow)["workflows"]
    return ({s["mcp"]["tool"] for w in workflows for s in w["steps"] if s.get("mcp")}
            | {name for w in workflows for name in w.get('tools', [])})


def select_tools(tools, profile="all", workflow=None):
    names = workflow_names(workflow) if workflow else None
    return [t for t in tools if (profile == "all" or profile_for(t.name) in ("core", profile))
            and (names is None or t.name in names or profile_for(t.name) == "core")]


def describe(tool):
    return {"name": tool.name, "description": tool.description,
            "profile": profile_for(tool.name), "input_schema": tool.input_schema,
            "long": tool.long, "side_effects": tool.side_effects,
            "native_tools": tool.native_tools}
