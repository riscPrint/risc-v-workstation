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
FLAGS = {"cross_check", "free_reset", "first_failure", "outputs", "payload", "x_inputs", "combinational", "event_model", "async_reset", "open", "xprop", "minimize", "emit_testbench", "check_x"}


def _argv(command, args):
    argv = [sys.executable, "-m", "rvw", "formal", *command.split()]
    for key, value in args.items():
        if value is None or value is False:
            continue
        if key == 'manifest' and command in ('apps', 'autocheck'):
            argv.append(str(value))
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
        if code not in ((0, 1, 3) if command == "datapath" else (0, 1)):
            raise error("failed")
        if not result.is_file():
            raise error("wrote no result")
        try:
            data = json.loads(result.read_text())
        except (OSError, ValueError) as e:
            raise error(f"unreadable result.json: {e}")
        if not isinstance(data, dict):
            raise error("result.json is not an object")
        if (code == 0) != (data.get("status") == ("proved" if command == "datapath" else "pass")):
            raise error(f"exit code and status {data.get('status')!r} disagree")
        return data
    return run


def _csr(job, **args):
    code = job.run(_argv('csr', args))
    if code:
        raise ToolError('CSR generation failed', {'exit_code': code, 'log_tail': job.tail(20)})
    return json.loads((Path(args['out']) / 'result.json').read_text())

def _connectivity(job, **args):
    manifest = args.pop('manifest')
    run = args.pop('run', False)
    argv = _argv('connectivity', args) + [manifest]
    if run:
        argv.append('--run')
    code = job.run(argv)
    path = Path(args['out']) / 'result.json'
    if code != 1 or not path.is_file():
        raise ToolError('connectivity result unavailable', {'exit_code': code, 'log_tail': job.tail(30)})
    data = json.loads(path.read_text())
    if data.get('schema') != 'rvw.connectivity/1' or data.get('status') != 'incomplete':
        raise ToolError('invalid connectivity report')
    return data


def _device_events(job, **args):
    code = job.run([sys.executable, "-m", "rvw", "formal", "device-events", "--model", args['model'], "--trace", args['trace'], "--out", args['out']])
    if code not in (1, 3):
        raise ToolError("device event check failed", {"exit_code": code, "log_tail": job.tail(30)})
    return json.loads(Path(args['out']).read_text())


def _upf(job, **args):
    code = job.run([sys.executable, "-m", "rvw", "formal", "upf", "--source", args['source'], "--bindings", args['bindings'], "--out", args['out']])
    if code not in (0, 3):
        raise ToolError("UPF generation failed", {"exit_code": code, "log_tail": job.tail(30)})
    return json.loads((Path(args['out'])/'result.json').read_text())


def _power(job, **args):
    code = job.run(_argv('power', args))
    if code:
        raise ToolError('power generation failed', {'exit_code': code, 'log_tail': job.tail(20)})
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

def _rvfi_generate(job, **args):
    manifest = args.pop('manifest')
    code = job.run(_argv('rvfi-generate', args) + [manifest])
    if code:
        raise ToolError('RVFI generation failed', {'exit_code': code, 'log_tail': job.tail(20)})
    result = json.loads((Path(args['out']) / 'result.json').read_text())
    if result.get('schema') != 'rvw.rvfi-generation/1' or result.get('status') != 'generated':
        raise ToolError('invalid RVFI generation report')
    return result


def _riscv(job, **args):
    code = job.run(_argv('riscv', args))
    out = Path(args['out'])
    if code not in (1, 3) or not (out / 'verdict.json').is_file() or not (out / 'results.json').is_file():
        raise ToolError('riscv-formal results unavailable', {'exit_code': code, 'log_tail': job.tail(20)})
    verdict = json.loads((out / 'verdict.json').read_text())
    if (code == 1) != (verdict.get('verdict') == 'reject'):
        raise ToolError('riscv-formal exit and verdict disagree')
    return dict(verdict=verdict, results=json.loads((out / 'results.json').read_text()))


def _liveness(job, **args):
    argv = [sys.executable, '-m', 'rvw', 'formal', 'liveness', args['source'],
            '--top', args['top'], '--out', args['out']]
    if args.get('run'):
        argv.append('--run')
    if 'timeout' in args:
        argv += ['--timeout', str(args['timeout'])]
    code = job.run(argv)
    if code not in (0, 1):
        raise ToolError('liveness lowering failed', {'exit_code': code, 'log_tail': job.tail(20)})
    return json.loads((Path(args['out']) / 'result.json').read_text())


def _sail_zicond(job, **args):
    code = job.run(_argv('sail-zicond', args))
    if code:
        raise ToolError('Sail generation failed', {'exit_code': code, 'log_tail': job.tail(20)})
    return json.loads((Path(args['out']) / 'manifest.json').read_text())


