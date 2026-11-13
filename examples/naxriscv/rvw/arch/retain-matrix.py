#!/usr/bin/env python3
"""Retain compact native receipts and hashes. Keep full captures in the run root."""
import hashlib
import json
from pathlib import Path
import sys


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def main(run_root, out):
    root = Path(run_root)
    summary = json.loads((root/"summary.json").read_text())
    if len(summary) != 30:
        raise ValueError("expected six programs on base and four variants")
    rows = []
    for row in summary:
        run = root/row["variant"]/row["program"]
        c1 = json.loads((run/"result.json").read_text())
        spike = row["spike"]
        if spike["status"] != "match" or not spike["trace_complete"]:
            raise ValueError("complete Spike match required")
        rows.append(dict(
            **{k:row[k] for k in ("variant","program","config","changes","cycles","instret","ipc","elf_sha256")},
            native_cache_hit=c1["details"]["simulation_session"]["verilator_cached"],
            native_inputs_sha256=c1["tools"]["native_build"]["sha256"],
            seed=c1["seed"], mem_latency=c1["mem_latency"], status=c1["status"],
            core_revision=c1["source"]["core_rev_full"], rtl_sha256=c1["rtl_sha256"],
            artifacts={name:digest(run/name) for name in
                       ("result.json","rvfi.jsonl","probe-events.jsonl","spike.json")},
            spike={k:spike.get(k) for k in
                   ("status","instructions","trap_events","trace_complete","synchronized","reference_limits")},
            topdown=row["topdown"]["fractions"], counts=row["counts"]["counts"]))
    report = dict(schema="rvw.nax-rtl-matrix/1", samples=rows,
                  variants={row["variant"]:row["changes"] for row in rows},
                  limits=["simulation only; six whole-program RV32IMA programs",
                          "private core fault controls disabled; no new core source changes",
                          "Spike counter synchronization remains explicit",
                          "project-bound slot partition, not hardware top-down counters",
                          "trace and probe captures retained under $RUN_ROOT/<variant>/<program>"])
    Path(out).write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    main(*sys.argv[1:])
