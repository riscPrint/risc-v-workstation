"""The `rvw formal` flows: BMC from reset, BMC from a simulation state, and X-propagation."""
from __future__ import annotations

import json
import re
import sys
import time
import uuid
from pathlib import Path

from . import common, vcdsnap
from .common import ChecksIndex, Port, vid
from .snapshot import InputSnapshot
from .tools import ACTIVE, Toolchain


def _inputs(args, out: Path, defines: list[str] = ()) -> tuple[InputSnapshot, list[Port], list[Path]]:
    snapshot = InputSnapshot(args, out)
    args._input_snapshot = snapshot
    snapshot.tools = Toolchain(snapshot.capture, args, snapshot.directory / 'tools')
    args._formal_tools_token = ACTIVE.set(snapshot.tools)
    ports = common.module_ports(snapshot.sources, args.top, out, args.timeout, defines, snapshot=snapshot,
                                allow_async_reset=getattr(args, "async_reset", False))
    # App port maps must match the sealed DUT interface. Yosys can otherwise resize
    # instance connections and leave an omitted port free without rejecting the RTL.
    for module, expected in getattr(args, "expected_interfaces", {}).items():
        actual = {p.name: {"direction": p.direction, "width": p.width}
                  for p in common.ports_from_json(out / "module_ports.json", module)}
        if actual != expected:
            raise ValueError(f"declared port map differs from elaborated interface: {module}")
    if getattr(args, "expected_interfaces", None):
        modules = json.loads((out / "module_ports.json").read_text())["modules"]
        for name, module in modules.items():
            if name == args.top:
                continue
            if any(c["type"] == "$assert" or (c["type"] == "$check" and
                   c.get("parameters", {}).get("FLAVOR") == "assert")
                   for c in module.get("cells", {}).values()):
                raise ValueError("app attribution needs DUT RTL without existing assertions")
    # Ports and state controls describe this exact elaboration. Later probes and proofs
    # read it instead of re-reading Verilog or running its preprocessor again.
    model = snapshot.seal(out / 'module_ports.il')
    return snapshot, ports, [model]


def _engine_block(engine: str, keep_going: bool) -> str:
    """One engine, or a comma-separated portfolio (sby runs them in parallel, first answer wins)."""
    return "\n".join(common.engine_line(e.strip(), keep_going) for e in engine.split(",") if e.strip())


def _header(kind: str, args, status: str, secs: float, asserts: int | None, reset: str | None,
            ties: dict, restrictions: list[str]) -> dict:
    return {
        "schema": "rvw.formal/1",
        "flow": kind,
        "frontend": getattr(args, "frontend", "verilog"),
        "proof_kind": "unbounded" if kind == "prove" else "bounded",
        "top": args.top,
        # pass | fail | unknown | error | timeout | no_checks (the proven design has no assertion)
        "status": status,
        "depth": args.depth,
        "engine": args.engine,
        "wall_s": round(secs, 1),
        "assertions": asserts,
        "reset": reset,
        "ties": {k: v for k, (_, v) in ties.items()},
        "restrictions": restrictions,
    }


def _finish(out: Path, kind: str, args, rc: int, secs: float, checks: ChecksIndex,
            model_top: str, reset: str | None, ties: dict, restrictions: list[str],
            reach_timeout: float | None, cycle_offset: int = 0, extra: dict | None = None,
            xprop_labels: list[dict] | None = None) -> dict:
    sby_dir = out / "sby"
    log = sby_dir / "logfile.txt"
    log_text = log.read_text(errors="replace") if log.exists() else ""
    asserts = common.count_asserts(sby_dir / "model" / "design_prep.il", model_top)
    status = common.final_status(rc, log_text, asserts)
    reachability = None
    if status == "pass" or "Status: PREUNSAT" in log_text:
        reachability = _reachability(out, model_top, args, reach_timeout)
        secs += reachability["wall_s"]
        if reachability["status"] != "reachable":
            status = "unknown"
    snapshot = args._input_snapshot
    sources = [out / r.get('frontend', r['path']) for r in snapshot.files
               if r['kind'] in ('source', 'include')]
    findings = ({"x_reaches": parse_xprop_failures(log_text, xprop_labels)} if xprop_labels is not None
                else {"failures": common.parse_failures(log, sources, checks, cycle_offset,
                                                       property_model=out / "module_ports.json")})
    traces = sorted(str(p.relative_to(out)) for p in sby_dir.glob("engine_*/trace*.vcd"))
    result = _header(kind, args, status, secs, asserts, reset, ties, restrictions)
    result.update({
        "reachability": reachability,
        "solver": _solver(rc, log_text),
        **findings,
        "traces": traces,
        "sby_log": str(log.relative_to(out)) if log.exists() else None,
        "tools": common.tool_versions(),
    })
    if extra:
        result.update(extra)
    if getattr(args, "event_model", False):
        result["event_model"] = {
            "backend": "yosys clk2fflogic (sby multiclock on)",
            "step": "one global input sample; transitions between samples are not represented",
            "clocks": [args.clock, *(args.event_clock or [])],
            "relationships": "unrelated; arbitrary rates, phase, simultaneous edges and stalls",
            "async_reset": bool(args.async_reset),
        }
        for failure in result.get("failures", []):
            failure["cycle"] = None  # global samples have no common clock-cycle number
    snapshot.finish(result)
    common.write_json(out / "result.json", result)
    return result


