#!/usr/bin/env python3
"""A fake core adapter that follows contract C1, for testing `rvw regress` without a simulator.

A "program" is a text file of `key=value` directives (one line):
    status=pass|fail|assert|timeout|rvfi_error|error   (default pass)
    fail_code=N  message=TEXT_WITH_UNDERSCORES  cycles=N  instret=N  roi_cycles=N  roi_instret=N
    fail_seeds=1,3       fail (code 7) only for these seeds
    sleep=S              take S seconds (to test wall-clock timeouts)
    crash=1              kill the whole adapter process (to test batch isolation)
    unattributed=1       a failure of a run that overlapped others, whose serial rerun could not
                         attribute it (RiscvSim's details.serial_rerun.attributed = false)
    pending=1            such a failure before its serial rerun (details.concurrent, no serial_rerun)
    inconclusive=TEXT    the C1 `inconclusive` field (underscores become spaces)
The core source tree is `$FAKE_SRC` (like SPINAL_BOOM): if it holds `overrides.json`, mapping a
program's file name to a directive line, that replaces the program's own directives, so different
revisions of the fake core behave differently. `$FAKE_ADAPTER_LOG` gets one line per command.
`$FAKE_BUILD_FAIL` makes `build` fail. `identity` prints `$FAKE_TOOLCHAIN` (default fake-1);
`$FAKE_IDENTITY_FAIL` makes it fail.
"""
import argparse
import concurrent.futures as cf
import hashlib
import functools
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def log(*words):
    p = os.environ.get("FAKE_ADAPTER_LOG")
    if p:
        with open(p, "a") as f:
            f.write(" ".join(map(str, words)) + "\n")


def directives(elf: Path) -> dict:
    text = elf.read_text().strip()
    src = os.environ.get("FAKE_SRC")
    if src and (Path(src) / "overrides.json").is_file():
        ov = json.loads((Path(src) / "overrides.json").read_text())
        text = ov.get(elf.name, text)
    d = {}
    for w in text.split():
        k, _, v = w.partition("=")
        d[k] = v
    return d


@functools.cache
def source_info():
    if os.environ.get("RVW_CAPTURE_SOURCE"):
        return {**json.loads(os.environ["RVW_CAPTURE_SOURCE"]), "tools_rev": "fake"}
    from rvw.regress.source import describe
    src = os.environ.get("FAKE_SRC")
    return {**describe(Path(src) if src else None).to_dict(), "tools_rev": "fake"}


def run_one(job: dict) -> None:
    elf = Path(job["elf"])
    out = Path(job["out"])
    out.mkdir(parents=True, exist_ok=True)
    seed = job.get("seed")
    if seed is None:
        seed = 4242
    log("run", elf.name, "seed", seed, "config", job.get("config"), "mem_latency", job.get("mem_latency"))
    d = directives(elf)
    if d.get("crash"):
        os._exit(3)
    if d.get("sleep"):
        time.sleep(float(d["sleep"]))
    status = d.get("status", "pass")
    fail_code = int(d["fail_code"]) if "fail_code" in d else None
    if "fail_seeds" in d and seed in {int(x) for x in d["fail_seeds"].split(",")}:
        status, fail_code = "fail", 7
    metrics = {}
    for k in ("roi_cycles", "roi_instret"):
        if k in d:
            metrics[k] = int(d[k])
    (out / "run.log").write_text(f"fake run of {elf}\n")
    res = {
        "schema": "rvw.run/1", "core": "fake", "config": job.get("config", "small"),
        "elf": str(elf), "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
        "seed": seed, "max_cycles": job.get("max_cycles"), "mem_latency": job.get("mem_latency"),
        "status": status, "fail_code": fail_code if status == "fail" else None,
        "message": d.get("message", "").replace("_", " ") or None,
        "cycles": int(d.get("cycles", 100)), "instret": int(d.get("instret", 50)), "wall_s": 0.01,
        "source": source_info(), "tools": {"fake": "1"}, "artifacts": {"log": "run.log"},
        "replay": f"fake_adapter.py run --elf {elf} --seed {seed} --out {out}",
    }
    if metrics:
        res["metrics"] = metrics
    if d.get("unattributed") or d.get("pending"):
        res["details"] = {"concurrent": True}
        if d.get("unattributed"):
            res["message"] = f"{status} while other simulations ran; message not attributable"
            res["details"]["serial_rerun"] = {"first": {"status": status}, "rerun_status": "not alone",
                                              "attributed": False}
    if d.get("inconclusive"):
        res["inconclusive"] = d["inconclusive"].replace("_", " ")
    (out / "result.json").write_text(json.dumps(res, indent=2))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--config", required=True)
    b.add_argument("--rvfi", action="store_true")
    b.add_argument("--json", action="store_true")
    r = sub.add_parser("run")
    r.add_argument("--elf", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--config", default="small")
    r.add_argument("--seed", type=int)
    r.add_argument("--max-cycles", type=int)
    r.add_argument("--mem-latency", type=int)
    m = sub.add_parser("run-many")
    m.add_argument("--manifest", required=True)
    m.add_argument("--jobs", type=int, default=1)
    sub.add_parser("identity")
    a = p.parse_args()
    if a.cmd == "identity":
        log("identity")
        if os.environ.get("FAKE_IDENTITY_FAIL"):
            return 1
        print(f"toolchain {os.environ.get('FAKE_TOOLCHAIN', 'fake-1')}")
        return 0
    if a.cmd == "build":
        log("build", a.config, "src", os.environ.get("FAKE_SRC"))
        if os.environ.get("FAKE_BUILD_FAIL"):
            print("error: elaboration failed at Foo.scala:12", file=sys.stderr)
            return 1
        if a.json:
            print(json.dumps({"config": a.config, "status": "ok"}))
        return 0
    if a.cmd == "run":
        run_one({"elf": a.elf, "out": a.out, "config": a.config, "seed": a.seed, "max_cycles": a.max_cycles,
                 "mem_latency": a.mem_latency})
        return 0
    jobs = [json.loads(l) for l in Path(a.manifest).read_text().splitlines() if l.strip()]
    log("run-many", len(jobs))
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        list(ex.map(run_one, jobs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
