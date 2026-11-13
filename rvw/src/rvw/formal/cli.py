"""`rvw formal`: SymbiYosys flows over Verilog, aware of SpinalChecks reports.

  rvw formal bmc       bounded model check from reset (inputs free, reset held for the first steps)
  rvw formal from-sim  bounded model check starting from cycle N of a simulation trace (FST or VCD)
  rvw formal xprop     can an X (uninitialized register/memory) reach a checked signal after reset?

With `--checks <top>.checks.json` (written by SpinalChecks), failures are reported by check id and
Scala source location instead of Verilog line.

By default, one clock only: every register, memory port and clocked assertion must be on the rising edge of --clock.
A design with another clock, a gated clock or a falling edge is refused (exit 2): the flows step every
clock together (sby multiclock off), which could give a false pass.
Asynchronous state controls and latches are also refused: events between clock edges are not modelled.
BMC --event-model enables sampled clock events. Declare extra clocks with --event-clock.
BMC --async-reset separately enables constant-value asynchronous-reset flip-flops in that model.
Use xprop --combinational for a clock-free module. That mode refuses all state.

Exit codes: 0 pass; 1 any other status (fail, unknown, timeout, error, no_checks), with result.json
written; 2 input error, no result.json (the previous one is removed first, except when another run
holds the same --out or --out is invalid: existing files are left alone).
"""
from __future__ import annotations

import argparse


def _flow(name: str, args) -> int:
    """Run a flow with SIGTERM raised as an exception, so that an MCP cancel (which signals this process)
    also stops yosys/sby and the solvers, which run in their own process groups. The flow holds a lock
    on its --out directory (common.begin) until it returns."""
    from rvw.formal import common, flows
    from rvw.common.capture import CaptureError
    import tempfile
    from pathlib import Path
    from rvw.common.capture import Capture
    from rvw.common.project import load_project
    try:
        with tempfile.TemporaryDirectory(prefix="rvw-formal-project-") as directory, common.sigterm_raises():
            project = load_project(getattr(args, "project", None), capture=Capture(Path(directory) / "inputs"))
            if project:
                args._project_capture = project.capture
                for key in ("verilog", "top", "checks", "clock", "reset"):
                    if getattr(args, key, None) is None:
                        setattr(args, key, project.get("formal", key))
            args.clock = args.clock or "clk"
            args.verilog = args.verilog or []
            return getattr(flows, name)(args)
    except (CaptureError, ValueError, OSError) as exc:
        common.die(str(exc))
    finally:
        common.release(args)


def _common(p: argparse.ArgumentParser, depth: int) -> None:
    p.set_defaults(event_model=False, event_clock=None, async_reset=False)
    p.add_argument("--verilog", nargs="+", help="design Verilog files")
    p.add_argument("--top", help="toplevel module")
    p.add_argument("--clock", help="clock port (default clk)")
    p.add_argument("--reset", help="reset input (default: `reset` if the toplevel has it; an explicit name must exist)")
    p.add_argument("--reset-active", choices=["high", "low"], default="high")
    p.add_argument("--checks", help="SpinalChecks report (<top>.checks.json) to name failures")
    p.add_argument("--depth", type=int, default=depth, help=f"BMC steps: cycles by default, global samples in event BMC (default {depth})")
    p.add_argument("--engine", default="smtbmc:yices", help="sby engine, ':'-separated, or a comma-separated portfolio run in parallel "
                        "(default smtbmc:yices; e.g. abc:bmc3, smtbmc:bitwuzla, 'smtbmc:yices,smtbmc:bitwuzla')")
    p.add_argument("--timeout", type=float, help="seconds before sby is stopped")
    p.add_argument("--out", required=True, help="work/result directory")
    p.add_argument("--json", action="store_true", help="print result.json")
    p.add_argument("--tie", action="append", metavar="PORT=VALUE",
                   help="tie a toplevel input to a constant for the proof (repeatable), e.g. io_irq=0; "
                        "restricts the environment (finds bugs, proves less)")


