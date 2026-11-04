from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler
from .dashboard import dashboard


def execute_json(hosts=None, manifest=None, adapter=None, identity_command=None, identity=None, out=None, jobs=1, timeout=600, action=None):
    if action == "recover":
        from .executor import recover
        return recover(out)
    if action == "cancel":
        return cancel_json(out)
    from .executor import execute
    return execute(hosts, manifest, adapter, identity_command, identity, out, jobs=jobs, timeout=timeout)


def cancel_json(out):
    from .executor import cancel
    return cancel(out)


def mcp_tools():
    string = {"type": "string"}
    array = {"type": "array", "items": string, "minItems": 1}
    return [ToolSpec("farm_run", "Run native SSH shards. Complete is transport completeness, not a gate verdict.",
        schema({"hosts": {"type": "array", "items": {"type": "object"}, "minItems": 1},
                "manifest": string, "adapter": array, "identity_command": array,
                "identity": {"type": "object"}, "out": string,
                "jobs": {"type": "integer", "minimum": 1}, "timeout": {"type": "number", "exclusiveMinimum": 0}},
               ["hosts", "manifest", "adapter", "identity_command", "identity", "out"]),
        handler("rvw.farm.mcp_tools"), long=True),
        ToolSpec("farm_recover", "Read crash checkpoints. Missing final collection stays inconclusive.",
                 schema({"out": string}, ["out"]), handler("rvw.farm.mcp_tools", "recover")),
        ToolSpec("farm_cancel", "Cancel shards and confirm host process-group cleanup.",
                 schema({"out": string}, ["out"]), handler("rvw.farm.mcp_tools", "cancel"), long=True)]