def _reachability(out: Path, top: str, args, timeout: float | None) -> dict:
    """A pass needs a legal path through every checked step, independently of the proof engine.

    Reuse the actual prepared model, with all its assumptions and initial state. Remove assertions
    and design covers. A new true cover is delayed until the last checked step. Only a fresh,
    successful cover job counts as evidence; an unsatisfiable, timed-out or failed job cannot pass.
    """
    name = "rvw_reachable_" + uuid.uuid4().hex
    common.clear_outputs(out, "reachability")
    config = f"""[options]
mode cover
depth {args.depth}
multiclock off

[engines]
smtbmc yices

[script]
read_rtlil {out / 'sby' / 'model' / 'design_prep.il'}
prep -top {top} -flatten
chformal -assert -cover -remove
cd {top}
add -wire {name} 1
connect -set {name} 1'1
add -cover {name}
chformal -cover -delay {args.depth - 1}
cd ..

[files]
"""
    (out / "reachability.sby").write_text(config)
    rc, secs = common.run(["sby", "-f", "-d", "reachability", "reachability.sby"],
                          out, out / "reachability.log", timeout)
    directory = out / "reachability"
    log = directory / "logfile.txt"
    text = log.read_text(errors="replace") if log.exists() else ""
    status = "unknown"
    solver_status, log_rc = common.sby_result(text)
    if log_rc == rc:
        if rc == 0 and solver_status == "pass":
            status = "reachable"
        elif rc != 0 and solver_status == "fail":
            status = "unreachable"
    return {"status": status, "depth": args.depth, "engine": "smtbmc:yices",
            "solver": _solver(rc, text),
            "wall_s": round(secs, 1), "log": "reachability/logfile.txt" if log.exists() else None}


def _solver(rc: int, log_text: str) -> dict:
    """Process exit code and the exit code in SBY's final log entry."""
    return {"exit": rc, "log_rc": common.sby_result(log_text)[1]}


def _sby(out: Path, name: str, text: str) -> None:
    """Remove the previous solver directory before writing the next job."""
    common.clear_outputs(out, "sby")
    (out / name).write_text(text)


def _print(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2))
        return
    print(f"{result['flow']}: {result['status']} (depth {result['depth']}, {result['assertions']} assertions, "
          f"{result['wall_s']} s)")
    if result["status"] == "no_checks":
        print("  nothing was checked: the design has no assertion (elaborate with SpinalChecks / includeFormal?)")
    _print_reachability(result)
    for r in result.get("restrictions", []):
        print(f"  restriction: {r}")
    for f in result["failures"]:
        what = f["check"] or f.get("fail_signal") or f["property"]
        cycle = f" (cycle {f['cycle']})" if f.get("cycle") is not None else ""
        print(f"  FAIL {what} at step {f['step']}{cycle} {f['location']}"
              + (f"  [{f['source']}]" if f.get("source") else ""))
    for t in result["traces"]:
        print(f"  trace: {t}")


def _print_reachability(result: dict) -> None:
    reachability = result.get("reachability")
    if reachability and reachability["status"] != "reachable":
        print(f"  bounded reachability: {reachability['status']} (see reachability/logfile.txt)")


# ---------------------------------------------------------------------------------------------------
# bmc: from reset


def counter_width(limit: int) -> int:
    """Width of a saturating step counter that must count past `limit` (at least 8 bits)."""
    return max(8, (limit + 1).bit_length() + 1)


def min_depth_reset(reset_cycles: int, settle: int = 0) -> int:
    """Smallest BMC depth at which a clocked assertion is checked at least once after the reset: the
    reset is active in steps 0..R-1, settling takes S more steps, and a clocked assertion on the values
    of step R+S is reported at step R+S+1, so steps 0..R+S+1 are needed."""
    return reset_cycles + settle + 2


def _reset_harness(name: str, ports: list[Port], clock: str, reset: str | None,
                   active_high: bool, reset_cycles: int, free_reset: bool, ties: dict,
                   counter_limit: int | None) -> tuple[list[str], list[str]]:
    ins = [p for p in ports if p.direction == "input" and p.name not in (clock, reset) and p.name not in ties]
    hdr = [f"input {vid(clock)}"] + [f"input {p.decl()}" for p in ins]
    if reset and free_reset:
        hdr.append("input rvw_reset_free")
    lines = [f"module {name}({', '.join(hdr)});"]
    if counter_limit is not None:
        cw = counter_width(counter_limit)
        lines += [f"  reg [{cw - 1}:0] rvw_cycle = {cw}'d0;",
                  f"  always @(posedge {vid(clock)}) if (rvw_cycle != {{{cw}{{1'b1}}}}) rvw_cycle <= rvw_cycle + {cw}'d1;"]
    if reset:
        on, off = ("1'b1", "1'b0") if active_high else ("1'b0", "1'b1")
        lines.append(f"  wire rvw_reset = (rvw_cycle < {cw}'d{reset_cycles}) ? {on} : "
                     + (f"(rvw_reset_free ? {on} : {off});" if free_reset else f"{off};"))
    conns = [f".{vid(clock)}({vid(clock)})"]
    if reset:
        conns.append(f".{vid(reset)}(rvw_reset)")
    conns += [f".{vid(p.name)}({vid(p.name)})" for p in ins]
    conns += [f".{vid(n)}({w}'d{v})" for n, (w, v) in ties.items()]
    return lines, conns


def wrapper(top: str, ports: list[Port], clock: str, reset: str | None, active_high: bool,
            reset_cycles: int, free_reset: bool, ties: dict | None = None) -> str:
    """BMC inputs are free except for the reset sequence and explicit ties."""
    lines, conns = _reset_harness("rvw_formal_top", ports, clock, reset, active_high,
                                 reset_cycles, free_reset, ties or {}, reset_cycles if reset else None)
    outs = [p for p in ports if p.direction != "input"]
    lines += [f"  wire {p.decl()};" for p in outs]
    conns += [f".{vid(p.name)}({vid(p.name)})" for p in outs]
    lines += [f"  {top} dut ({', '.join(conns)});", "endmodule"]
    return "\n".join(lines) + "\n"


