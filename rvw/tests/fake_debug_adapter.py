#!/usr/bin/env python3
"""A fake C1 core adapter for testing rvw bundle/reduce/bisect without a real core.

Model: with randomized memory timing (no --mem-latency), seeds divisible by 3 hit an assertion
"lsu.scala:1241" at cycle 1000 + (seed * 7919) % 5000; fixed latency 1 asserts at cycle 700;
everything else passes at cycle 8000. With FAKE_CORE=DIR, the bug exists only if DIR/bug exists
(for bisect). Retires one instruction every 2 cycles. Writes result.json, rvfi.jsonl
(--rvfi-trace) and wave.vcd (--wave, limited to --wave-from/--wave-to cycles).

FAKE_COMMIT_SKEW=K: instructions commit in the wave (signal `commit`) at an irregular pattern of
cycles, and the RVFI trace stamps each retirement K cycles later (like BOOM's 2).
FAKE_WAVE_T1=T: wave time of cycle 1 (default 10; BOOM's reset offset makes it ~170).
FAKE_HANG=N: the program stops retiring at cycle N and never finishes (status timeout at max
cycles). FAKE_SYMBOL=NAME>=V: the assertion fires (cycle 700) only if the ELF's integer data symbol
NAME is >= V, whatever the seed and latency; otherwise the run passes. A comma list of NAME>=V and
NAME==V conditions fails when any holds (a non-monotone failure).
FAKE_NO_RVFI_END=1: the RVFI trace has no C2 end event (a capture that stopped early).
FAKE_INCONCLUSIVE=1: a failing result carries the C1 `inconclusive` field. FAKE_WALL_CLOCK=1 (or, with FAKE_CORE=DIR, a file DIR/slow): the run ends as a wall-clock timeout
at cycle 1024 (status timeout, wall_clock_timeout true, as RiscvSim writes it).
FAKE_ERROR=1: the run ends as a harness `error` ("harness could not load variant") at cycle 100.
FAKE_SYNTH=1: the result carries `synthesized: true` (a result rvw wrote, not the adapter).
"""
import hashlib
import json
import os
import sys
import time


def opts(argv):
    o, i = {}, 0
    while i < len(argv):
        a = argv[i]
        if a in ("--rvfi-trace", "--wave", "--konata", "--coverage", "--spinaltrace", "--json"):
            o[a[2:]] = True
        else:
            o[a[2:]] = argv[i + 1]
            i += 1
        i += 1
    return o


def fail_cycle(seed, lat, elf=None):
    core = os.environ.get("FAKE_CORE")
    if core and not os.path.exists(os.path.join(core, "bug")):
        return None
    sym = os.environ.get("FAKE_SYMBOL")
    if sym:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
        from rvw.runs.elf import Elf
        for cond in sym.split(","):          # any of NAME>=V or NAME==V
            op = ">=" if ">=" in cond else "=="
            name, v = cond.split(op)
            x = Elf(elf).read_int(name)
            if (x >= int(v)) if op == ">=" else (x == int(v)):
                return 700
        return None
    if lat is None:
        return 1000 + (seed * 7919) % 5000 if seed % 3 == 0 else None
    return 700 if lat == 1 else None


def commit_cycle(i):
    return 2 * i + 1 + (((i * 2654435761) >> 9) & 1)     # irregular (no short period)


def core_rev():
    core = os.environ.get("FAKE_CORE")
    if not core:
        return None
    import subprocess
    return subprocess.run(["git", "-C", core, "rev-parse", "--short", "HEAD"], capture_output=True,
                          text=True).stdout.strip() or None


