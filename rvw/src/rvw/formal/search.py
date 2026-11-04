"""Finite bounded depth search. A bounded pass is never an unbounded proof."""
import contextlib
import io
import copy
import json
import math
import time
from pathlib import Path

from . import common


def depth_search(args):
    from .cli import _flow
    if (args.depth < 2 or args.max_depth < args.depth
            or not math.isfinite(args.budget) or args.budget <= 0
            or args.timeout is not None and (not math.isfinite(args.timeout) or args.timeout <= 0)):
        raise ValueError("give depth >= 2, max-depth >= depth and finite positive budgets")
    out = Path(args.out).absolute()
    # Fresh directory prevents an old campaign from being mistaken for this one.
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.monotonic() + args.budget
    depth, attempts = args.depth, []
    stop = "budget_exhausted"
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            break
        child = copy.copy(args)
        child.out = str(out / f"depth-{depth}")
        child.depth = depth
        child.timeout = min(left, args.timeout) if args.timeout is not None else left
        child.json = False
        with contextlib.redirect_stdout(io.StringIO()):
            _flow("bmc", child)
        path = Path(child.out) / "result.json"
        result = json.loads(path.read_text())
        attempts.append({"depth": depth, "status": result["status"], "result": str(path)})
        if result["status"] != "pass":
            stop = "attempt_" + result["status"]
            break
        if depth == args.max_depth:
            stop = "max_depth_reached"
            break
        depth = min(args.max_depth, depth * 2)
    result = {"schema": "rvw.formal-depth-search/1",
              "status": "fail" if attempts and attempts[-1]["status"] == "fail" else "inconclusive",
              "reason": "bounded search cannot establish an unbounded proof",
              "stop_reason": stop,
              "support": {"mode": "bmc", "schedule": "doubling",
                          "initial_depth": args.depth, "max_depth": args.max_depth,
                          "budget_s": args.budget, "attempt_timeout_s": args.timeout,
                          "engine": getattr(args, "engine", "smtbmc:yices"),
                          "unbounded_proof": False},
              "attempts": attempts,
              "max_bounded_pass": max((a["depth"] for a in attempts if a["status"] == "pass"), default=None)}
    common.write_json(out / "result.json", result)
    if args.json:
        print(json.dumps(result, indent=2))
    return 1