def bmc(args) -> int:
    out = common.begin(args)
    args.event_model = bool(args.event_model or args.event_clock)
    if args.async_reset and not args.event_model:
        common.die("--async-reset requires --event-model or --event-clock")
    for clock in args.event_clock or []:
        common.check_ident("--event-clock", clock)
    if len(set([args.clock, *(args.event_clock or [])])) != 1 + len(args.event_clock or []):
        common.die("event clocks must be distinct")

    snapshot, ports, files = _inputs(args, out)
    reset = common.resolve_reset(args, ports)
    if reset is None:
        # stderr: with --json, stdout is the result document only (result.json has "reset": null)
        print(f"note: {args.top} has no reset input; inputs are free from step 0", file=sys.stderr)
    if args.event_model and reset in (args.event_clock or []):
        common.die("an event clock cannot also be the reset input")
    need = ((2 * args.reset_cycles + 4) if args.event_model else min_depth_reset(args.reset_cycles)) if reset else 2
    if args.depth < need:
        common.die(f"--depth {args.depth} checks nothing after the reset (reset held {args.reset_cycles} steps); "
                   f"use --depth >= {need}")
    ties = _ties(args, ports, {args.clock, reset})
    if args.event_model and set(ties) & set(args.event_clock or []):
        common.die("event clocks cannot be tied")
    started = time.time()
    common.need("yosys")
    common.probe_clocks(files, args.top, args.clock, out, args.timeout,
                        extra_clocks=args.event_clock or (), event_model=args.event_model)
    restrictions = _restrictions(ties, reset, args.reset_cycles, args.free_reset)
    if args.event_model and reset:
        restrictions = [r for r in restrictions if not r.startswith("reset ")]
        restrictions.append(f"reset {reset} held active until {args.reset_cycles} primary-clock rising edges"
                            + (", then free" if args.free_reset else ", then inactive"))
    common.clear_outputs(out, 'rvw_formal_top.sv')
    (out / "rvw_formal_top.sv").write_text(
        wrapper(args.top, ports, args.clock, reset, args.reset_active == "high", args.reset_cycles, args.free_reset, ties))
    snapshot.seal(out / 'rvw_formal_top.sv')
    from .cuts import commands
    cut_script, cut_records = commands(args, out, files)
    # SBY applies clk2fflogic in event mode; the default retains the one-clock model.
    sby = f"""[options]
mode {getattr(args, "mode", "bmc")}
depth {args.depth}
multiclock {'on' if args.event_model else 'off'}

[engines]
{_engine_block(args.engine, not args.first_failure)}

[script]
{common.read_rtlil(files)}
read_verilog -formal -sv {out / 'rvw_formal_top.sv'}
prep -top rvw_formal_top
{cut_script}

[files]
"""
    common.need("sby")
    _sby(out, "bmc.sby", sby)
    cache_root = getattr(args, "proof_cache", None)
    cache_identity, cache_hit = None, False
    if cache_root:
        from . import proof_cache
        cache_identity = proof_cache.identity(out, sby, snapshot)
        cache_hit = proof_cache.restore(cache_root, cache_identity, out)
    if cache_hit:
        rc, secs = 0, 0
    else:
        rc, secs = common.run(["sby", "-f", "-d", "sby", "bmc.sby"], out, out / "sby.log",
                              _remaining(args.timeout, started))
    result = _finish(out, getattr(args, "mode", "bmc"), args, rc, secs, ChecksIndex.load(snapshot.checks), "rvw_formal_top",
                     reset, ties, restrictions, _remaining(args.timeout, started))
    if cut_records:
        result['cut_points'] = cut_records
        if result['status'] == 'fail':
            result['status'] = 'unknown'
            result['abstraction_counterexample'] = True
        common.write_json(out / "result.json", result)
    if cache_root:
        result['proof_cache'] = {'key': proof_cache.key_for(cache_identity), 'hit': cache_hit,
                                 'rule': 'exact prepared inputs, tools, environment and runner code'}
        # _finish always performs fresh reachability and tool verification, even on a hit.
        proof_cache.publish(cache_root, cache_identity, out, result)
        common.write_json(out / "result.json", result)
    _print(result, args.json)
    return 0 if result["status"] == "pass" else 1


# ---------------------------------------------------------------------------------------------------
# from-sim: BMC from a state of a simulation trace


