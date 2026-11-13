"""MCP tools for `rvw formal` (contract C7). Each runs the CLI in a subprocess job, so cancel
stops sby, and returns the flow's result.json, the same JSON `--json` prints.

The CLI clears the previous result under its output lock. Return only a parsed result whose
status agrees with the process exit code. Missing or invalid results are tool errors."""
import json
import sys
from pathlib import Path

from rvw.mcp.spec import ToolError, ToolSpec, schema

S = {"type": "string"}
I = {"type": "integer", "minimum": 0}
B = {"type": "boolean"}
COMMON = {
    "project": {**S, "description": "project file or directory"},
    "verilog": {"type": "array", "items": S, "description": "design Verilog files"},
    "top": S, "out": {**S, "description": "work/result directory"},
    "clock": {**S, "default": "clk"},
    "reset": {**S, "description": "reset input; default `reset` when the toplevel has one"},
    "reset_active": {**S, "enum": ["high", "low"], "default": "high"},
    "checks": {**S, "description": "SpinalChecks report (<top>.checks.json) to name failures by check id and Scala line"},
    "depth": I, "engine": {**S, "description": "sby engine, or a comma-separated parallel portfolio"},
    "timeout": {"type": "number", "minimum": 0},
    "tie": {"type": "array", "items": S, "description": "PORT=VALUE constants for toplevel inputs (all flows; listed in "
            "the result's `restrictions`)"},
}
FLAGS = {"free_reset", "first_failure", "outputs", "payload", "x_inputs", "combinational", "event_model", "async_reset", "open"}


def _argv(command, args):
    argv = [sys.executable, "-m", "rvw", "formal", command]
    for key, value in args.items():
        if value is None or value is False:
            continue
        opt = "--" + key.replace("_", "-")
        if key in FLAGS:
            argv.append(opt)
        elif key == "verilog":
            argv += [opt, *map(str, value)]
        elif isinstance(value, list):
            for v in value:
                argv += [opt, str(v)]
        else:
            argv += [opt, str(value)]
    return argv


def _runner(command):
    def run(job, **args):
        code = job.run(_argv(command, args))
        result = Path(args["out"]) / "result.json"

        def error(why):
            return ToolError(f"rvw formal {command}: {why} (exit {code})",
                             {"exit_code": code, "log_tail": job.tail(30)})
        if code not in (0, 1):
            raise error("failed")
        if not result.is_file():
            raise error("wrote no result")
        try:
            data = json.loads(result.read_text())
        except (OSError, ValueError) as e:
            raise error(f"unreadable result.json: {e}")
        if not isinstance(data, dict):
            raise error("result.json is not an object")
        if (code == 0) != (data.get("status") == "pass"):
            raise error(f"exit code and status {data.get('status')!r} disagree")
        return data
    return run


def _csr(job, **args):
    code = job.run(_argv('csr', args))
    if code:
        raise ToolError('CSR generation failed', {'exit_code': code, 'log_tail': job.tail(20)})
    return json.loads((Path(args['out']) / 'result.json').read_text())


def _template(job, **args):
    from .invariants import NAMES
    if args['kind'] not in NAMES:
        raise ToolError('unknown template kind')
    argv = [sys.executable, '-m', 'rvw', 'formal', 'template', args['kind'], '--out', args['out']]
    for key in ('entries', 'width'):
        if key in args:
            argv += ['--' + key, str(args[key])]
    code = job.run(argv)
    if code:
        raise ToolError('template generation failed', {'exit_code': code, 'log_tail': job.tail(20)})
    return {'status': 'generated', 'out': args['out']}


def mcp_tools():
    return [
        ToolSpec("formal_template", "Generate a project-bound safety monitor. No verification run.",
                 schema({"kind": S, "out": S, "entries": I, "width": I}, ["kind", "out"]),
                 _template, long=True),
        ToolSpec("formal_proof_core", "Extract a deletion-minimal solver core for one named SMT query. Not an RTL proof.",
                 schema({"smt2": S, "mapping": S, "db": S, "solver": S,
                         "timeout": {"type": "number", "exclusiveMinimum": 0}, "out": S},
                        ["smt2", "mapping", "out"]), _runner("proof-core"), long=True),
        ToolSpec("formal_csr", "Generate CSR monitors, directed assembly and coverage. Does not run verification.",
                 schema({"model": S, "out": S}, ["model", "out"]), _csr, long=True),
        ToolSpec("formal_cex", "Replay a captured failing BMC witness with edited inputs through Yosys sim. Not a proof.",
                 schema({"result": S, "out": S, "trace_index": I,
                         "edit": {"type": "array", "items": S},
                         "hgldd": S, "pdg": S, "criterion": S, "at_time": I, "open": B,
                         "timeout": {"type": "number", "exclusiveMinimum": 0}}, ["result", "out"]),
                 _runner("cex"), long=True),
        ToolSpec("formal_bmc", "Bounded model check of a design's assertions from reset (SymbiYosys). Use for shallow "
                 "bugs; failures are named by SpinalChecks id and Scala line when `checks` is given. Runs as a job.",
                 schema({**COMMON, "reset_cycles": I, "free_reset": B, "first_failure": B,
                         "clock_schedule": {"type": "array", "items": S},
                         "event_model": B, "event_clock": {"type": "array", "items": S}, "async_reset": B}, ["out"]),
                 _runner("bmc"), long=True),
        ToolSpec("formal_from_sim", "Bounded model check starting from cycle N (or time T) of a Verilator FST/VCD of the "
                 "same Verilog: finds bugs too deep for BMC from reset. Memories come from the trace by default. Runs as a job.",
                 schema({**COMMON, "trace": S, "cycle": I, "time": I, "scope": S,
                         "memories": {**S, "enum": ["trace", "free", "zero"]}, "first_failure": B},
                        ["out", "trace"]),
                 _runner("from-sim"), long=True),
        ToolSpec("formal_x_sweep", "Bounded per-module X inventory with native Icarus replay. Not an acceptance gate.",
                 schema({**COMMON, "module": {"type": "array", "items": S},
                         "module_timeout": {"type": "number", "exclusiveMinimum": 0},
                         "campaign_timeout": {"type": "number", "exclusiveMinimum": 0},
                         "replay": {**S, "enum": ["icarus"]}}, ["out"]),
                 _runner("x-sweep"), long=True),
        ToolSpec("formal_xprop", "X-propagation: can an uninitialized register or memory make a checked signal "
                 "(outputs, stream valid/ready, payload while valid) X after reset? Runs as a job.",
                 schema({**COMMON, "reset_cycles": I, "settle": I, "outputs": B, "payload": B,
                         "signal": {"type": "array", "items": S}, "filter": S, "x_inputs": B, "combinational": B,
                         "replay": {**S, "enum": ["icarus"]}},
                        ["out"]),
                 _runner("xprop"), long=True),
    ]
