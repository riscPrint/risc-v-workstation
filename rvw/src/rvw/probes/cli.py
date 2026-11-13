"""rvw probes: list a design's probes, show the consumers they enable, convert event streams."""
import json
import sys
from pathlib import Path

from . import api
from .convert import CONVERTERS


def register(subparsers):
    parser = subparsers.add_parser("probes", help="simulation probes: list, consumer gaps, convert events")
    sub = parser.add_subparsers(dest="probes_command", required=True)
    check = sub.add_parser("check", help="name missing required probe kinds or kind/name bindings")
    src = check.add_mutually_exclusive_group(required=True)
    src.add_argument("--db", type=Path)
    src.add_argument("--events", type=Path)
    check.add_argument("--consumer", help="consumer ID, such as perf-causal; name each missing field binding")
    check.add_argument("--require", action="append")
    check.add_argument("--validate", action="store_true",
                       help="validate the event stream against the contract (ordering, fields, counters, IDs)")
    check.add_argument("--c2", type=Path, help="the run's rvfi.jsonl: also check retired-event probes against it")
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=_check)
    ls = sub.add_parser("list", help="list probes from a design database or an event stream, with the consumers they enable")
    src = ls.add_mutually_exclusive_group(required=True)
    src.add_argument("--db", type=Path, help="design database built with probes enabled")
    src.add_argument("--events", type=Path, help="rvw.probe-events/1 stream (probe-events.jsonl)")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=_list)
    sm = sub.add_parser("summary", help="event counts and counter totals of an event stream")
    sm.add_argument("events", type=Path)
    sm.set_defaults(func=_summary)
    cv = sub.add_parser("convert", help="write a consumer tool's format from an event stream")
    cv.add_argument("events", type=Path)
    cv.add_argument("--to", required=True, choices=sorted(CONVERTERS))
    cv.add_argument("--out", required=True, type=Path, help="new output file")
    cv.add_argument("--c2", type=Path, help="the run's rvfi.jsonl (bp-events, counts, interrupts, bus, csr-writes, mmu-walks, mmu identity)")
    cv.add_argument("--c1", type=Path, help="the run's result.json (counts)")
    cv.add_argument("--probe", help="probe name when several probes of the kind exist")
    cv.add_argument("--roi", help="START:END C2 orders (bp-events)")
    cv.add_argument("--elf", type=Path, help="the run's ELF (cache-check; default: the stream identity)")
    cv.add_argument("--geometry", action="append", metavar="CACHE=SETSxWAYS", help="cache geometry (cache-check)")
    cv.add_argument("--json", action="store_true")
    cv.set_defaults(func=_convert)


def _fail(e):
    print(json.dumps({"status": "error", "error": str(e)}), file=sys.stderr)
    return 2


def _list(args):
    try:
        rep = api.report(db=args.db, events=args.events)
    except (ValueError, OSError) as e:
        return _fail(e)
    if args.json:
        print(json.dumps(rep, indent=1))
        return 0
    for p in rep["probes"]:
        print(f"{p['kind']:9} {p['name']:28} {', '.join(p['fields'])}")
    if not rep["probes"]:
        print(rep["note"])
    print()
    for r in rep["consumers"]:
        detail = ", ".join(r["probes"]) if r["status"] == "enabled" else "; ".join(r["missing"]) or r["note"]
        print(f"{r['status']:12} {r['tool']:44} {detail}")
    return 0


def _summary(args):
    try:
        print(json.dumps(api.summary(args.events), indent=1))
    except (ValueError, OSError) as e:
        return _fail(e)
    return 0


def _convert(args):
    roi = None
    if args.roi:
        a, b = args.roi.split(":")
        roi = (int(a), int(b))
    try:
        rep = api.run_convert(args.events, args.to, args.out, c2=args.c2, c1=args.c1, probe=args.probe, roi=roi,
                              elf=args.elf, geometry=args.geometry)
    except (ValueError, OSError, KeyError) as e:
        return _fail(e)
    rep = {"status": "written", "out": str(args.out), **rep}
    print(json.dumps(rep, indent=1) if args.json else f"wrote {args.out}: {json.dumps(rep)}")
    return 0


def _check(args):
    from .check import check
    try:
        result = check(db=args.db, events=args.events, require=args.require, c2=args.c2, validate=args.validate, consumer=args.consumer)
    except (ValueError, OSError) as exc:
        return _fail(exc)
    print(json.dumps(result, indent=2))
    if result['status'] == 'violations':
        return 1
    return 3 if result['missing_probes'] or result['status'] == 'inconclusive' else 0
