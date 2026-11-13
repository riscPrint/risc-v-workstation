#!/usr/bin/env python3
"""Calibrate the OoO model description (ooo.json) against NaxRiscv RTL runs.

Usage: calibrate.py RUNS OUT
RUNS holds one directory per benchmark with result.json, rvfi.jsonl and counts.json from
`rvw/run.sh run --probes --rvfi-trace` and `rvw probes convert --to counts`; the ELFs are in
rvw/out/bench/<name>.riscv. Training and held-out programs are disjoint. The fit searches the
branch penalty, fetch latency and load latency on training programs only, then scores the
held-out programs (`rvw arch ooo-fit`). It also writes model and RTL top-down partitions.
"""
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
TRAIN = ("median", "qsort", "multiply")
HELD = ("towers", "vvadd", "rsort", "memcpy", "dhrystone")  # spmv exceeds the 1M-cycle model budget
EVENTS = {"branches": dict(model_event="branches", rtl_event="branches", edge="retirement", unit="instructions",
                           identity="retired conditional branches and jumps (RTL: branch-context learn port)",
                           family="control", region="whole-program")}
GRID = {"branch_penalty": [6, 8, 10], "frontend.fetch_latency": [2, 3, 4], "latencies.load": [2, 3, 4]}


def main(runs, out):
    runs, out = Path(runs).resolve(), Path(out).resolve()
    out.mkdir(parents=True)
    (out / "event-map.json").write_text(json.dumps(EVENTS, indent=1))
    samples = [dict(id=n, split="training" if n in TRAIN else "heldout", elf=str(HERE.parent / "out/bench" / f"{n}.riscv"),
                    trace=str(runs / n / "rvfi.jsonl"), c1=str(runs / n / "result.json"), events=str(runs / n / "counts.json"))
               for n in TRAIN + HELD]
    plan = dict(schema="rvw.ooo-calibration-plan/1", config=str(HERE / "ooo.json"), event_map="event-map.json", samples=samples)
    (out / "calibration-plan.json").write_text(json.dumps(plan, indent=1))
    (out / "fit-plan.json").write_text(json.dumps(dict(schema="rvw.ooo-fit-plan/1", calibration_plan="calibration-plan.json",
                                                       parameters=GRID), indent=1))
    rvw = Path(sys.executable).with_name("rvw")
    with (out / "fit-stdout.json").open("w") as f:
        subprocess.run(["nice", "-n", "10", str(rvw), "arch", "ooo-fit", str(out / "fit-plan.json"),
                        "--out", str(out / "fit"), "--json"], stdout=f, check=True)
    best = out / "fit" / "best-config.json"
    rows = []
    for n in TRAIN + HELD:
        model = json.loads(subprocess.run([str(rvw), "ooo", str(best), str(runs / n / "rvfi.jsonl"), "--json"],
                                          capture_output=True, text=True, check=True).stdout)
        rtl = json.loads((runs / n / "topdown.json").read_text())
        c1 = json.loads((runs / n / "result.json").read_text())
        rows.append(dict(program=n, split="training" if n in TRAIN else "heldout", rtl_cycles=c1["cycles"],
                         instructions=c1["instret"], rtl_ipc=c1["instret"] / c1["cycles"], model_cycles=model["cycles"],
                         model_ipc=model["ipc"], ipc_error_pct=100 * (model["ipc"] * c1["cycles"] / c1["instret"] - 1),
                         rtl_topdown=rtl["fractions"], model_topdown=model["topdown"]["fractions"]))
    (out / "summary.json").write_text(json.dumps(rows, indent=1))
    for r in rows:
        print(f"{r['program']:10s} {r['split']:8s} rtl {r['rtl_ipc']:.3f} model {r['model_ipc']:.3f} "
              f"error {r['ipc_error_pct']:+.1f}%")


if __name__ == "__main__":
    main(*sys.argv[1:])
