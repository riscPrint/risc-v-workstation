"""`rvw bundle RUN_DIR`: turn a failed run into a failure bundle (contract C5)."""
from __future__ import annotations

import argparse
import sys

from ..common import jsonout
from .make import Options, make


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("bundle", help="failure bundle from a failed run (C5)", description=__doc__)
    p.add_argument("run_dir", help="C1 run directory (with result.json)")
    p.add_argument("--out", help="bundle directory (default RUN_DIR/bundle)")
    p.add_argument("-n", "--retired", type=int, default=64, help="retired instructions to list (64)")
    p.add_argument("--cut-cycles", type=int, default=500, help="cycles of wave before the failure to keep (500)")
    p.add_argument("--no-rerun", action="store_true", help="never re-run the replay for a wave/trace")
    p.add_argument("--rerun-window", type=int, default=3000, help="cycles of wave to record when re-running (3000)")
    p.add_argument("--konata", action="store_true", help="also ask the re-run for a Konata log")
    p.add_argument("--core-config", help="core debug description (default RiscvSim/<core>/debug.toml)")
    p.add_argument("--pdg", help="SpinalTrace pdg.json of an instrumented build of the same design")
    p.add_argument("--trace-wave", help="wave of the instrumented build covering the failure (default: the run's)")
    p.add_argument("--trace-cycles", type=int, default=20, help="cycles of wave the dependency trace unrolls (20)")
    p.add_argument("--no-spinaltrace", action="store_true", help="skip the SpinalTrace dependency trace")
    p.add_argument("--timeout", type=float, help="seconds before the re-run is killed, counted "
                                                 "from when the core lock is held")
    p.add_argument("--json", action="store_true", help="print summary.json")
    p.set_defaults(func=run)


def execute_json(run_dir: str, *, out=None, retired=64, cut_cycles=500, no_rerun=False,
                 rerun_window=3000, konata=False, core_config=None, pdg=None, trace_wave=None,
                 trace_cycles=20, no_spinaltrace=False, timeout=None, project=None) -> dict:
    """Shared CLI/MCP entry point returning the C5 summary."""
    o = Options(project=project, out=out, retired=retired, cut_cycles=cut_cycles, rerun=not no_rerun,
                rerun_window=rerun_window, konata=konata, core_config=core_config,
                spinaltrace=not no_spinaltrace, timeout=timeout, pdg=pdg, trace_wave=trace_wave,
                trace_cycles=trace_cycles)
    return make(run_dir, o)


def run(a) -> int:
    try:
        S = execute_json(a.run_dir, project=getattr(a, "project", None), out=a.out, retired=a.retired, cut_cycles=a.cut_cycles,
                         no_rerun=a.no_rerun, rerun_window=a.rerun_window, konata=a.konata,
                         core_config=a.core_config, no_spinaltrace=a.no_spinaltrace, timeout=a.timeout,
                         pdg=a.pdg, trace_wave=a.trace_wave, trace_cycles=a.trace_cycles)
    except (FileNotFoundError, ValueError) as e:
        print(f"rvw bundle: {e}", file=sys.stderr)
        return 2
    if a.json:
        try:
            jsonout.write(S, indent=1, default=str)
        except jsonout.JsonOutputError as e:
            print(f"rvw bundle: {e}", file=sys.stderr)
            return 2
    else:
        print(f"{S['signature']}: suspected {S['suspect']['unit']}; see {S['out']}/summary.md")
    return 0