def from_sim(args) -> int:
    out = common.begin(args)
    snapshot, ports, files = _inputs(args, out)
    trace = snapshot.trace
    if args.depth < 2:
        common.die("--depth must be >= 2 (a clocked assertion on the loaded state is reported at step 1)")
    reset = common.resolve_reset(args, ports)
    ties = _ties(args, ports, {args.clock})
    started = time.time()
    common.need("yosys"), common.need("sby")
    if str(trace).endswith(".fst"):
        common.need("fst2vcd")
    common.need("vcd2fst")  # yosys sim reads VCD through it
    common.probe_clocks(files, args.top, args.clock, out, _remaining(args.timeout, started))

    scope = args.scope
    t0 = time.time()
    with vcdsnap.open_trace(trace, _remaining(args.timeout, started)) as stream:
        if not scope:
            cands = [s for s in vcdsnap.scopes(stream) if s.split(".")[-1] == args.top]
            if not cands:
                common.die(f"no scope named {args.top} in {trace}; pass --scope")
            if len(cands) != 1:
                common.die("multiple trace scopes match --top; pass --scope: " + ", ".join(cands))
            scope = cands[0]
            stream.seek(0)
        common.check_hier("scope", scope)
        snap = vcdsnap.take_stream(stream, scope, args.clock, args.cycle, args.time)
    snap_vcd = out / "state.vcd"
    common.clear_outputs(out, 'state.vcd')
    vcdsnap.write(snap, snap_vcd, args.top)
    snapshot.seal(snap_vcd)
    # Convert with the pinned tool before Yosys starts. Yosys otherwise looks up
    # vcd2fst internally, after a release launcher can reset PATH.
    snap_fst = out / 'state.fst'
    common.clear_outputs(out, 'state.fst')
    rc, _ = common.run(['vcd2fst', str(snap_vcd), str(snap_fst)], out,
                       out / 'state_convert.log', _remaining(args.timeout, started))
    if rc != 0 or not snap_fst.is_file():
        common.die('replay state conversion failed; see ' + str(out / 'state_convert.log'))
    snapshot.seal(snap_fst)
    t_snap = time.time() - t0

    # Load the state into the design: registers get `init` attributes, memories INIT parameters.
    # The RTL's own initial values (`initial` blocks, Spinal `init` on a register without reset, memory
    # init contents) hold at time 0, not at cycle N: drop them first, so state the trace does not give
    # starts free instead of at a value it may no longer have (that could turn a FAIL into a PASS).
    ys = f"""{common.read_rtlil(files)}
prep -top {args.top}
flatten
# Remove design assumptions influenced by $initstate before creating flow samplers.
# Such assumptions describe time zero, not the resumed state. The transitive selection is
# conservative: it can also remove a runtime assumption derived from $initstate.
select -set rvw_design_assumes t:$assume t:$check r:FLAVOR=assume %i %u
select -set rvw_initial_assumptions t:$initstate %co* @rvw_design_assumes %i t:$check r:FLAVOR=assume %i r:TRG_ENABLE=1 %i r:TRG_WIDTH=0 %i %u
tee -o {out / 'removed_initial_assumptions.txt'} select -list @rvw_initial_assumptions
delete @rvw_initial_assumptions
setattr -unset init w:*
memory_unpack
delete t:$meminit t:$meminit_v2
memory_collect
async2sync
flatten
# The only init values left are the flow's own (async2sync's assertion sampling registers start disabled);
# mark them so the report tells them from state loaded from the trace.
setattr -set rvw_flow_init 1 a:init
sim -clock {args.clock} -r {snap_fst} -scope {args.top} -at {snap.time}{_unit(snap.timescale)} -w
# sim -w also leaves init values on combinational wires (e.g. aliases of ports); the solver would hold
# those at step 0 even where --tie or free inputs drive something else. Keep them on flip-flop outputs only.
select -set rvw_ffq t:*ff* %x:+[Q] t:*ff* %d w:* %i
setattr -unset init w:* @rvw_ffq %d
write_rtlil {out / 'state.il'}
tee -o {out / 'state_stat.txt'} stat
"""
    common.clear_outputs(out, "state.il", "state_stat.txt", "load_state.log")
    (out / "load_state.ys").write_text(ys)
    rc, secs_load = common.run(["yosys", "-q", "-l", str(out / "load_state.log"), "-s", "load_state.ys"], out,
                               out / "load_state.out", _remaining(args.timeout, started))
    if rc == common.TIMEOUT_EXIT:
        common.die(f"loading the state timed out (--timeout {args.timeout} s)")
    if rc != 0:
        tail = (out / "load_state.out").read_text(errors="replace")[-2000:]
        common.die(f"loading the state failed:\n{tail}")
    # Counted before --memories rewrites INIT, so `zero` does not count its filled zeros as traced.
    coverage = state_coverage(out / "state.il")
    if args.memories != "trace":
        set_memory_init(out / "state.il", args.memories)
        if args.memories == "free":
            coverage = state_coverage(out / "state.il")
    snapshot.seal(out / 'state.il')

    # A tie that differs from the traced value at cycle N cuts whatever was in flight (e.g. a valid that
    # was high mid-transfer): the proof may then fail on the environment, not the design.
    traced = {v.path[0]: snap.values.get(v.code) for v in snap.vars if len(v.path) == 1}
    tie_conflicts = []
    for name, (_, val) in ties.items():
        tv = traced.get(name)
        if tv and tv[0] in "b01" and set(tv.lstrip("b")) <= {"0", "1"} and int(tv.lstrip("b"), 2) != val:
            tie_conflicts.append({"port": name, "tie": val, "traced": int(tv.lstrip("b"), 2)})
    restrictions = _restrictions(ties, None, 0, False)
    if reset and reset not in ties:
        ties[reset] = (1, 0 if args.reset_active == "high" else 1)
        restrictions.append(f"reset {reset} tied inactive")
    reset_script = _tie_script(args.top, ties)
    # multiclock off is sound only for one clock: the clock probe above refused any other design.
    sby = f"""[options]
mode bmc
depth {args.depth}
multiclock off

[engines]
{_engine_block(args.engine, not args.first_failure)}

[script]
read_rtlil {out / 'state.il'}
{reset_script}prep -top {args.top}

[files]
"""
    _sby(out, "from_sim.sby", sby)
    rc, secs = common.run(["sby", "-f", "-d", "sby", "from_sim.sby"], out, out / "sby.log",
                          _remaining(args.timeout, started))
    extra = {
        "trace": str(Path(args.trace).resolve()), "scope": scope, "cycle": args.cycle, "time": snap.time,
        "tie_conflicts": tie_conflicts,
        "timescale": snap.timescale, "memories_mode": args.memories,
        "trace_memories": snap.memories, "state": coverage,
        "snapshot_s": round(t_snap, 1), "load_s": round(secs_load, 1),
        "removed_initial_assumptions": (out / 'removed_initial_assumptions.txt').read_text().splitlines(),
        "note": "BMC step k is cycle N+k of the simulation (step 0 is the loaded state); a clocked assertion "
                "reported at step k failed on the values of step k-1, so failures list cycle N+k-1",
    }
    cyc0 = args.cycle if args.cycle is not None else 0
    result = _finish(out, "from-sim", args, rc, secs, ChecksIndex.load(snapshot.checks), args.top,
                     reset, ties, restrictions, _remaining(args.timeout, started), cyc0, extra)
    _print(result, args.json)
    if not args.json:
        st = coverage
        design_bits = st["ff_bits"] - st["ff_bits_flow"]
        print(f"  state: {st['ff_bits_from_trace']}/{design_bits} register bits and "
              f"{st['mem_init']}/{st['mems']} memories loaded from the trace; "
              f"{st['ff_bits_free']} register bits start free")
        for r in st["registers_free"][:20]:
            print(f"    register not (fully) in trace (free in the proof): {r}")
        for m in st["mems_uninit"][:20]:
            print(f"    memory not in trace (free in the proof): {m}")
        for c in tie_conflicts:
            print(f"  warning: --tie {c['port']}={c['tie']} but the trace has {c['traced']} at this cycle "
                  "(an in-flight transfer is cut; failures right after the start may come from that)")
        if st["ff_bits_free"] or st["mems_uninit"]:
            print("  note: state missing from the trace starts free and can give spurious failures at the first "
                  "steps; with Verilator trace with --trace-underscore (Spinal's _zz_ registers), "
                  "--trace-max-array and --trace-max-width")
    return 0 if result["status"] == "pass" else 1


