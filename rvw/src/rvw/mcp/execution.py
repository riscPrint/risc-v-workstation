"""Job migration for blocking providers. Existing long handlers remain intact."""
from dataclasses import replace

# Providers with potentially large file scans or native operations.
BACKGROUND_TOOLS = {"sim_checkpoint", "sim_resume", "sim_suffix_check", "csim_convert", "soc_audit"}


def use_background(tool):
    return ((not tool.long and tool.name in BACKGROUND_TOOLS)
            or (tool.long and not tool.wants_job
                and getattr(tool.handler, "__module__", "").startswith("rvw.")))



def run_discovered(tool_name, arguments, provider=None):
    if provider is not None:
        from .lazy import resolve
        return resolve(provider, tool_name).handler(**arguments)
    # Resolve closures in the worker from the provider rather than pickling them.
    from .registry import discover
    tools, problems = discover()
    tool = next((t for t in tools if t.name == tool_name), None)
    if tool is None:
        raise ValueError(f"tool {tool_name} disappeared: {problems}")
    return tool.handler(**arguments)


def prepare(tool):
    if not use_background(tool):
        return tool
    def execute(job, **arguments):
        from .worker import run_function
        return run_function(job, __name__, "run_discovered",
                            {"tool_name": tool.name, "arguments": arguments,
                             "provider": getattr(tool, "_rvw_provider", None)})
    return replace(tool, handler=execute, long=True)
