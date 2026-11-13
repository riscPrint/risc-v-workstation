#!/usr/bin/env python3
"""Build a saved-evidence plan and run the existing OoO calibration command."""
import argparse
import json
from pathlib import Path

from rvw.cli import main
from rvw.probes.api import run_convert


def calibrate():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--runs", required=True, type=Path, help="smoke, branches and throughput C1 run directories")
    parser.add_argument("--out", required=True, type=Path, help="new output directory")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    samples = []
    for index, name in enumerate(("smoke", "branches", "throughput")):
        run = (args.runs / name).resolve()
        c1 = json.loads((run / "result.json").read_text())
        counts = (args.out / (name + "-counts.json")).resolve()
        run_convert(run / "probe-events.jsonl", "counts", counts,
                    c1=run / "result.json", c2=run / "rvfi.jsonl")
        samples.append(dict(id=name, split="training" if index == 0 else "heldout",
                            elf=c1["elf"], trace=str(run / "rvfi.jsonl"),
                            c1=str(run / "result.json"), events=str(counts)))
    config = args.config.resolve()
    plan = (args.out / "plan.json").resolve()
    plan.write_text(json.dumps(dict(schema="rvw.ooo-calibration-plan/1", config=str(config),
                                   event_map=str(config.parent / "event-map.json"), samples=samples), indent=2) + "\n")
    return main(["arch", "ooo-calibrate", str(plan), "--out", str(args.out / "report.json"), "--json"])


if __name__ == "__main__":
    raise SystemExit(calibrate())
