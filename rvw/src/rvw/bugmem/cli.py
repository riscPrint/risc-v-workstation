"""`rvw bugmem`: remember failure signatures with their root causes; match new failures."""
from __future__ import annotations

import argparse
import sys

from ..common import jsonout
from .memory import BugMemError, Store


def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("bugmem", help="store failure signatures and root causes; match new failures",
                       description=__doc__)
    w = p.add_subparsers(dest="bugmem_cmd", required=True)

    def common(q):
        q.add_argument("--store", help="JSON-lines store (default: RVW_BUGMEM or ~/.local/share/rvw/bugmem.jsonl)")
        q.add_argument("--json", action="store_true")

    q = w.add_parser("add", help="store a failure report with its root cause")
    q.add_argument("report", help="bundle summary.json, bundle dir, C1 result.json or run dir")
    q.add_argument("--cause", required=True, help="root cause, in words")
    q.add_argument("--fix", help="fix (commit, PR or description)")
    q.add_argument("--scope", help="where the fix was verified (tests, configs, seeds)")
    q.add_argument("--label", help="defect class label, used by `evaluate`")
    common(q)
    q.set_defaults(func=_add)

    q = w.add_parser("match", help="stored failures similar to a new failure report")
    q.add_argument("report")
    q.add_argument("--top", type=int, default=5)
    q.add_argument("--min-score", type=float, default=0.2)
    common(q)
    q.set_defaults(func=_match)

    q = w.add_parser("list", help="stored failures")
    common(q)
    q.set_defaults(func=_list)

    q = w.add_parser("evaluate", help="leave-one-out matching accuracy over labelled entries")
    q.add_argument("--top", type=int, default=3)
    common(q)
    q.set_defaults(func=_evaluate)


def _run(fn):
    def call(a):
        try:
            r = fn(a, Store(a.store))
            if a.json:
                jsonout.write(r)
            return 0
        except BugMemError as e:
            if a.json:
                jsonout.write({"error": str(e)})
            print(f"rvw bugmem: {e}", file=sys.stderr)
            return 2
    return call


@_run
def _add(a, store):
    e = store.add(a.report, a.cause, a.fix, a.scope, a.label)
    if not a.json:
        print(f"stored {e['id']}: {len(e['features'])} features, signature {e['signature']}")
    return e


@_run
def _match(a, store):
    r = store.match(a.report, a.top, a.min_score)
    if not a.json:
        print(f"# {r['status']}: {len(r['candidates'])} of {r['stored']} stored failures (similarity, not diagnosis)")
        for c in r['candidates']:
            print(f"{c['score']:.2f} {c['id']} {c['signature']}: {c['cause']}")
            print(f"     shared: {', '.join(c['shared'])}")
            if c.get('fix'):
                print(f"     fix: {c['fix']}" + (f" (verified: {c['scope']})" if c.get('scope') else ""))
    return r


@_run
def _list(a, store):
    entries = store.entries()
    if not a.json:
        for e in entries:
            print(f"{e['id']} {e['added']} {e['signature']} [{e.get('label') or '-'}]: {e['cause']}")
    return {"store": str(store.path), "entries": entries}


@_run
def _evaluate(a, store):
    r = store.evaluate(a.top)
    if not a.json:
        acc = r['top1_accuracy']
        print(f"held out {r['held_out']} of {r['labelled']} labelled ({r['unmatchable']} unmatchable): "
              f"top-1 {'n/a' if acc is None else f'{acc:.2f}'}")
    return r