def run(o):
    out = o["out"]
    os.makedirs(out, exist_ok=True)
    seed = int(o.get("seed", 12345))
    lat = int(o["mem-latency"]) if "mem-latency" in o else None
    maxc = int(o.get("max-cycles", 200000))
    core = os.environ.get("FAKE_CORE")
    if core and os.path.exists(os.path.join(core, "build-broken")):
        sys.exit("build failed")
    fc = fail_cycle(seed, lat, o.get("elf"))
    hang = int(os.environ["FAKE_HANG"]) if os.environ.get("FAKE_HANG") else None
    end = 8000 if hang is None else maxc + 1
    status, msg = "pass", None
    if fc is not None and fc <= maxc:
        end, status, msg = fc, "assert", f"Assertion failed: (lsu.scala:1241) at cycle {fc}"
    elif end > maxc:
        end, status = maxc, "timeout"
    wall = bool(os.environ.get("FAKE_WALL_CLOCK")) or bool(core and os.path.exists(os.path.join(core, "slow")))
    if wall:
        end, status, msg = min(end, 1024), "timeout", "wall-clock timeout after 5 s at cycle 1024"
    if os.environ.get("FAKE_ERROR"):
        end, status, msg = 100, "error", "harness could not load variant"
    retired_until = end if hang is None else min(end, hang)
    skew = int(os.environ["FAKE_COMMIT_SKEW"]) if os.environ.get("FAKE_COMMIT_SKEW") else None
    commits = {commit_cycle(i) for i in range(retired_until // 2 + 1)} if skew is not None else set()
    arts = {"log": "run.log"}
    with open(os.path.join(out, "run.log"), "w") as f:
        f.write(f"fake run seed={seed} lat={lat} -> {status}\n")
    if o.get("rvfi-trace"):
        with open(os.path.join(out, "rvfi.jsonl"), "w") as f:
            f.write(json.dumps({"schema": "rvw.rvfi/1", "xlen": 64, "core": "fake"}) + "\n")
            for i in range(retired_until // 2):
                pc = 0x80000000 + 4 * (i % 40)
                cyc = commit_cycle(i) + skew if skew is not None else 2 * i + 1
                if cyc > end:
                    break
                f.write(json.dumps({"order": i, "cycle": cyc, "pc": hex(pc), "pc_next": hex(pc + 4),
                                    "insn": "0x00000013", "rd": 0, "rd_wdata": "0x0", "trap": False}) + "\n")
            if not os.environ.get("FAKE_NO_RVFI_END"):     # C2 end event, as RiscvSim writes it
                f.write(json.dumps({"event": "end", "cycle": end, "status": status}) + "\n")
        arts["rvfi_trace"] = "rvfi.jsonl"
    t1 = int(os.environ.get("FAKE_WAVE_T1", "10"))   # wave time of cycle 1 (reset offset)
    T = lambda c: t1 + (c - 1) * 10
    details = {"wave_time_per_cycle": 10, "wave_time_of_cycle_1": t1}
    if os.environ.get("FAKE_NO_DETAILS"):
        details = {}
    if o.get("wave"):
        lo = int(o.get("wave-from", 0))
        hi = min(int(o.get("wave-to", end)), end)
        if "wave-from" in o or "wave-to" in o:
            details["wave_window"] = {"from": int(o["wave-from"]) if "wave-from" in o else None,
                                      "to": int(o["wave-to"]) if "wave-to" in o else None}
        with open(os.path.join(out, "wave.vcd"), "w") as f:
            f.write("$timescale 1ps $end\n$scope module TOP $end\n$var wire 1 ! clk $end\n"
                    "$scope module Fake $end\n$var wire 16 \" count [15:0] $end\n"
                    "$var wire 1 # busy $end\n$var wire 1 % commit $end\n$upscope $end\n$upscope $end\n"
                    "$enddefinitions $end\n")
            for c in range(lo, hi + 1):
                f.write(f"#{T(c)}\n1!\nb{c & 0xffff:b} \"\n{1 if c % 7 == 0 else 0}#\n{1 if c in commits else 0}%\n#{T(c) + 5}\n0!\n")
        arts["wave"] = "wave.vcd"
    replay = " ".join([os.path.abspath(__file__), "run", "--elf", o["elf"], "--seed", str(seed),
                       "--max-cycles", str(maxc)] + (["--mem-latency", str(lat)] if lat is not None else [])
                      + ["--out", out])
    res = {"schema": "rvw.run/1", "core": "fake", "config": o.get("config", "small"), "elf": o["elf"],
           "elf_sha256": hashlib.sha256(open(o["elf"], "rb").read()).hexdigest(), "seed": seed, "max_cycles": maxc, "mem_latency": lat, "status": status,
           "fail_code": None, "message": msg, "cycles": end, "instret": retired_until // 2, "wall_s": 0.01,
           "source": {"core_repo": os.environ.get("FAKE_CORE"), "core_rev": core_rev()},
           "artifacts": arts, "replay": replay, "details": details}
    if wall:
        res["wall_clock_timeout"] = True
    if os.environ.get("FAKE_SYNTH"):
        res["synthesized"] = True
    if os.environ.get("FAKE_INCONCLUSIVE") and status != "pass":
        res["inconclusive"] = "failure while other simulations ran; not attributed (fake)"
    with open(os.path.join(out, "result.json"), "w") as f:
        json.dump(res, f, indent=1)
    calls = os.environ.get("FAKE_CALLS")
    if calls:
        with open(calls, "a") as f:
            f.write(json.dumps({"seed": seed, "lat": lat, "max": maxc, "t": time.time()}) + "\n")


def main():
    sub, o = sys.argv[1], opts(sys.argv[2:])
    if sub == "run":
        run(o)
    elif sub == "run-many":
        with open(o["manifest"]) as f:
            for line in f:
                if line.strip():
                    j = json.loads(line)
                    run({k.replace("_", "-"): (True if v is True else str(v)) for k, v in j.items()
                         if v is not None and v is not False})
    elif sub == "build":
        pass
    else:
        sys.exit(f"unknown subcommand {sub}")


if __name__ == "__main__":
    main()