def _ties(args, ports: list[Port], exclude: set) -> dict[str, tuple[int, int]]:
    """--tie PORT=VALUE -> {port: (width, value)}; ports must be toplevel inputs, values must fit."""
    widths = {p.name: p.width for p in ports if p.direction == "input"}
    out = {}
    for t in args.tie or []:
        name, eq, val = str(t).partition("=")
        common.check_ident("--tie port", name)
        if not eq or name not in widths or name in exclude:
            common.die(f"--tie {t!r}: {name} is not a free toplevel input of {args.top} (use PORT=VALUE)")
        try:
            v = int(val.strip(), 0)
        except ValueError:
            common.die(f"--tie {t!r}: {val!r} is not an integer")
        if v < 0 or v >= (1 << widths[name]):
            common.die(f"--tie {t!r}: {v} does not fit in {name} ({widths[name]} bits)")
        if name in out:
            common.die(f"--tie {name} given twice")
        out[name] = (widths[name], v)
    return out


def _restrictions(ties: dict, reset: str | None, reset_cycles: int, free_reset: bool) -> list[str]:
    """The environment restrictions a result holds under, in words (stored in result.json)."""
    r = [f"input {n} tied to {v}" for n, (_, v) in ties.items()]
    if reset:
        r.append(f"reset {reset} held active for steps 0..{reset_cycles - 1}"
                 + (", then free" if free_reset else ", then inactive"))
    return r


def _remaining(timeout: float | None, started: float) -> float | None:
    if timeout is None:
        return None
    return max(1.0, timeout - (time.time() - started))


def _tie_script(top: str, ties: dict) -> str:
    lines = []
    for name, (w, v) in ties.items():
        lines.append(f"delete -input {top}/w:{name}")
    if ties:
        lines.append(f"cd {top}")
        lines += [f"connect -nounset -set {name} {w}'d{v}" for name, (w, v) in ties.items()]
        lines.append("cd ..")
    return "\n".join(lines) + ("\n" if lines else "")


def _unit(timescale: str) -> str:
    m = re.fullmatch(r"(\d+)\s*([a-z]+)", timescale)
    if not m:
        return "ps"
    if m.group(1) != "1":
        common.die(f"timescale {timescale} not supported (needs 1<unit>)")
    return m.group(2)


def set_memory_init(rtlil: Path, mode: str) -> None:
    """`free`: every memory starts with any contents (INIT all x). `zero`: words the trace did not give
    (x) start at zero."""
    out, in_mem = [], False
    for line in rtlil.read_text(errors="replace").splitlines():
        s = line.strip()
        if s.startswith("cell "):
            in_mem = s.split()[1].startswith("$mem")
        elif s == "end":
            in_mem = False
        elif in_mem and s.startswith("parameter \\INIT ") and "'" in s:
            head, bits = s.rsplit("'", 1)
            bits = "x" * len(bits) if mode == "free" else bits.replace("x", "0")
            line = line[: len(line) - len(s)] + head + "'" + bits
        out.append(line)
    rtlil.write_text("\n".join(out) + "\n")


_FF_TYPES = ("$dff", "$sdff", "$adff", "$dffe", "$sdffe", "$sdffce", "$adffe", "$aldff", "$aldffe")


def _const_bits(text: str, width: int | None = None) -> str:
    """An RTLIL constant as a bit string, MSB first: `4'01x0`, or a plain integer (32 bits)."""
    text = text.strip()
    if "'" in text:
        return text.split("'", 1)[1].replace(" ", "")
    try:
        v = int(text)
    except ValueError:
        return "x" * (width or 0)
    w = width or 32
    return format(v & ((1 << w) - 1), f"0{w}b")


def _param_int(cell: dict, name: str, default: int) -> int:
    text = cell["params"].get(name)
    if text is None:
        return default
    bits = _const_bits(text)
    return int(bits, 2) if bits and set(bits) <= {"0", "1"} else default


def _sig_bits(spec: str, wires: dict) -> list:
    """The bits of an RTLIL sigspec, LSB first: (wire, index) for a wire bit, None for a constant bit.
    `wires` maps a wire name to (width, offset, upto)."""
    toks = spec.replace("{", " ").replace("}", " ").split()
    chunks: list[list] = []  # MSB-first chunks, each LSB first
    i = 0
    while i < len(toks):
        t = toks[i]
        if t[0] in "\\$":
            width, offset, upto = wires.get(t, (1, 0, False))
            idx = list(range(offset, offset + width))
            if i + 1 < len(toks) and toks[i + 1].startswith("["):
                rng = toks[i + 1].strip("[]")
                hi, _, lo = rng.partition(":")
                hi_i = int(hi)
                lo_i = int(lo) if lo else hi_i
                idx = list(range(min(hi_i, lo_i), max(hi_i, lo_i) + 1))
                i += 1
            chunks.append([(t, b) for b in idx])
        else:
            bits = _const_bits(t)
            chunks.append([None] * len(bits))
        i += 1
    out: list = []
    for c in reversed(chunks):
        out += c
    return out


