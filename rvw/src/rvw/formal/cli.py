"""`rvw formal`: SymbiYosys flows over Verilog, aware of SpinalChecks reports.

  rvw formal bmc       bounded model check from reset (inputs free, reset held for the first steps)
  rvw formal from-sim  bounded model check starting from cycle N of a simulation trace (FST or VCD)
  rvw formal xprop     can an X (uninitialized register/memory) reach a checked signal after reset?

With `--checks <top>.checks.json` (written by SpinalChecks), failures are reported by check id and
Scala source location instead of Verilog line.

One clock only: every register, memory port and clocked assertion must be on the rising edge of --clock.
A design with another clock, a gated clock or a falling edge is refused (exit 2): the flows step every
clock together (sby multiclock off), which could give a false pass.
Asynchronous state controls and latches are also refused: events between clock edges are not modelled.

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
    p.add_argument("--verilog", nargs="+", help="design Verilog files")
    p.add_argument("--top", help="toplevel module")
    p.add_argument("--clock", help="clock port (default clk)")
    p.add_argument("--reset", help="reset input (default: `reset` if the toplevel has it; an explicit name must exist)")
    p.add_argument("--reset-active", choices=["high", "low"], default="high")
    p.add_argument("--checks", help="SpinalChecks report (<top>.checks.json) to name failures")
    p.add_argument("--depth", type=int, default=depth, help=f"BMC depth in cycles (default {depth})")
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

    b = s.add_parser("bmc", help="bounded model check from reset")
    _common(b, 20)
    b.add_argument("--reset-cycles", type=int, default=1, help="steps the reset is held active (default 1)")
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
    x.set_defaults(func=lambda a: _flow("xprop", a))
