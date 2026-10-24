"""`rvw bisect RUN_DIR --good REV`: the core commit that introduced a failure signature."""
from __future__ import annotations

import argparse
import sys

from ..common import jsonout
from .core import Bisector, Options


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("bisect", help="find the core commit that introduced a failure signature",
                       description=__doc__)
    p.add_argument("run_dir", help="C1 run directory of the failure (ideally reduced: rvw reduce)")
    p.add_argument("--good", required=True, help="a revision without the failure")
    p.add_argument("--bad", help="a revision with it (default: the run's core_rev)")
    p.add_argument("--core-repo", help="core git checkout to clone (default: the run's source.core_repo)")
    p.add_argument("--core-env", help="environment variable the adapter reads the core path from "
                                      "(default [core].source_env of the core config; BOOM: SPINAL_BOOM)")
    p.add_argument("--workdir", help="where the private clone and runs go (default: a new directory under "
                                     "~/.cache/rvw/bisect). An existing one must be an earlier rvw bisect "
                                     "workspace of the same core repo")
    p.add_argument("--signature", help="signature to look for (default: the run's; 're:REGEX' for a family)")
    p.add_argument("--other", choices=["skip", "good", "bad"], default="skip",
                   help="verdict for results that neither match nor pass (default skip)")
    p.add_argument("--max-cycles", type=int, help="max cycles of each test (default: the unreduced run's "
                                                 "max cycles when RUN_DIR is an rvw reduce trial, else the "
                                                 "run's own)")
    p.add_argument("--hang-cycles", type=int, default=5000,
                   help="timeouts count as the signature only with no retirement for this many cycles (5000)")
    p.add_argument("--no-verify", action="store_true", help="do not test the endpoints first")
    p.add_argument("--remove-clone", action="store_true",
                   help="delete the private clone afterwards (only if this invocation created it)")
    p.add_argument("--timeout", type=float, help="seconds per test run, counted from when the core lock "
                                                 "is held (time in the lock queue does not count)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=run)


def execute_json(run_dir: str, good: str, *, bad=None, core_repo=None, core_env=None, workdir=None,
                 signature=None, other="skip", max_cycles=None, no_verify=False, remove_clone=False,
                 timeout=None, hang_cycles=5000, project=None) -> dict:
    """Shared CLI/MCP entry point; all checkouts happen in the private clone."""
    if other not in ("skip", "good", "bad"):
        raise ValueError("other must be skip, good or bad")
    o = Options(project=project, good=good, bad=bad, core_repo=core_repo, core_env=core_env, workdir=workdir,
                signature=signature, other=other, verify=not no_verify, keep=not remove_clone,
                timeout=timeout, max_cycles=max_cycles, hang_cycles=hang_cycles)
    return Bisector(run_dir, o).bisect()


def run(a) -> int:
    try:
        r = execute_json(a.run_dir, a.good, project=getattr(a, "project", None), bad=a.bad, core_repo=a.core_repo, core_env=a.core_env,
                         workdir=a.workdir, signature=a.signature, other=a.other,
                         no_verify=a.no_verify, remove_clone=a.remove_clone, timeout=a.timeout,
                         max_cycles=a.max_cycles, hang_cycles=a.hang_cycles)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"rvw bisect: {e}", file=sys.stderr)
        return 2
    res = r["result"]
    if a.json:
        try:
            jsonout.write(r, indent=1)
        except jsonout.JsonOutputError as e:
            print(f"rvw bisect: {e}", file=sys.stderr)
            return 2
    elif res.get("first_bad"):
        print(f"first bad commit: {res['commit']}  (details: {r['workdir']}/bisect.md)")
    else:
        print(f"no single first bad commit: {res.get('error') or res.get('note')}")
    return 0 if res.get("first_bad") else 1