def state_coverage(rtlil: Path) -> dict:
    """Where the start state comes from, bit by bit. Register bits: `from_trace` (an `init` loaded from the
    trace), `flow` (registers the flow adds and starts itself, e.g. async2sync's assertion samplers, marked
    `rvw_flow_init`), `free` (no init: any value). The RTL's own initial values were removed before the
    state was loaded, so an init on a design register can only come from the trace. Memories: INIT bits
    that are not x came from the trace (`--memories trace`)."""
    wires: dict = {}      # (module, name) -> (width, offset, upto)
    inits: dict = {}      # (module, name) -> init bits, MSB first
    flow: set = set()     # (module, name) with rvw_flow_init
    cells: list[dict] = []
    module = None
    attrs: dict = {}
    cur = None
    for line in rtlil.read_text(errors="replace").splitlines():
        s = line.strip()
        if s.startswith("module "):
            module, attrs, cur = s.split()[1], {}, None
        elif s.startswith("attribute "):
            p = s.split(" ", 2)
            attrs[p[1]] = p[2] if len(p) > 2 else ""
        elif s.startswith("wire "):
            p = s.split()
            name = p[-1]
            width = int(p[p.index("width") + 1]) if "width" in p else 1
            offset = int(p[p.index("offset") + 1]) if "offset" in p else 0
            wires[(module, name)] = (width, offset, "upto" in p)
            if "\\init" in attrs:
                inits[(module, name)] = _const_bits(attrs["\\init"], width)
            if "\\rvw_flow_init" in attrs:
                flow.add((module, name))
            attrs = {}
        elif s.startswith("cell "):
            _, typ, name = s.split()[:3]
            cur = {"type": typ, "name": name, "module": module, "params": {}, "conns": {}}
            cells.append(cur)
            attrs = {}
        elif s.startswith("parameter ") and cur is not None:
            p = s.split(" ", 2)
            cur["params"][p[1]] = p[2] if len(p) > 2 else ""
        elif s.startswith("connect ") and cur is not None:
            p = s.split(" ", 2)
            cur["conns"][p[1]] = p[2] if len(p) > 2 else ""
        elif s == "end":
            cur, attrs = None, {}
        elif not s.startswith("attribute"):
            attrs = {}
    by_module: dict = {}
    for (m, n), w in wires.items():
        by_module.setdefault(m, {})[n] = w
    ff_bits = from_trace = flow_bits = free = 0
    free_regs: list[str] = []
    mems = mem_init = mem_bits = mem_bits_trace = 0
    mems_uninit: list[str] = []
    for c in cells:
        t, m = c["type"], c["module"]
        if t in _FF_TYPES:
            width = _param_int(c, "\\WIDTH", 1)
            bits = _sig_bits(c["conns"].get("\\Q", ""), by_module.get(m, {}))
            if len(bits) != width:  # unparsed sigspec: count the cell as free
                bits = [None] * width
            ff_bits += width
            cell_free = 0
            free_wires: list[str] = []
            for b in bits:
                if b is None:
                    cell_free += 1
                    continue
                key = (m, b[0])
                if key in flow:
                    flow_bits += 1
                    continue
                w, off, upto = wires[key]
                init = inits.get(key)
                pos = (b[1] - off) if upto else (w - 1 - (b[1] - off))
                if init is not None and len(init) == w and 0 <= pos < w and init[pos] in "01":
                    from_trace += 1
                else:
                    cell_free += 1
                    if b[0] not in free_wires:
                        free_wires.append(b[0])
            free += cell_free
            for n in (free_wires or ([c["name"]] if cell_free else [])):
                if len(free_regs) < 50:
                    free_regs.append(f"{m.lstrip(chr(92))}.{n.lstrip(chr(92))}")
        elif t.startswith("$mem"):
            mems += 1
            init = c["params"].get("\\INIT", "")
            size, wdt = _param_int(c, "\\SIZE", 0), _param_int(c, "\\WIDTH", 0)
            body = _const_bits(init, size * wdt) if init else ""
            known = sum(ch in "01" for ch in body)
            mem_bits += size * wdt
            mem_bits_trace += known
            if known:
                mem_init += 1
            else:
                memid = c["params"].get("\\MEMID", c["name"]).strip('"').lstrip("\\")
                mems_uninit.append(f"{m.lstrip(chr(92))}.{memid}")
    return {"ff_bits": ff_bits, "ff_bits_from_trace": from_trace, "ff_bits_flow": flow_bits,
            "ff_bits_free": free, "registers_free": free_regs,
            "mems": mems, "mem_init": mem_init, "mem_bits": mem_bits, "mem_bits_from_trace": mem_bits_trace,
            "mems_uninit": mems_uninit}


# ---------------------------------------------------------------------------------------------------
# xprop: can an X (uninitialized register or memory) reach a checked signal after reset?


