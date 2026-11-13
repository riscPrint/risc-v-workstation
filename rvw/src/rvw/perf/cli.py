import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from rvw.common.capture import Capture, CaptureError
from rvw.common.jsonout import write

from .analysis import analyze, compare, render
from .inputs import capture_input
from . import topdown


def register(subparsers):
    parser = subparsers.add_parser("perf", help="Measure Kanata 0004 pipeline traces")
    parser.add_argument("paths", nargs="+", help="LOG, compare A B (logs or rvw.perf/1 JSON), or topdown EVENTS")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--window", type=int, default=1000)
    parser.add_argument("--isa", choices=("none", "riscv"), default="none")
    parser.add_argument("--lane", default="0")
    parser.add_argument("--queue-stage")
    parser.add_argument("--issue-stage")
    parser.add_argument("--head-stage")
    parser.add_argument("--in-order-retirement", action="store_true")
    parser.add_argument("--result", help="C1 result.json (otherwise discovered beside log)")
    parser.add_argument("--tolerance", type=float, default=.05, help="comparison relative magnitude threshold")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--c2", help="topdown: the run's rvfi.jsonl; retiring slots must equal its retirements")
    parser.set_defaults(func=run)


def calculate(args):
    """Return the CLI JSON report for reuse by MCP."""
    if args.paths[0] == "topdown":
        if len(args.paths) != 2:
            raise ValueError("usage: rvw perf topdown EVENTS [--c2 RVFI] [--result RESULT]")
        return topdown.report(args.paths[1], c2=getattr(args, "c2", None), c1=args.result)
    options = {key: getattr(args, key) for key in ("window", "isa", "lane", "queue_stage", "issue_stage",
                                                 "head_stage", "in_order_retirement", "result")}
    comparing = len(args.paths) == 3 and args.paths[0] == "compare"
    if comparing and args.result:
        raise ValueError("--result is for single-log analysis; place result.json beside each input log")
    if not comparing and len(args.paths) != 1:
        raise ValueError("usage: rvw perf LOG or rvw perf compare A B")
    paths = args.paths[1:] if comparing else args.paths
    with TemporaryDirectory(prefix="rvw-perf-") as temporary:
        capture = Capture(Path(temporary) / "inputs")
        inputs = [capture_input(capture, path, result=args.result, saved=str(path).endswith(".json"))
                  for path in paths]
        reports = []
        for path, item in zip(paths, inputs):
            if str(path).endswith(".json"):
                with item.trace.copy.open() as stream:
                    report = json.load(stream)
                if report.get("schema") != "rvw.perf/1":
                    raise ValueError("expected rvw.perf/1 report")
                # This is producer-supplied content. The command binds it to the saved JSON.
                report["producer_capture"] = report.pop("capture", None)
            else:
                report = analyze(item, **{key: value for key, value in options.items() if key != "result"})
            reports.append(report)
        report = compare(*reports, args.tolerance) if comparing else reports[0]
        capture.verify_tools()
        report["capture"] = capture.record()
        report["cache_key"] = None
        return report


def run(args):
    try:
        report = calculate(args)
        if args.json:
            write(report)
        elif report.get("schema") == topdown.SCHEMA:
            print(topdown.render(report))
        else:
            print(render(report, args.top))
        return 0
    except CaptureError as exc:
        if args.json:
            write({"status": "inconclusive", "cause": exc.cause, "message": str(exc), "cache_key": None})
        else:
            print(f"rvw perf: inconclusive: {exc}", file=sys.stderr)
        return 3
    except (OSError, ValueError, KeyError) as exc:
        print(f"rvw perf: {exc}", file=sys.stderr)
        return 2


def execute_json(paths: list[str], **options) -> dict:
    from argparse import Namespace
    defaults = dict(window=1000, isa="none", lane="0", queue_stage=None, issue_stage=None,
                    head_stage=None, in_order_retirement=False, result=None, tolerance=.05, c2=None)
    unknown = options.keys() - defaults.keys()
    if unknown:
        raise TypeError(f"unknown options: {sorted(unknown)}")
    defaults.update(options)
    return calculate(Namespace(paths=paths, **defaults))