def register(sub) -> None:
    p = sub.add_parser("formal", help="SymbiYosys flows: BMC from reset or from a simulation state, X-propagation",
                       description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="formal_command", required=True)

    from rvw.soc import device_events
    events = s.add_parser("device-events", help="check concurrent accepted device requests and independent register events")
    events.add_argument("--model", required=True)
    events.add_argument("--trace", required=True)
    events.add_argument("--out", required=True)
    events.set_defaults(func=device_events.run)

    from . import csr
    c = s.add_parser("csr", help="generate project CSR checks, assembly and coverage")
    c.add_argument("--model", required=True)
    c.add_argument("--out", required=True)
    c.set_defaults(func=csr.run)
    from .deep_cli import register as deep_register
    deep_register(s)

    from .security.cli import register as security_register
    security_register(s)


    from . import regression
    regress = s.add_parser("regress", help="run declared SBY properties with a CPU worker cap")
    regress.add_argument("manifest", nargs="?")
    regress.add_argument("--out", required=True)
    regress.add_argument("--jobs", type=int, default=1)
    regress.add_argument("--timeout", type=float, default=60)
    regress.add_argument("--json", action="store_true")
    regress.set_defaults(func=regression.run)

    from . import property_library
    library = s.add_parser("properties", help="generate SVA intents or typed Stream/Flow assertions")
    library.add_argument("spec", help="JSON intent list or channel bindings")
    library.add_argument("--channels", help="SpinalChecks rvw.checks/1 report")
    library.add_argument("--db", help="SpinalDB database for automatic channel port and clock binding")
    library.add_argument("--out", required=True)
    library.set_defaults(func=property_library.run)

    from . import event_sim
    simulation = s.add_parser("simulate", help="replay timed input events and count finite SVA observations")
    simulation.add_argument("--verilog", nargs="+", required=True)
    simulation.add_argument("--top", required=True)
    simulation.add_argument("--events", required=True)
    simulation.add_argument("--out", required=True)
    simulation.add_argument("--backend", choices=["icarus", "verilator"], default="icarus")
    simulation.add_argument("--observe", action="append")
    simulation.add_argument("--check-x", action="store_true")
    simulation.add_argument("--timeout", type=float, default=60)
    simulation.set_defaults(func=event_sim.run)

    from . import liveness
    live = s.add_parser("liveness", help="lower eventual response SVA to a native SBY live job")
    live.add_argument("source")
    live.add_argument("--top", required=True)
    live.add_argument("--out", required=True)
    live.add_argument("--run", action="store_true")
    live.add_argument("--timeout", type=float, default=60)
    live.set_defaults(func=liveness.run)

    from . import temporal
    lowering = s.add_parser("sva-lower", help="lower finite temporal SVA to native Yosys assertions")
    lowering.add_argument("source")
    lowering.add_argument("--out", required=True)
    lowering.set_defaults(func=temporal.run)

    template = s.add_parser("template", help="write a reusable out-of-order safety monitor")
    from . import invariants, contracts
    template.add_argument("kind", choices=invariants.NAMES)
    template.add_argument("--entries", type=int, default=4)
    template.add_argument("--width", type=int, default=3)
    template.add_argument("--out", required=True)
    template.set_defaults(func=invariants.run)
    contract = s.add_parser("contracts", help="check neighbour guarantees and closed composition")
    contract.add_argument("manifest")
    contract.add_argument("--out", required=True)
    contract.add_argument("--budget", type=float, default=60)
    contract.add_argument("--depth", type=int, default=12)
    contract.add_argument("--engine", default="abc:pdr")
    contract.add_argument("--json", action="store_true")
    contract.set_defaults(func=contracts.run)

    strengthen = s.add_parser("strengthen", help="mine unsigned bounds and prove candidates before strengthening")
    from . import mining
    strengthen.add_argument("manifest")
    strengthen.add_argument("--out", required=True)
    strengthen.add_argument("--budget", type=float, default=60)
    strengthen.add_argument("--depth", type=int, default=12)
    strengthen.add_argument("--engine", default="smtbmc:yices")
    strengthen.add_argument("--json", action="store_true")
    strengthen.set_defaults(func=mining.run)
    from . import testplan
    report = s.add_parser("testplan", help="join property inventory, proof, activation and mutation evidence")
    report.add_argument("--manifest", required=True)
    report.add_argument("--out", required=True)
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=testplan.run)
    from . import cores
    core = s.add_parser("proof-core", help="extract a deletion-minimal core from a named SMT query")
    core.add_argument("--smt2")
    core.add_argument("--result", help="captured formal result; export SMT from its SBY model")
    core.add_argument("--depth", type=int)
    core.add_argument("--property", help="exact assertion cell name from the captured model")
    core.add_argument("--mapping")
    core.add_argument("--db")
    core.add_argument("--solver", default="z3")
    core.add_argument("--timeout", type=float, default=60)
    core.add_argument("--out", required=True)
    core.add_argument("--json", action="store_true")
    core.set_defaults(func=cores.run)
    from . import apps, bench
    app = s.add_parser("apps", help="table-driven connectivity, CSR, progress and UNR checks")
    app.add_argument("manifest")
    app.add_argument("--out", required=True)
    app.add_argument("--depth", type=int, default=20)
    app.add_argument("--engine", default="smtbmc:yices")
    app.add_argument("--timeout", type=float, default=60)
    app.add_argument("--mode", choices=["bmc", "prove"], default="bmc")
    app.add_argument("--event-model", action="store_true")
    app.add_argument("--async-reset", action="store_true")
    app.add_argument("--json", action="store_true")
    app.set_defaults(func=apps.run)
    from . import autocheck
    auto = s.add_parser("autocheck", help="per-bit constants, declared dead code, FSM states and transitions")
    auto.add_argument("manifest")
    auto.add_argument("--out", required=True)
    auto.add_argument("--max-properties", type=int, default=256)
    auto.add_argument("--depth", type=int, default=20)
    auto.add_argument("--engine", default="smtbmc:yices")
    auto.add_argument("--timeout", type=float, default=60)
    auto.add_argument("--mode", choices=["bmc", "prove"], default="bmc")
    auto.add_argument("--xprop", action="store_true", help="also run the existing output X-propagation flow")
    auto.add_argument("--json", action="store_true")
    auto.set_defaults(func=autocheck.run, event_model=False, async_reset=False)
    benchmark = s.add_parser("bench", help="pinned same-input formal engine benchmark")
    benchmark.add_argument("manifest")
    benchmark.add_argument("--out", required=True)
    benchmark.add_argument("--timeout", type=float, default=60)
    benchmark.add_argument("--json", action="store_true")
    benchmark.set_defaults(func=bench.run)

    c = s.add_parser("cex", help="what-if replay of a captured BMC counterexample (not a proof)")
    c.add_argument("--result", required=True, help="formal result.json or directory")
    c.add_argument("--trace-index", type=int, default=0)
    c.add_argument("--edit", action="append", help="PORT@TIME=INTEGER; lasts to the next witness change")
    c.add_argument("--timeout", type=float, default=60)
    c.add_argument("--out", required=True)
    c.add_argument("--json", action="store_true")
    c.add_argument("--hgldd", help="SpinalWaves HGLDD directory for this captured design")
    c.add_argument("--pdg", help="SpinalTrace pdg.json for this captured design")
    c.add_argument("--criterion", help="SpinalTrace failing assertion criterion, e.g. line:Top.scala:20")
    c.add_argument("--at-time", type=int, help="SpinalTrace sample time in VCD units")
    c.add_argument("--minimize", action="store_true", help="reduce input changes and trace prefixes with exact-property replay")
    c.add_argument("--max-checks", type=int, default=100)
    c.add_argument("--emit-testbench", action="store_true", help="generate a portable Verilog replay model and testbench")
    c.add_argument("--db", help="SpinalDB database for structural driver analysis")
    c.add_argument("--signal", help="failing design signal for driver analysis")
    c.add_argument("--open", action="store_true", help="open Surfer after typed lookup succeeds")
    from . import cex
    c.set_defaults(func=cex.run)
    hist = s.add_parser("sby-history", help="read per-property history from retained C3 campaigns")
    hist.add_argument("paths", nargs="+")
    from .campaign import history
    hist.set_defaults(func=history)

    campaign = s.add_parser("sby-regress", help="run SBY jobs and write conditional C3/C4 observations")
    campaign.add_argument("manifest", help="TOML campaign with [[property]] rows")
    campaign.add_argument("--out", required=True)
    campaign.add_argument("--timeout", type=float, default=60)
    campaign.add_argument("--json", action="store_true")
    from .campaign import run as run_campaign
    campaign.set_defaults(func=run_campaign)

    proof = s.add_parser("prove", help="unbounded safety proof from reset")
    _common(proof, 20)
    proof.add_argument("--memory-model", choices=["auto", "array", "map"], default="auto")
    proof.add_argument("--proof-cache", help="shared directory for exact proof input reuse")
    proof.add_argument("--abstraction", help="JSON unconstrained abstraction plan")
    proof.add_argument("--cut", action="append", help="unconstrained abstraction SIGNAL:WIDTH")
    proof.add_argument("--reset-cycles", type=int, default=1)
    proof.add_argument("--free-reset", action="store_true")
    proof.add_argument("--first-failure", action="store_true")
    proof.set_defaults(func=lambda a: _flow("bmc", a), mode="prove",
                       engine="abc:pdr,aiger:avy")

    search = s.add_parser("depth-search", help="bounded search with a total time budget")
    _common(search, 4)
    search.add_argument("--max-depth", required=True, type=int)
    search.add_argument("--budget", required=True, type=float)
    search.add_argument("--reset-cycles", type=int, default=1)
    search.add_argument("--free-reset", action="store_true")
    search.add_argument("--first-failure", action="store_true")
    from .search import depth_search
    search.set_defaults(func=depth_search)
    r = s.add_parser("riscv", help="bounded riscv-formal checks from project RVFI settings")
    r.add_argument("--out", required=True)
    r.add_argument("--timeout", type=float, default=60, help="seconds per check")
    r.add_argument("--json", action="store_true")
    from rvw.formal.riscv import main as riscv_main
    r.set_defaults(func=riscv_main)
    from .connectivity import register as register_connectivity
    register_connectivity(s)
    from .datapath import register as register_datapath
    register_datapath(s)
    from .equiv import register as register_equiv
    register_equiv(s)

    b = s.add_parser("bmc", help="bounded model check from reset")
    _common(b, 20)
    b.add_argument("--memory-model", choices=["auto", "array", "map"], default="auto")
    b.add_argument("--proof-cache", help="shared directory for exact proof input reuse")
    b.add_argument("--frontend", choices=["verilog", "slang", "temporal"], default="verilog",
                   help="slang: restricted clocked SVA subset; needs RVW_SLANG plugin")
    b.add_argument("--abstraction", help="JSON unconstrained abstraction plan")
    b.add_argument("--cut", action="append", help="unconstrained abstraction SIGNAL:WIDTH")
    b.add_argument("--event-clock", action="append", metavar="PORT",
                   help="enable event BMC; declare each extra independent rising-edge clock (repeatable)")
    b.add_argument("--event-model", action="store_true", help="use sampled events and sby multiclock on")
    b.add_argument("--clock-schedule", action="append", metavar="PORT=BITS",
                   help="periodic clock levels, sample zero first; declare every event clock")
    b.add_argument("--async-reset", action="store_true", help="allow constant-value async reset FFs in event BMC")
    b.add_argument("--reset-cycles", type=int, default=1, help="primary-clock cycles the reset is held active (default 1)")
    b.add_argument("--free-reset", action="store_true", help="let the solver assert reset again later")
    b.add_argument("--first-failure", action="store_true", help="stop at the first failing step (default: keep going)")
    b.set_defaults(func=lambda a: _flow("bmc", a))

    f = s.add_parser("from-sim", help="bounded model check from cycle N of a simulation trace")
    _common(f, 20)
    f.add_argument("--trace", required=True, help="Verilator FST or VCD of a simulation of the same Verilog")
    g = f.add_mutually_exclusive_group(required=True)
    g.add_argument("--cycle", type=int, help="start right after the N-th rising clock edge in the trace (1-based)")
    g.add_argument("--time", type=int, help="start at this trace time (trace time units)")
    f.add_argument("--scope", help="trace scope of the toplevel instance (default: the unique scope named --top)")
    f.add_argument("--memories", choices=["trace", "free", "zero"], default="trace",
                   help="memory contents: from the trace (default; memories absent from it stay free), "
                        "free (any value: sound, may give spurious failures), zero")
    f.add_argument("--first-failure", action="store_true", help="stop at the first failing step (default: keep going)")
    f.set_defaults(func=lambda a: _flow("from_sim", a))

    swarm = s.add_parser("swarm", help="bounded checks from uniformly selected simulation cycles")
    _common(swarm, 20)
    swarm.add_argument("--trace", required=True)
    swarm.add_argument("--state-plan", help="trace-hashed coverage-hole state priorities")
    swarm.add_argument("--engine-pool", action="append", help="rotate engines across sampled states; repeat for diversity")
    swarm.add_argument("--start-cycle", type=int, default=1)
    swarm.add_argument("--end-cycle", type=int, required=True)
    swarm.add_argument("--samples", type=int, default=4)
    swarm.add_argument("--budget", type=float, required=True)
    swarm.add_argument("--scope")
    swarm.add_argument("--memories", choices=["trace", "free"], default="trace")
    swarm.add_argument("--first-failure", action="store_true")
    from .swarm import run as run_swarm
    swarm.set_defaults(func=run_swarm)

    x = s.add_parser("xprop", help="X-propagation: can an X reach a checked signal after reset?")
    _common(x, 10)
    x.add_argument("--reset-cycles", type=int, default=2, help="steps the reset is held active (default 2)")
    x.add_argument("--settle", type=int, default=0, help="extra steps after reset before checking")
    x.add_argument("--outputs", action="store_true", help="check every toplevel output")
    x.add_argument("--payload", action="store_true",
                   help="with --checks: also check stream/flow payloads while valid (default: valid and ready only)")
    x.add_argument("--signal", action="append", help="flattened signal name to check (repeatable)")
    x.add_argument("--filter", help="regex: keep only targets whose signal matches")
    x.add_argument("--x-inputs", action="store_true", help="do not assume the inputs are defined")
    x.add_argument("--combinational", action="store_true", help="clock-free module (state is refused)")
    x.add_argument("--replay", choices=["icarus"], help="replay candidates with native 4-state Icarus")
    x.add_argument("--first-failure", action="store_true", help="stop after the first formal witness; other targets stay not_reported")
    x.set_defaults(func=lambda a: _flow("xprop", a))

    context = s.add_parser("x-context", help="native parent-design replay from reset with explicit input ties")
    _common(context, 16)
    context.add_argument("--reset-cycles", type=int, default=2)
    context.add_argument("--signal", action="append", required=True, help="hierarchical observation in the parent")
    context.set_defaults(replay="icarus", func=lambda a: _flow("x_context", a))

    sweep = s.add_parser("x-sweep", help="bounded per-module X campaign")
    _common(sweep, 8)
    sweep.add_argument("--module", action="append", help="module to sweep (repeatable; default all)")
    sweep.add_argument("--module-timeout", type=float, default=30, help="seconds per module")
    sweep.add_argument("--campaign-timeout", type=float, default=300, help="total campaign seconds")
    sweep.add_argument("--replay", choices=["icarus"], default="icarus")
    sweep.add_argument("--first-failure", action="store_true", help="stop each module after the first formal witness")
    sweep.set_defaults(func=lambda a: _flow("x_sweep", a))