def xprop(args) -> int:
    out = common.begin(args)
    try:
        rx = re.compile(args.filter) if args.filter else None
    except re.error as exc:
        common.die(f"--filter {args.filter!r} is not a valid regex: {exc}")
    snapshot, ports, files = _inputs(args, out, ['SYNTHESIS'])
    common.need("yosys"), common.need("sby")
    names = {p.name for p in ports}
    comb = getattr(args, 'combinational', False)
    if comb:
        if any(p.direction == 'inout' for p in ports):
            common.die('inout ports are not supported by rvw formal wrappers')
        model = json.loads((out / 'module_ports.json').read_text())
        state = [c['type'] for m in model['modules'].values() for c in m.get('cells', {}).values()
                 if any(t in c['type'].lower() for t in ('dff', 'mem', 'latch', 'fsm'))]
        if state:
            common.die('--combinational refuses state: ' + ', '.join(sorted(set(state))))
        if args.reset:
            common.die('--combinational does not use --reset')
        reset = None
    else:
        reset = common.resolve_reset(args, ports)
    R, S = (0, 0) if comb else (args.reset_cycles, args.settle)
    # The asserts are armed once the step counter passes R+S; a clocked assert on step k's values is
    # reported at step k+1. Shallower runs would check nothing and pass.
    need = min_depth_reset(R, S) + 1
    if not comb and args.depth < need:
        common.die(f"--depth {args.depth} checks nothing after reset ({R} cycles) and settle ({S}); "
                   f"use --depth >= {need}")
    ties = _ties(args, ports, {args.clock, reset})
    checks = ChecksIndex.load(snapshot.checks)

    # Targets: (label, signal, condition signal or None). Names are flattened hierarchical names.
    targets: list[tuple[str, str, str | None]] = []
    if args.outputs:
        for p in ports:
            if p.direction == "output":
                targets.append((f"output {p.name}", p.name, None))
    # A Flow/Stream inside another channel's payload (e.g. an optional field `Flow(UInt)` in a response)
    # carries data, not a handshake: its valid is only meaningful while the outer valid is high.
    in_payload = {p for ch in checks.channels for p in ch.get("payload", [])}
    for ch in checks.channels:
        if not ch.get("valid") or ch["valid"] in in_payload:
            continue
        label = f"{ch['kind']} {(ch['path'] + '.') if ch['path'] else ''}{ch['object']}"
        targets.append((label + " valid", ch["valid"], None))
        if ch.get("ready"):
            targets.append((label + " ready", ch["ready"], ch["valid"]))
        for pl in ch.get("payload", []) if args.payload else []:
            targets.append((label + f" payload {pl}", pl, ch["valid"]))
    for s in args.signal or []:
        targets.append((f"signal {s}", s, None))
    # A signal checked "while valid" (stream payload, ready) replaces an unconditional output target.
    conditional = {s for _, s, c in targets if c}
    targets = [t for t in targets if t[2] or t[1] not in conditional]
    if rx is not None:
        targets = [t for t in targets if rx.search(t[1])]
    # Refuse old reports with invalid names instead of silently dropping requested targets.
    for _, sig, cond in targets:
        for name in (sig, cond):
            if name is not None and not common.is_hier(name):
                common.die(f"xprop: invalid target name {name!r}; regenerate the checks report")
    if not targets:
        common.die("xprop: nothing to check (use --outputs, --checks or --signal)")

    # Signals to bring out as ports of the flattened design (outputs are ports already).
    internal = sorted({s for _, s, _ in targets if s not in names} | {c for _, _, c in targets if c and c not in names})
    expose_sel = " ".join(f"w:{s}" for s in internal)
    ys_prep = f"""{common.read_rtlil(files)}
prep -top {args.top}
flatten
memory_map
{('expose ' + expose_sel) if internal else ''}
"""
    started = time.time()
    # Which signals exist after flattening (Spinal or yosys may have optimized some away), and how wide.
    common.clear_outputs(out, "exposed_ports.json", "targets.json")
    common.clear_outputs(out, common.CLOCKS_JSON)
    # The clock probe runs last in the same yosys run (it deletes most of the design).
    (out / "probe.ys").write_text(ys_prep + f"write_json -noscopeinfo {out / 'exposed_ports.json'}\n"
                                  + common.clock_probe_cmds(args.top, out / common.CLOCKS_JSON))
    rc, _ = common.run(["yosys", "-q", "-s", "probe.ys"], out, out / "probe.log", args.timeout)
    if rc == common.TIMEOUT_EXIT:
        common.die(f"xprop: yosys timed out (--timeout {args.timeout} s)")
    if rc != 0:
        common.die("xprop: yosys failed, see " + str(out / "probe.log"))
    if not comb:
        common.check_one_clock(common.clock_problems(out / common.CLOCKS_JSON, args.top, args.clock), args.clock)
    exposed_ports = common.ports_from_json(out / "exposed_ports.json", args.top)
    widths = {p.name: p.width for p in exposed_ports}
    present = set(widths)
    inputs = {p.name for p in ports if p.direction == "input"}
    asked = set(args.signal or [])
    absent = sorted(s for s in asked if s not in present and s not in inputs)
    if absent:
        common.die(f"xprop: --signal not found in the flattened design: {', '.join(absent)}")
    targets = [t for t in targets if t[1] not in inputs]  # inputs are assumed defined
    missing = [t for t in targets if t[1] not in present]
    targets = [t for t in targets if t[1] in present and (t[2] is None or t[2] in present)]
    if not targets:
        common.die("xprop: none of the targets exist in the flattened design")

    assume_defined = "-assume-def-inputs" if not args.x_inputs else ""
    w, conns = _reset_harness("rvw_xprop_top", ports, args.clock, reset, args.reset_active == "high",
                              R, False, ties, R + S + 1)
    if comb:
        w = ["module rvw_xprop_top(" + ', '.join('input ' + p.decl() for p in ports
             if p.direction == 'input' and p.name not in ties) + ");"]
        conns = [f".{vid(p.name)}({vid(p.name)})" for p in ports
                 if p.direction == 'input' and p.name not in ties]
        conns += [f".{vid(n)}({wd}'d{v})" for n, (wd, v) in ties.items()]
    input_masks = {}
    if args.x_inputs:
        for index, p in enumerate(ports):
            if p.direction == 'input':
                input_masks[p.name] = (f'rvw_input_x{index}' if p.name not in ties
                                       and (comb or p.name not in (args.clock, reset)) else "0")
                if input_masks[p.name] != '0':
                    w.insert(1, f'  (* anyseq *) reg [{p.width-1}:0] {input_masks[p.name]};')
        split = []
        for c in conns:
            name = next(p.name for p in ports if c.startswith('.' + vid(p.name) + '('))
            split += [c.replace('.' + vid(name) + '(', '.' + vid(name + '_d') + '(', 1),
                      f".{vid(name + '_x')}({input_masks[name]})"]
        conns = split
    cw = counter_width(R + S + 1)
    sigs = sorted({t[1] for t in targets} | {t[2] for t in targets if t[2]})
    for i, s in enumerate(sigs):
        wd = widths[s]
        rng = f"[{wd - 1}:0] " if wd > 1 else ""
        if s in inputs:  # Input validity conditions use the same X masks as the DUT.
            src = f"{ties[s][0]}'d{ties[s][1]}" if s in ties else vid(s)
            w.append(f"  wire {rng}rvw_d{i} = {src};\n  wire {rng}rvw_x{i} = {input_masks.get(s, '0')};")
            continue
        w.append(f"  wire {rng}rvw_d{i};\n  wire {rng}rvw_x{i};")
        conns.append(f".{vid(s + '_d')}(rvw_d{i})")
        conns.append(f".{vid(s + '_x')}(rvw_x{i})")
    w.append(f"  {args.top} dut ({', '.join(conns)});")
    w.append("  always @* begin" if comb else
             f"  always @(posedge {vid(args.clock)}) if (rvw_cycle > {cw}'d{R + S}) begin")
    labels = []
    for k, (label, s, cond) in enumerate(targets):
        i = sigs.index(s)
        if cond:
            j = sigs.index(cond)
            expr = f"!(rvw_d{j} && !rvw_x{j}) || rvw_x{i} == 0"
        else:
            expr = f"rvw_x{i} == 0"
        w.append(f"    rvw_x_{k}: assert({expr});")
        labels.append({"assert": f"rvw_x_{k}", "label": label, "signal": s, "when_valid": cond})
    w.append("  end")
    w.append("endmodule")
    common.clear_outputs(out, 'rvw_xprop_top.sv')
    (out / "rvw_xprop_top.sv").write_text("\n".join(w) + "\n")
    snapshot.seal(out / 'rvw_xprop_top.sv')
    common.write_json(out / "targets.json", {"targets": labels, "missing": [t[1] for t in missing]})

    # multiclock off is sound only for one clock: the clock probe above refused any other design.
    sby = f"""[options]
mode bmc
depth {args.depth}
multiclock off

[engines]
{_engine_block(args.engine, not getattr(args, "first_failure", False))}

[script]
{ys_prep}
# Unwritten registers and undriven nets have no cell for xprop to encode. Make their
# unknown value explicit first. Real inputs and driven/initialized state are preserved.
setundef -undriven -undef
xprop -split-outputs {'-split-inputs' if args.x_inputs else ''} {assume_defined}
read_verilog -formal -sv {out / 'rvw_xprop_top.sv'}
prep -top rvw_xprop_top

[files]
"""
    _sby(out, "xprop.sby", sby)
    rc, secs = common.run(["sby", "-f", "-d", "sby", "xprop.sby"], out, out / "sby.log",
                          _remaining(args.timeout, started))
    restrictions = _restrictions(ties, reset, R, False)
    restrictions.append("inputs may be X" if args.x_inputs else "inputs assumed defined (not X)")
    if S:
        restrictions.append(f"checked from step {R + S + 1} (settle {S})")
    result = _finish(out, "xprop", args, rc, secs, checks, "rvw_xprop_top", reset, ties,
                     restrictions, _remaining(args.timeout, started),
                     extra={"targets": len(targets), "missing_signals": [t[1] for t in missing]},
                     xprop_labels=labels)
    # Yosys cannot X-encode formal monitors. Keep them and their assumptions.
    # Other unencoded cells cannot earn an X-clean verdict.
    encoding_log = out / 'sby' / 'model' / 'design.log'
    unencoded = []
    if encoding_log.exists():
        for line in encoding_log.read_text(errors='replace').splitlines():
            if 'Warning: Unhandled cell ' in line:
                match = re.search(r'Unhandled cell .* \(([^()]+)\)', line)
                kind = match.group(1) if match else 'unreadable cell type'
                if kind not in {'$check', '$assert', '$assume', '$cover', '$live', '$fair', '$print'}:
                    unencoded.append(kind)
    result['unencoded_cells'] = sorted(set(unencoded))
    if unencoded and result['status'] == 'pass':
        result.update(status='unknown', cause='unsupported_x_encoding')
    from .xreplay import replay
    result['backend'] = 'yosys-xprop'
    result['inventory'] = [dict(t, disposition='candidate' if any(
        f['assert'] == t['assert'] for f in result['x_reaches']) else 'not_reported') for t in labels]
    if getattr(args, 'replay', None):
        replay(args, out, ports, labels, result, reset, ties, R, S, comb)
    snapshot.finish(result)
    if result['input_snapshot']['problems']:
        for target in result['inventory']:
            if target['disposition'] == 'confirmed':
                target.update(disposition='inconclusive', reason='tool capture verification failed')
        if 'replay' in result:
            result['replay']['status'] = 'inconclusive'
    common.write_json(out / 'result.json', result)
    status = result['status']
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"xprop: {status} ({len(targets)} targets, {result['assertions']} assertions, depth {args.depth}, {result['wall_s']} s)")
        _print_reachability(result)
        for f in result["x_reaches"]:
            print(f"  candidate: {f['label']} at step {f['step']}")
        for r in restrictions:
            print(f"  restriction: {r}")
        if missing:
            print(f"  {len(missing)} signals not found in the flattened design (see targets.json)")
    return 0 if status == "pass" else 1


def parse_xprop_failures(text: str, labels: list[dict]) -> list[dict]:
    """X findings by target, earliest step first (from the engines' lines: sby's summary is partial)."""
    by_assert = {l["assert"]: l for l in labels}
    found: dict[str, dict] = {}
    for m in re.finditer(r"failed assertion \S*?(rvw_x_\d+)\S* at \S+ step (\d+)", text):
        if m.group(1) in by_assert and m.group(1) not in found:
            found[m.group(1)] = {**by_assert[m.group(1)], "step": int(m.group(2))}
    for prop, _file, _line, step in common.engine_failures(text):
        a = re.search(r"(rvw_x_\d+)", prop)
        if a and a.group(1) in by_assert and a.group(1) not in found:
            found[a.group(1)] = {**by_assert[a.group(1)], "step": step}
    return sorted(found.values(), key=lambda f: (f["step"], f["label"]))


def x_sweep(args):
    from .xsweep import sweep
    return sweep(args)


def x_context(args):
    from .xcontext import run
    return run(args)
