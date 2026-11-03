from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler
from .dashboard import dashboard


def execute_json(hosts, manifest, adapter, identity_command, identity, out, jobs=1, timeout=600):
    from .executor import execute
    return execute(hosts, manifest, adapter, identity_command, identity, out, jobs=jobs, timeout=timeout)


def mcp_tools():
    string = {"type": "string"}
    array = {"type": "array", "items": string, "minItems": 1}
    return [ToolSpec("farm_run", "Run native SSH shards. Complete is transport completeness, not a gate verdict.",
        schema({"hosts": {"type": "array", "items": {"type": "object"}, "minItems": 1},
                "manifest": string, "adapter": array, "identity_command": array,
                "identity": {"type": "object"}, "out": string,
                "jobs": {"type": "integer", "minimum": 1}, "timeout": {"type": "number", "exclusiveMinimum": 0}},
               ["hosts", "manifest", "adapter", "identity_command", "identity", "out"]),
        handler("rvw.farm.mcp_tools"), long=True)]
