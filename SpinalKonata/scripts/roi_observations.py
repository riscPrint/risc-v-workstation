#!/usr/bin/env python3
"""BOOM benchmark-only inspection of setStats marker retirement boundaries.

These are trace observation windows, not a replacement for benchmark CSR counters.
The generic rvw parser and analyzer do not know these symbols or stage names.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory

from rvw.common.capture import Capture
from rvw.common.proc import run_group
from captured import capture_run

from rvw.perf.classify import identify
from rvw.perf.kanata import read, Trace
from rvw.perf.analysis import _bubbles


def observe(run):
    with TemporaryDirectory(prefix="konata-roi-") as temporary:
        capture = Capture(Path(temporary) / "inputs")
        inputs = capture_run(capture, run)
        env = capture.env("RISCV_OBJDUMP")
        objdump = capture.tool(env["RISCV_OBJDUMP"] or
            "riscv64-unknown-elf-objdump")
        report = observe_captured(inputs, objdump)
        capture.verify_tools()
        report["capture"] = capture.record()
        report["cache_key"] = None
        return report


def observe_captured(inputs, objdump, full=None):
    trace = read(inputs.trace.copy)
    output = run_group([str(objdump.path), "-d", str(inputs.elf.copy)], capture=True, timeout=30)
    if output.timed_out or output.returncode:
        raise ValueError("inconclusive: objdump did not finish successfully")
    assembly = output.stdout
    match = re.search(r"^([0-9a-f]+) <setStats>:\n\s*([0-9a-f]+):[^\n]*\bcsrr\s+\w+,mcycle", assembly, re.M)
    if not match:
        raise ValueError("expected setStats entry to read mcycle")
    marker_pc = hex(int(match[2], 16))
    markers = sorted(i.end for i in trace.instructions.values() if i.end is not None and not i.flushed
                     and identify(i.labels, "riscv")[0] == marker_pc)
    if len(markers) != 2:
        raise ValueError(f"expected two retired setStats mcycle markers, found {markers}")
    start, end = markers
    commits = Counter()
    stage_cycles = Counter()
    stage_class_cycles = defaultdict(Counter)
    pc_cycles = Counter()
    flushes = Counter()
    queue_waits = defaultdict(list)
    labelled = {}
    for ins in trace.instructions.values():
        pc, cls = identify(ins.labels, "riscv")
        labelled.setdefault(pc, ins.labels.get("0", ""))
        if ins.end is not None and start <= ins.end < end:
            if ins.flushed:
                flushes[pc] += 1
            else:
                commits[ins.end] += 1
        spans = [s for s in ins.spans if s.lane == "0"]
        q = [s.start for s in spans if s.stage == "Iq"]
        issue = [s.start for s in spans if s.stage == "Is"]
        if q and issue and start <= min(issue) < end:
            queue_waits[cls].append(min(issue) - min(q))
        for span in spans:
            duration = max(0, min(span.end if span.end is not None else end, end) - max(span.start, start))
            stage_cycles[span.stage] += duration
            stage_class_cycles[cls][span.stage] += duration
            pc_cycles[pc, span.stage] += duration
    full = full if full is not None else json.loads(inputs.report.copy.read_text())
    bubble_details = _bubbles(Trace(trace.instructions, start, end - 1, 0, []), commits, "Iq", "0")
    return {"schema": "spinalkonata.roi-observation/1", "marker_pc": marker_pc,
            "start": start, "end_exclusive": end, "cycles": end - start,
            "instret": sum(commits.values()), "ipc": sum(commits.values()) / (end - start),
            "retirement_basis": "Physical BOOM ROB commit records; includes predicated-off operations. This is event IPC, not architectural IPC.",
            "commit_bubble_cycles": end - start - len(commits),
            "inferred_head_residency_during_bubbles": bubble_details["head_residency"],
            "discarded_instructions_ending_in_window": sum(flushes.values()),
            "stage_resident_instruction_cycles_clipped_to_window": dict(stage_cycles),
            "class_stage_cycles": {c: dict(v) for c, v in stage_class_cycles.items()},
            "first_issue_queue_mean_by_class": {c: {"n": len(v), "mean": sum(v)/len(v), "max": max(v)}
                                                 for c, v in queue_waits.items()},
            "top_pc_stage_residency": [{"pc": pc, "stage": s, "cycles": n, "label": labelled[pc]}
                                       for (pc, s), n in pc_cycles.most_common(20)],
            "retired_commit_window_count_note": "Includes first marker R, excludes second marker R; creation/stage intervals are clipped, so their sums are instruction-cycles, not wall time.",
            "scope_note": "Two committed setStats-entry mcycle-read R events bound this trace window. R occurs one cycle after commit. This is an observation window and may differ slightly from CSR sampling boundaries. No exact gem5 comparison is claimed.",
            "full_run_counter_check": full.get("cross_check")}


if __name__ == "__main__":
    print(json.dumps(observe(sys.argv[1]), indent=2))
