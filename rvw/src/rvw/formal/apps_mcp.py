"""MCP entry points for formal apps and proof coverage."""
from rvw.mcp.spec import ToolSpec

def mcp_tools():
    from .mcp_tools import ToolSpec, schema, S, I, B, _runner
    return [
        ToolSpec("formal_app_live", "Reduce fair response liveness to a full-state lasso safety check.", schema({"manifest": S, "out": S, "depth": I, "engine": S, "timeout": {"type": "number"}, "mode": S}, ["manifest", "out"]), _runner("app-live"), long=True),
        ToolSpec("formal_recheck", "Bounded solver what-if over a captured model with pinned signals and full-depth feasibility.",
                 schema({"result": S, "pin": {"type": "array", "items": S, "minItems": 1},
                         "out": S, "depth": I, "engine": S,
                         "timeout": {"type": "number", "exclusiveMinimum": 0}}, ["result", "pin", "out"]),
                 _runner("recheck"), long=True),
        ToolSpec("formal_autocheck", "Check per-bit constants, declared dead code and FSM coverage. Optional output X propagation.",
                 schema({"manifest": S, "out": S, "db": S, "kind": {"type": "array", "items": S}, "max_properties": I, "depth": I,
                         "engine": S, "timeout": {"type": "number", "exclusiveMinimum": 0},
                         "mode": {**S, "enum": ["bmc", "prove"]}, "xprop": B}, ["manifest", "out"]),
                 _runner("autocheck"), long=True),
        ToolSpec("formal_apps", "Run reviewed connectivity, CSR, bounded progress, UNR and FSM monitor contracts.",
                 schema({"manifest": S, "out": S, "depth": I, "engine": S,
                         "timeout": {"type": "number", "exclusiveMinimum": 0},
                         "mode": {**S, "enum": ["bmc", "prove"]}, "event_model": B, "async_reset": B},
                        ["manifest", "out"]), _runner("apps"), long=True),


        ToolSpec("formal_testplan", "Join a formal inventory with captured proof, core, activation and mutation evidence. JSON and HTML.",
                 schema({"manifest": S, "out": S}, ["manifest", "out"]), _runner("testplan"), long=True),

        ToolSpec("formal_shortest", "Search increasing BMC depths for the sole captured assertion. Unknown depths cannot certify minimality.",
                 schema({"result": S, "out": S, "max_depth": I, "timeout": {"type": "number", "exclusiveMinimum": 0}, "engine": S}, ["result", "out"]), _runner("shortest"), long=True),
        ToolSpec("formal_proof_core", "Extract a deletion-minimal solver core for one named SMT query. Not an RTL proof.",
                 schema({"smt2": S, "mapping": S, "result": S, "depth": I, "property": S, "db": S, "solver": S,
                         "timeout": {"type": "number", "exclusiveMinimum": 0}, "out": S},
                        ["out"]), _runner("proof-core"), long=True),
        ToolSpec("formal_cex", "Replay a captured failing BMC witness with edited inputs through Yosys sim. Not a proof.",
                 schema({"result": S, "out": S, "trace_index": I,
                         "edit": {"type": "array", "items": S},
                         "hgldd": S, "pdg": S, "criterion": S, "at_time": I, "open": B,
                         "minimize": B, "max_checks": I, "emit_testbench": B, "db": S, "signal": S,
                         "timeout": {"type": "number", "exclusiveMinimum": 0}}, ["result", "out"]),
                 _runner("cex"), long=True),
    ]