def _custom_isa(job, **args):
    manifest = args.pop('manifest')
    code = job.run(_argv('custom-isa', args) + [manifest])
    path = Path(args['out']) / 'result.json'
    if code not in (0,1) or not path.is_file():
        raise ToolError('custom ISA generation failed', {'exit_code': code, 'log_tail': job.tail(20)})
    result = json.loads(path.read_text())
    if (code == 1) != (result.get('status') == 'mismatch'):
        raise ToolError('custom ISA result and exit code disagree')
    return result


def _profiles(job, **args):
    manifest = args.pop('manifest')
    code = job.run(_argv('profiles', args) + [manifest])
    path = Path(args['out']) / 'result.json'
    if code != 3 or not path.is_file():
        raise ToolError('profile report unavailable', {'exit_code': code, 'log_tail': job.tail(20)})
    result = json.loads(path.read_text())
    if result.get('schema') != 'rvw.profile-report/1' or result.get('status') != 'inconclusive':
        raise ToolError('invalid profile report')
    return result


def mcp_tools():
    from .deep_cli import mcp_tools as deep_tools
    return [*deep_tools(),

        ToolSpec("formal_simulate", "Replay timed multi-clock input events and collect SVA counts and four-state observations as C1.",
                 schema({"verilog": {"type": "array", "items": S}, "top": S, "events": S,
                         "out": S, "backend": {**S, "enum": ["icarus", "verilator"]},
                         "observe": {"type": "array", "items": S}, "check_x": B,
                         "timeout": {"type": "number", "exclusiveMinimum": 0}},
                        ["verilog", "top", "events", "out"]), _runner("simulate"), long=True),
        ToolSpec("formal_liveness", "Lower eventual response properties to SBY live jobs. Engine passes remain inconclusive.",
                 schema({"source": S, "top": S, "out": S, "run": B,
                         "timeout": {"type": "number", "exclusiveMinimum": 0}}, ["source", "top", "out"]),
                 _liveness, long=True),
        ToolSpec("formal_device_events", "Check concurrent device requests against independent reset state. Matching samples remain inconclusive.",
                 schema({"model": S, "trace": S, "out": S}, ["model", "trace", "out"]), _device_events, long=True),
        ToolSpec("formal_upf", "Import literal UPF domain/isolation declarations and generate sampled checks. No verification run.",
                 schema({"source": S, "bindings": S, "out": S}, ["source", "bindings", "out"]), _upf, long=True),
        ToolSpec("formal_sail_zicond", "Compile pinned Sail RV32 CZERO rules into instruction checks. This is a result slice with an explicit RVFI shell, not a full-machine proof.",
                 schema({"model": S, "compiler": S, "out": S}, ["model", "out"]), _sail_zicond, long=True),
        ToolSpec("formal_custom_isa", "Export versioned pure custom R-type semantics, GNU software hooks and verification plans. Does not run a DUT.",
                 schema({"manifest": S, "out": S}, ["manifest", "out"]), _custom_isa, long=True),
        ToolSpec("formal_profiles", "Track pinned RVA23/RVB23 named requirements, configuration declarations and hash-bound proof evidence. No full profile acceptance verdict.",
                 schema({"manifest": S, "baseline": S, "out": S}, ["manifest", "out"]), _profiles, long=True),
        ToolSpec("formal_power", "Generate sampled low-power checks and declared DFT inventory. No proof or ATPG run.",
                 schema({"intent": S, "out": S, "db": S}, ["intent", "out"]), _power, long=True),
        ToolSpec("formal_template", "Generate a project-bound safety monitor. No verification run.",
                 schema({"kind": S, "out": S, "entries": I, "width": I}, ["kind", "out"]),
                 _template, long=True),
        ToolSpec("formal_autocheck", "Check per-bit constants, declared dead code and FSM coverage. Optional output X propagation.",
                 schema({"manifest": S, "out": S, "max_properties": I, "depth": I,
                         "engine": S, "timeout": {"type": "number", "exclusiveMinimum": 0},
                         "mode": {**S, "enum": ["bmc", "prove"]}, "xprop": B}, ["manifest", "out"]),
                 _runner("autocheck"), long=True),
        ToolSpec("formal_apps", "Run reviewed connectivity, CSR, bounded progress, UNR and FSM monitor contracts.",
                 schema({"manifest": S, "out": S, "depth": I, "engine": S,
                         "timeout": {"type": "number", "exclusiveMinimum": 0},
                         "mode": {**S, "enum": ["bmc", "prove"]}, "event_model": B, "async_reset": B},
                        ["manifest", "out"]), _runner("apps"), long=True),


        ToolSpec("formal_properties", "Generate SVA for common intents and typed Stream/Flow channels. Does not run a proof.",
                 schema({"spec": S, "channels": S, "db": S, "out": S}, ["spec", "out"]), _properties, long=True),
        ToolSpec("formal_security_pair", "Prove declared digital two-copy observation contracts or initial-state independence.",
                 schema({"manifest": S, "out": S, "timeout": {"type":"number", "exclusiveMinimum":0}}, ["manifest","out"]),
                 _runner("security pair"), long=True),
        ToolSpec("formal_datapath", "Bit-blast mapped RTL and a C reference with CBMC. Fixed or bounded-latency transactions; no streaming proof.",
                 schema({"rtl": S, "model": S, "binding": S, "max_latency": I, "width": {"type": "integer", "enum": [8,16,32,64]},
                         "out": S, "latency": I, "unwind": I,
                         "case": {**S, "enum": ["all", "finite", "nan", "infinity", "zero", "subnormal"]},
                         "rounding": {"type": "integer", "enum": [0,1,2,3,4]},
                         "reference_tree": S, "reference_source": {"type": "array", "items": S},
                         "reference_include": {"type": "array", "items": S},
                         "timeout": {"type": "number", "exclusiveMinimum": 0}}, ["rtl", "model", "width", "out"]),
                 _runner("datapath"), long=True),
        ToolSpec("formal_testplan", "Join a formal inventory with captured proof, core, activation and mutation evidence. JSON and HTML.",
                 schema({"manifest": S, "out": S}, ["manifest", "out"]), _runner("testplan"), long=True),

        ToolSpec("formal_riscv", "Run selected project riscv-formal checks through SBY. Return C3 outcomes and a C4 verdict. Bounded passes cannot accept a core.",
                 schema({"project": S, "out": S, "timeout": {"type": "number", "exclusiveMinimum": 0}}, ["out"]), _riscv, long=True),
        ToolSpec("formal_rvfi_generate", "Generate an RVFI wrapper and project configuration from a core-owned port binding. No proof is run.",
                 schema({"manifest": S, "out": S}, ["manifest", "out"]), _rvfi_generate, long=True),
        ToolSpec("formal_proof_core", "Extract a deletion-minimal solver core for one named SMT query. Not an RTL proof.",
                 schema({"smt2": S, "mapping": S, "result": S, "depth": I, "property": S, "db": S, "solver": S,
                         "timeout": {"type": "number", "exclusiveMinimum": 0}, "out": S},
                        ["out"]), _runner("proof-core"), long=True),
        ToolSpec("formal_csr", "Generate CSR monitors, directed assembly and coverage. Does not run verification.",
                 schema({"model": S, "out": S}, ["model", "out"]), _csr, long=True),

        ToolSpec("formal_regress", "Run declared SBY property tasks with a CPU worker cap. Return conditional C3 and JUnit observations.",
                 schema({"manifest": S, "project": S, "out": S, "jobs": {"type": "integer", "minimum": 1},
                         "timeout": {"type": "number", "exclusiveMinimum": 0}}, ["out"]),
                 _regress, long=True),
        ToolSpec("formal_sva_lower", "Lower finite clocked SVA to native Yosys assertions. Unsupported constructs give named errors.",
                 schema({"source": S, "out": S}, ["source", "out"]), _lower, long=True),

        ToolSpec("formal_connectivity", "Resolve project connection tables, report undeclared drivers and optionally prove observed RTL contracts. Overall design acceptance remains incomplete.",
                 schema({"manifest": S, "db": S, "out": S, "run": B,
                         "proof_mode": {**S, "enum": ["bmc", "prove"]},
                         "clock": S, "reset": S, "depth": I, "max_nodes": I,
                         "engine": S, "timeout": {"type": "number", "exclusiveMinimum": 0}},
                        ["manifest", "db", "out"]), _connectivity, long=True),
        ToolSpec("formal_cex", "Replay a captured failing BMC witness with edited inputs through Yosys sim. Not a proof.",
                 schema({"result": S, "out": S, "trace_index": I,
                         "edit": {"type": "array", "items": S},
                         "hgldd": S, "pdg": S, "criterion": S, "at_time": I, "open": B,
                         "minimize": B, "max_checks": I, "emit_testbench": B, "db": S, "signal": S,
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


def _regress(job, **args):
    manifest = args.pop("manifest", None)
    argv = _argv("regress", args)
    if manifest:
        argv.append(manifest)
    code = job.run(argv)
    path = Path(args["out"]) / "result.json"
    if code != 1 or not path.is_file():
        raise ToolError("formal regress failed", {"exit_code": code, "log_tail": job.tail(30)})
    data = json.loads(path.read_text())
    if data.get("schema") != "rvw.formal-regress/1" or data.get("status") != "unknown":
        raise ToolError("formal regress wrote an invalid result")
    return data


def _lower(job, **args):
    code = job.run([sys.executable, "-m", "rvw", "formal", "sva-lower", args["source"], "--out", args["out"]])
    if code:
        raise ToolError("SVA lowering failed", {"exit_code": code, "log_tail": job.tail(30)})
    return {"output": args["out"]}


def _properties(job, **args):
    argv = [sys.executable, "-m", "rvw", "formal", "properties", args["spec"], "--out", args["out"]]
    if args.get("channels"):
        argv += ["--channels", args["channels"]]
    if args.get("db"):
        argv += ["--db", args["db"]]
    code = job.run(argv)
    if code:
        raise ToolError("SVA intent generation failed", {"exit_code": code, "log_tail": job.tail(30)})
    return {"output": args["out"]}
