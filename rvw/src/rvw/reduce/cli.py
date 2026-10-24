"""`rvw reduce RUN_DIR`: shortest reproduction of a failure with the same signature.

Exit status: 0 when at least one trial reproduced the signature, 1 when none did, 2 for bad input
(the run passed, or its signature does not match --signature, or a timeout that is not a hang)."""
from __future__ import annotations

import argparse
import sys

from ..common import jsonout
from .core import Options, Reducer


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("reduce", help="shrink a failing run, keeping its failure signature",
                       description=__doc__)
    p.add_argument("run_dir", help="C1 run directory of the failure")
    p.add_argument("--out", help="output directory (default RUN_DIR/reduce)")
    p.add_argument("--signature", help="signature to preserve (default: the run's; 're:REGEX' for a family)")
    p.add_argument("--modes", default="cycles,seeds,latency",
                   help="comma list of cycles, seeds, latency, symbols (default cycles,seeds,latency)")
    p.add_argument("--seeds", type=int, default=12, help="number of seeds to try (12)")
    p.add_argument("--seed-start", type=int, default=1, help="first seed to try (1)")
    p.add_argument("--latencies", default="1,2,5,10,20,50", help="fixed memory latencies to try")
    p.add_argument("--symbol", action="append", default=[],
                   help="NAME[:BYTES] integer in initialized data to minimize (adds the symbols mode)")
    p.add_argument("--monotone", action="store_true",
                   help="symbols: the failure is known to be monotone in the value, so the binary search "
                        "boundary is the minimum (exact)")
    p.add_argument("--exhaustive", action="store_true",
                   help="symbols: after the binary search, try every untested smaller value in order to "
                        "prove the minimum (exact when the budget allows)")
    p.add_argument("--margin", type=int, default=100, help="cycles past the failure for max cycles (100)")
    p.add_argument("--hang-cycles", type=int, default=5000, help="timeouts: cycles without retirement that count as a hang")
    p.add_argument("--jobs", type=int, default=1, help="parallel simulations inside one run-many (1)")
    p.add_argument("--batch", type=int, default=4, help="trials per run-many batch (4)")
    p.add_argument("--budget", type=int, default=64, help="maximum number of trials (64)")
    p.add_argument("--timeout", type=float, help="seconds per trial, counted from when the core lock is "
                                                 "held (time in the lock queue does not count)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=run)


def execute_json(run_dir: str, *, out=None, signature=None, modes="cycles,seeds,latency", seeds=12,
                 seed_start=1, latencies="1,2,5,10,20,50", symbol=None, margin=100,
                 hang_cycles=5000, jobs=1, batch=4, budget=64, timeout=None, monotone=False,
                 exhaustive=False, project=None) -> dict:
    """Shared CLI/MCP options and reduction result."""
    modes = [m.strip() for m in modes.split(",") if m.strip()]
    if symbol and "symbols" not in modes:
        modes.append("symbols")
    bad = [m for m in modes if m not in ("cycles", "seeds", "latency", "symbols")]
    if bad:
        raise ValueError(f"unknown mode(s) {bad}")
    o = Options(project=project, out=out, signature=signature, modes=modes, seeds=seeds, seed_start=seed_start,
                latencies=[int(x) for x in latencies.split(",") if x.strip()], symbols=symbol or [],
                margin=margin, hang_cycles=hang_cycles, jobs=jobs, batch=batch, budget=budget,
                timeout=timeout, monotone=monotone, exhaustive=exhaustive)
    return Reducer(run_dir, o).reduce()


def run(a) -> int:
    try:
        r = execute_json(a.run_dir, project=getattr(a, "project", None), out=a.out, signature=a.signature, modes=a.modes, seeds=a.seeds,
                         seed_start=a.seed_start, latencies=a.latencies, symbol=a.symbol, margin=a.margin,
                         hang_cycles=a.hang_cycles, jobs=a.jobs, batch=a.batch, budget=a.budget,
                         timeout=a.timeout, monotone=a.monotone, exhaustive=a.exhaustive)
    except (FileNotFoundError, ValueError) as e:
        print(f"rvw reduce: {e}", file=sys.stderr)
        return 2
    if a.json:
        try:
            jsonout.write(r, indent=1, default=str)
        except jsonout.JsonOutputError as e:
            print(f"rvw reduce: {e}", file=sys.stderr)
            return 2
    else:
        b = r["best"]
        if r["reproduced"]:
            print(f"{r['signature']}: best cycle {b['cycles']} (seed {b['seed']}, mem_latency {b['mem_latency']}); "
                  f"replay: {b['replay']}")
        else:
            print(f"{r['signature']}: no trial reproduced the signature; see {r['out']}/reduce.md")
    return 0 if r["reproduced"] else 1
