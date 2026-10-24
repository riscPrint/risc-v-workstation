"""Build a C5 failure bundle from a failed C1 run directory."""
from __future__ import annotations

import json
import dataclasses
import os
import re
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .. import runs
from ..runs import adapter
from ..runs.inputs import DebugInputs, snapshot_elf
from ..wave.capture import scope
from ..wave import ops as wops
from ..wave import vcd
from ..common.jsonout import say
from ..common.proc import run_group
from . import clock as wclock
from . import handshakes, snapshot, trace
from .disasm import Disasm
from rvw.common.riscv import classify


@dataclass
class Options:
    out: Path | None = None
    retired: int = 64              # instructions in retired.txt
    cut_cycles: int = 500          # cycles of wave kept in wave-window.vcd
    rerun: bool = True             # re-run the replay with a wave window if needed
    rerun_window: int = 3000       # cycles of wave to record when re-running
    konata: bool = False           # ask the re-run for a Konata log too
    core_config: str | None = None
    project: str | None = None
    spinaltrace: bool = True
    timeout: float | None = None   # for the re-run
    pdg: str | None = None         # SpinalTrace pdg.json of an instrumented build
    trace_wave: str | None = None  # wave of the instrumented build (default: the run's wave)
    trace_cycles: int = 20         # cycles of wave dyn-pdg unrolls
    log: list[str] = field(default_factory=list)


def _say(o: Options, msg: str) -> None:
    o.log.append(msg)
    say("bundle", msg)


def make(run_dir: str, o: Options) -> dict:
    path = Path(run_dir).resolve()
    directory = path if path.is_dir() else path.parent
    out = Path(o.out or (directory / 'bundle')).resolve()
    inputs = DebugInputs()
    stage = adapter.fresh_dir(out / 'work')
    with scope(inputs):
        report = _make(run_dir, dataclasses.replace(o, out=stage), inputs)
        inputs.publish(out, [*report['files'].values(), 'summary.json', 'summary.md'], source=stage)
        report['out'] = str(out)
        return report


def _make(run_dir: str, o: Options, inputs: DebugInputs) -> dict:
    run = runs.open_run(run_dir, capture=inputs.capture)
    out = Path(o.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg, cfg_path = inputs.config(run.get("core"), o.core_config, project=o.project)
    replay_cmd = inputs.command(run, cfg) if o.rerun or o.spinaltrace else None
    elf = (Path(replay_cmd.get('elf')) if replay_cmd is not None else
           snapshot_elf(run, out, inputs.capture, root=inputs.root))
    o = dataclasses.replace(o)
    if o.pdg and o.spinaltrace:
        o.pdg = str(inputs.file(o.pdg))
    if o.trace_wave and o.spinaltrace:
        o.trace_wave = str(inputs.file(o.trace_wave))
    st = cfg.get('spinaltrace') or {}
    if st.get('pdg') and o.spinaltrace:
        pdg = Path(os.path.expandvars(st['pdg']))
        st['pdg'] = str(inputs.file(pdg))
    if st.get('adapter') and o.spinaltrace:
        exe = Path(st['adapter'])
        exe = exe if exe.is_absolute() else inputs.root / exe
        traced = replay_cmd.set()
        traced.exe = [str(exe)]
        st['captured_command'] = inputs.bind_adapter(traced)
    cli = inputs.environment.get('SPINALTRACE_CLI') or shutil.which('spinaltrace-cli', path=inputs.environment.get('PATH'))
    if cli is None:
        candidate = inputs.root / 'SpinalTrace/target/release/spinaltrace-cli'
        cli = str(candidate) if candidate.exists() else None
    st['captured_cli'] = inputs.program(cli) if cli and o.spinaltrace else None
    cfg['spinaltrace'] = st
    dis = Disasm(str(elf), capture=inputs.capture, environment=inputs.environment)
    core = cfg.get("core", {})
    sig = runs.signature(run.data)
    status = run.get("status")
    fail_cycle = run.get("cycles")
    S: dict = {"schema": "rvw.bundle/1", "run": str(run.dir), "status": status, "signature": sig,
               "message": run.get("message"), "fail_code": run.get("fail_code"),
               "core": run.get("core"), "config": run.get("config"), "elf": run.get("elf"),
               "seed": run.get("seed"), "mem_latency": run.get("mem_latency"),
               "max_cycles": run.get("max_cycles"), "cycles": fail_cycle, "instret": run.get("instret"),
               "source": inputs.source_metadata(), "recorded_source": run.get("source"), "core_config": str(cfg_path) if cfg_path else None,
               "files": {}, "notes": []}
    if status == "pass":
        S["notes"].append("the run passed; the bundle describes its end state")
    if run.inconclusive:
        S["notes"].append(f"the result is inconclusive ({run.inconclusive}): its message and signature may "
                          "belong to another run; re-run the test alone before trusting this bundle")

    wave = run.artifact("wave")
    rvfi = run.artifact("rvfi_trace")
    konata = run.artifact("konata")
    wave_run = run                       # the run whose wave (and wave clock) the bundle uses
    clk = wclock.wave_clock(run, core, wave)

    # 1. Re-run with a wave window (and RVFI trace) when the run lacks them
    cov, why = wclock.covers(run, wave, fail_cycle, clk) if fail_cycle is not None else (False, "no failure cycle")
    need_wave = not cov
    need_rvfi = rvfi is None
    if wave is not None and need_wave:
        _say(o, f"the run's wave does not cover the failure: {why}")
    if (need_wave or need_rvfi) and o.rerun and fail_cycle is not None:
        lo = max(0, fail_cycle - o.rerun_window)
        hi = fail_cycle + 20
        # First with the RVFI trace; if that model fails differently (e.g. its riscv-formal monitor
        # fires first), once more with the wave only.
        attempts = [("rerun", True), ("rerun-wave", False)]
        for name, with_rvfi in attempts:
            cmd = replay_cmd.set(wave=True, wave_from=lo, wave_to=hi, rvfi_trace=with_rvfi or None,
                                               konata=o.konata or None)
            _say(o, f"re-running with wave cycles {lo}..{hi}: {cmd.set(out=str(out / name)).shell()}")
            at = adapter.execute(cmd, out / name, core=run.get("core"), timeout=o.timeout)
            rr = at.run
            S[name] = {"command": cmd.set(out=str(at.dir)).shell(), "wall_s": round(at.wall, 1),
                       "dir": str(at.dir), "capture": rr.capture.record() if rr and rr.capture else None}
            if rr is None:
                S[name]["error"] = f"{at.error}; see {at.log}"
                _say(o, S[name]["error"])
                break
            rsig = runs.signature(rr.data)
            rinc = rr.inconclusive
            S[name].update({"status": rr.get("status"), "signature": rsig, "cycles": rr.get("cycles"),
                            "reproduced": rinc is None and rsig == sig and rr.get("cycles") == fail_cycle})
            if rinc:
                S[name]["inconclusive"] = rinc
            _say(o, f"re-run: {rsig} at cycle {rr.get('cycles')} ({'same' if rsig == sig else 'DIFFERENT'} signature"
                    + (f"; INCONCLUSIVE: {rinc}" if rinc else "") + ")")
            if rinc:
                S["notes"].append(f"re-run `{name}` is inconclusive ({rinc}); its wave, trace and snapshot are "
                                  "not used")
            elif rsig == sig:
                if rr.get("cycles") != fail_cycle:
                    S["notes"].append(f"re-run `{name}` fails at cycle {rr.get('cycles')}, not {fail_cycle}; "
                                      "the bundle describes the re-run")
                rclk = wclock.wave_clock(rr, core, rr.artifact("wave"))
                rcov, rwhy = wclock.covers(rr, rr.artifact("wave"), rr.get("cycles"), rclk)
                S[name]["wave_covers_failure"] = rcov
                if rr.artifact("wave") is not None:
                    wave, wave_run, clk = rr.artifact("wave"), rr, rclk
                    if not rcov:
                        S["notes"].append(f"the re-run's wave does not cover the failure either: {rwhy}")
                rvfi = rr.artifact("rvfi_trace") or rvfi
                konata = rr.artifact("konata") or konata
                fail_cycle = rr.get("cycles", fail_cycle)
                break
            else:
                S["notes"].append(f"re-run `{name}` ended with {rsig}, not {sig}"
                                  + (" (the RVFI model's monitor or a non-deterministic run)" if with_rvfi else ""))
            if not with_rvfi or not need_rvfi and not need_wave:
                break
    elif need_wave:
        S["notes"].append(f"no wave covering the failure ({why}; re-run disabled)")
    S["period"] = clk.period
    S["clock"] = clk.to_dict()
    if not clk.known:
        S["notes"].append("the wave time of cycle 1 is unknown (no details.wave_time_of_cycle_1): cycle labels "
                          f"assume cycle N at N x {clk.period}")

    # 2. Retired instructions and last progress
    if dis.error:
        S["notes"].append(dis.error)
    prog: dict = {}
    rvfi_tail = None
    if rvfi:
        tail = rvfi_tail = trace.read_rvfi_tail(str(rvfi), o.retired)
        lines = []
        for r in tail.retired:
            pc = trace.hexint(r["pc"])
            ins = trace.hexint(r.get("insn"))
            wd = f" {_rd(r)}" if r.get("rd") else ""
            mem = _mem(r)
            flag = " TRAP" if r.get("trap") else ""
            lines.append(f"{r.get('order', ''):>9} {r.get('cycle', ''):>9}  {pc:#012x}  {ins or 0:08x}  "
                         f"{dis.func(pc)}: {dis.text(pc)}{wd}{mem}{flag}")
        for e in tail.traps[-8:]:
            lines.append(f"# trap at cycle {e.get('cycle')}: cause={e.get('cause')} tval={e.get('tval')}"
                         f" intr={e.get('intr')}")
        hdr = "#   order     cycle  pc            insn      function: disassembly  [rd=value] [mem]\n"
        (out / "retired.txt").write_text(hdr + "\n".join(lines) + "\n")
        S["files"]["retired"] = "retired.txt"
        if tail.retired:
            last = tail.retired[-1]
            lpc = trace.hexint(last["pc"])
            npc = trace.hexint(last.get("pc_next"))
            nl = dis.at(npc) if npc is not None else None
            ninsn = int(nl.raw, 16) if nl else None
            prog = {"last_order": last.get("order"), "last_cycle": last.get("cycle"),
                    "last_pc": hex(lpc), "last_func": dis.func(lpc), "last_text": dis.text(lpc),
                    "next_pc": hex(npc) if npc is not None else None,
                    "next_text": dis.text(npc) if npc is not None else None,
                    "next_func": dis.func(npc) if npc is not None else None,
                    "next_class": classify(ninsn) if nl else "unknown",
                    "instret": tail.total}
            if fail_cycle is not None and last.get("cycle") is not None:
                prog["cycles_since_last_retire"] = fail_cycle - int(last["cycle"])
            li = trace.loop_info(tail.retired)
            if li:
                prog["loop"] = li
            prog["recent_traps"] = tail.traps[-4:]
    else:
        S["notes"].append("no RVFI trace: retired instructions unavailable")
    S["progress"] = prog

    # 3. Wave window, pipeline snapshot, handshakes
    period = clk.period
    if wave:
        wend = vcd.end_time(str(wave))
        covered, why = (wclock.covers(wave_run, wave, fail_cycle, clk) if fail_cycle is not None
                        else (False, "no failure cycle"))
        # Adapters end the simulation at the failure (any status), so the snapshot is at the failing
        # cycle: the end of the wave, or the failure cycle's last time if the wave runs on.
        t_snap = wend
        if covered and wend is not None:
            t_snap = min(wend, clk.time(fail_cycle) + period - 1)
        elif wend is not None:
            S["notes"].append(f"the wave does not cover the failure ({why}); the snapshot is at the end "
                              "of the wave")
        lo = max(0, (t_snap or 0) - o.cut_cycles * period)
        _say(o, f"cutting {wave.name} to {lo}..{t_snap}")
        cut = wops.cut(str(wave), str(out / "wave-window.vcd"), lo, t_snap)
        S["files"]["wave_window"] = "wave-window.vcd"
        S["wave"] = {"source": str(wave), "from": lo, "to": t_snap, "snapshot_time": t_snap,
                     "covers_failure": covered,
                     "snapshot_cycle": clk.cycle(t_snap) if t_snap is not None else None,
                     # A cut that starts before cycle 1 starts in reset: no negative cycle numbers
                     "from_cycle": max(1, clk.cycle(lo)), "from_reset": lo < clk.time(1),
                     "signals": cut["signals"], "bytes": cut["bytes"]}
        if cfg.get("snapshot"):
            S["snapshot"] = snapshot.take(cfg["snapshot"], str(out / "wave-window.vcd"), t_snap)
        if cfg.get("handshakes"):
            S["handshakes"] = handshakes.analyze(cfg["handshakes"], str(out / "wave-window.vcd"), t_snap, period)
        if core.get("commit") and rvfi_tail is not None and clk.known:
            sk = wclock.rvfi_skew(str(out / "wave-window.vcd"), core["commit"], clk, rvfi_tail.retired)
            S["rvfi_skew"] = sk if sk else {"measured": False, "commit_signals": core["commit"]}
    else:
        S["notes"].append("no wave: no pipeline snapshot")

    # 4. Konata: instructions in flight at the failure
    if konata:
        try:
            inflight, kend = trace.konata_inflight(str(konata))
            S["inflight"] = [{"id": u.id, "label": u.label, "detail": u.detail, "stage": u.stage,
                              "stage_since": u.since, "age": kend - u.born} for u in inflight[:48]]
            S["inflight_total"] = len(inflight)
        except (OSError, ValueError) as e:
            S["notes"].append(f"Konata log not read: {e}")

    # 5. SpinalTrace dependency trace
    if o.spinaltrace:
        S["dynpdg"] = _spinaltrace(run, cfg, S, out, wave, o, replay_cmd, inputs)

    # 6. Suspected unit, summary, replay
    S["suspect"] = suspect(cfg, S)
    S["replay"] = None
    if replay_cmd is not None:
        S["replay"] = replay_cmd.set(out="OUT_DIR").shell()
        _write_replay(out / "replay.sh", replay_cmd, run)
        S["files"]["replay"] = "replay.sh"
    else:
        S["notes"].append("replay unavailable: reruns and SpinalTrace are disabled; "
                          "the adapter and source were not captured")
    S["next"] = next_commands(S, out, cfg)
    S["files"]["summary"] = "summary.md"
    S["capture"] = inputs.record()
    S["cache_key"] = None
    (out / "summary.json").write_text(json.dumps(S, indent=1, default=str) + "\n")
    (out / "summary.md").write_text(render_md(S, out))
    _say(o, f"wrote {out}/summary.md")
    S["out"] = str(out)
    return S


def _rd(r: dict) -> str:
    return f"x{r.get('rd')}={r.get('rd_wdata')}"


def _mem(r: dict) -> str:
    rm, wm = r.get("mem_rmask") or 0, r.get("mem_wmask") or 0
    if wm:
        return f" [st {r.get('mem_addr')}={r.get('mem_wdata')}]"
    if rm:
        return f" [ld {r.get('mem_addr')}]"
    return ""


def suspect(cfg: dict, S: dict) -> dict:
    fail = cfg.get("failure", {})
    status = S["status"]
    ev = []
    unit = None
    from ..runs.signature import assertion_location
    loc = assertion_location(S.get("message"))
    if status == "assert" and loc:
        for rx, u in (fail.get("units") or {}).items():
            if re.search(rx, loc[0]):
                unit = u
                break
        ev.append(f"assertion at {loc[0]}:{loc[1]}")
    p = S.get("progress") or {}
    if status == "timeout":
        cls = p.get("next_class")
        since = p.get("cycles_since_last_retire")
        if p.get("loop") and (since or 0) < 1000:
            unit = unit or "software (the program is looping, still retiring)"
            ev.append(f"still retiring, looping over {p['loop']['distinct_pcs']} pcs "
                      f"{p['loop']['pc_lo']}..{p['loop']['pc_hi']}")
        elif cls:
            unit = unit or (fail.get("insn_units") or {}).get(cls)
            ev.append(f"no retirement for {since} cycles; oldest unretired instruction {p.get('next_pc')} "
                      f"`{p.get('next_text')}` is a {cls}")
    if status == "fail":
        unit = unit or "functional bug visible to software (wrong result checked by the program)"
        ev.append(f"program reported failure code {S.get('fail_code')}; see the last retired instructions")
    if status == "rvfi_error":
        unit = unit or "retirement/architectural state (RVFI monitor)"
    h = S.get("handshakes") or {}
    for n, d in (h.get("channels") or {}).items():
        if d.get("stalled_cycles", 0) > 100:
            ev.append(f"channel {n} has had valid without ready for {d['stalled_cycles']} cycles")
    if h.get("open_requests"):
        old = [r for r in h["open_requests"] if (r.get("age_cycles") or 0) > 500]
        if old:
            ev.append(f"{len(old)} memory request(s) unanswered for >500 cycles")
    return {"unit": unit or "unknown", "evidence": ev}


def _spinaltrace(run, cfg: dict, S: dict, out: Path, wave: Path | None, o: Options,
                 replay_cmd: adapter.Command, inputs: DebugInputs) -> dict:
    st = cfg.get("spinaltrace") or {}
    trace_run = None
    pdg = Path(o.pdg) if o.pdg else (run.artifact("pdg") or _details_pdg(run))
    if o.trace_wave:
        wave = Path(o.trace_wave)
    elif pdg is None and st.get("adapter") and o.rerun and S.get("cycles") is not None:
        # Re-run through the core's SpinalTrace-instrumented adapter with a short wave window
        f = int(S["cycles"])
        cmd = replay_cmd.set(wave=True, wave_from=max(1, f - o.trace_cycles - 5),
                                           wave_to=f + 5, rvfi_trace=None, konata=None)
        cmd.exe = st["captured_command"].exe
        cmd.env = st["captured_command"].env.copy()
        tdir = out / "rerun-spinaltrace"
        say("bundle", f"re-running with the SpinalTrace model: {cmd.set(out=str(tdir)).shell()}")
        at = adapter.execute(cmd, tdir, core=run.get("core"), timeout=o.timeout)
        tr = at.run
        R = S["rerun_spinaltrace"] = {"dir": str(at.dir), "wall_s": round(at.wall, 1),
                                      "signature": runs.signature(tr.data) if tr else None,
                                      "cycles": tr.get("cycles") if tr else None,
                                      "capture": tr.capture.record() if tr and tr.capture else None}
        # Its wave window ends 5 cycles after `f`: only a conclusive re-run with the same signature at
        # the same cycle shows this failure.
        tinc = tr.inconclusive if tr is not None else None
        R["reproduced"] = tr is not None and tinc is None and R["signature"] == S["signature"] and R["cycles"] == f
        if R["reproduced"]:
            pdg = _details_pdg(tr)
            wave = tr.artifact("wave")
            trace_run = tr
        elif tr is None:
            R["error"] = f"{at.error}; see {at.log}"
            S["notes"].append(f"the SpinalTrace re-run failed: {R['error']}")
        elif tinc:
            R["inconclusive"] = tinc
            S["notes"].append(f"the SpinalTrace re-run is inconclusive ({tinc}); its wave and PDG are not used")
        else:
            S["notes"].append(f"the SpinalTrace re-run did not reproduce the failure: {R['signature']} at cycle "
                              f"{R['cycles']}, not {S['signature']} at cycle {f}")
    if pdg is not None:
        pdg = inputs.file(pdg)
    if wave is not None:
        wave = inputs.file(wave)
    if pdg is None and st.get("pdg"):
        p = Path(os.path.expandvars(st["pdg"]))
        pdg = p if p.exists() else None
    cli = st.get("captured_cli")
    from ..runs.signature import assertion_location
    loc = assertion_location(S.get("message"))
    crit = f"line:{loc[0]}:{loc[1]}" if loc else (st.get("criteria") or {}).get(S["status"])
    res = {"criterion": crit}
    if pdg is None:
        res["skipped"] = ("no SpinalTrace PDG for this build (run artifact 'pdg' or [spinaltrace].pdg); "
                          "build the core with SpinalTrace instrumentation to get one")
        return res
    if not cli:
        res["skipped"] = "spinaltrace-cli not found (SPINALTRACE_CLI or PATH)"
        return res
    if not crit or not wave:
        res["skipped"] = (f"no criterion for status {S['status']} (assertion location or "
                          f"[spinaltrace.criteria].{S['status']}) or no wave")
        return res
    if crit.startswith("line:") and loc:
        lines = pdg_lines(pdg, loc[0])
        if loc[1] not in lines:
            near = [l for l in lines if loc[1] - 8 <= l < loc[1]]
            if near:
                crit = f"line:{loc[0]}:{max(near)}"
                res["criterion"] = crit
                res["criterion_note"] = (f"{loc[0]}:{loc[1]} has no statement in the PDG (assertion helpers "
                                         f"are located at their own definition); traced the enclosing "
                                         f"condition at line {max(near)} instead")
    # dyn-pdg unrolls every cycle of the wave it gets: give it a short window ending at the failure
    end = vcd.end_time(str(wave))
    tclk = wclock.wave_clock(trace_run or run, cfg.get("core") or {}, wave)
    t = end if S["status"] == "assert" or not S.get("cycles") else min(end, tclk.time(S["cycles"]) + tclk.period - 1)
    period = tclk.period
    tw = out / "trace-window.vcd"
    wops.cut(str(wave), str(tw), max(0, t - o.trace_cycles * period), t)
    res["wave"] = str(wave)
    argv = [cli, "dyn-pdg", "-s", crit, "-p", str(pdg), "-v", str(tw),
            "--at-time", str(max(0, t - 1)), "-o", str(out / "dynpdg.json"), "--summary"]
    if st.get("top_module"):
        argv += ["--top-module", st["top_module"]]
    if st.get("extra_scopes"):
        argv += ["--extra-scopes", *st["extra_scopes"]]
    res["command"] = shlex.join(argv)
    (out / "dynpdg.json").unlink(missing_ok=True)
    p = run_group(argv, capture=True, timeout=1800, env=inputs.environment)
    (out / "dynpdg.txt").write_text((p.stdout or "") + (p.stderr or ""))
    if p.timed_out:
        res["error"] = "spinaltrace-cli timed out (process group stopped)"
        return res
    res["exit"] = p.returncode
    res["summary"] = "\n".join((p.stdout or "").splitlines()[:40])
    if p.returncode == 0 and (out / "dynpdg.json").exists():
        S["files"]["dynpdg"] = "dynpdg.json"
        from .pdgdigest import digest
        res["digest"] = digest(str(out / "dynpdg.json"), 40, crit)
    return res


def pdg_lines(pdg: Path, file: str) -> set[int]:
    """Source lines of `file` that have statements in a SpinalTrace pdg.json (regex scan, no JSON load)."""
    rx = re.compile(rb'"file":\s*"(?:[^"]*/)?' + re.escape(file.encode()) + rb'",\s*"line":\s*(\d+)')
    with open(pdg, "rb") as f:
        return {int(m.group(1)) for m in rx.finditer(f.read())}


def _details_pdg(run) -> Path | None:
    if run.capture is not None:
        return run.captured_artifacts.get('details_pdg')
    p = (run.get("details") or {}).get("pdg")
    return Path(p) if p and Path(p).exists() else None


def _write_replay(path: Path, cmd: adapter.Command, run) -> None:
    root = runs.tools_root()
    lock = adapter.lock_prefix(run.get("core"))
    # Quote every argument, then put "$out" in place of the --out value only (an ELF path or any
    # other argument may contain "OUT").
    prefix = (['env', *[arg for name in cmd.unset for arg in ('-u', name)],
               *[f'{k}={v}' for k, v in cmd.env.items()]] if cmd.unset or cmd.env else [])
    argv = prefix + lock + cmd.set(out=None).argv() + ["--out"]
    line = " ".join(shlex.quote(a) for a in argv) + ' "$out"'
    body = ["#!/usr/bin/env bash",
            f"# Reproduce {run.get('status')} ({runs.signature(run.data)}) of {run.dir}",
            "# Add --wave --wave-from N --wave-to M, --rvfi-trace or --konata for more detail.",
            "set -euo pipefail",
            f"cd {shlex.quote(str(root))}",
            'out="${1:-$(mktemp -d)}"',
            line,
            'echo "result: $out/result.json"']
    path.write_text("\n".join(body) + "\n")
    path.chmod(0o755)


def next_commands(S: dict, out: Path, cfg: dict) -> list[str]:
    cmds = []
    if S.get("files", {}).get("wave_window"):
        w = out / "wave-window.vcd"
        cmds.append(f"rvw wave changes {w} 'REGEX' --from {S['wave']['from']}  # signals around the failure")
        cmds.append(f"surfer {w}")
        unit = S.get("suspect", {}).get("unit", "")
        for g in cfg.get("snapshot", []):
            if g.get("unit") and g["unit"].split()[0].lower() in unit.lower() and g.get("scope"):
                cmds.append(f"rvw wave list {w} '{g['scope']}'  # all {g['name']} signals")
                break
    d = S.get("dynpdg") or {}
    if d.get("command"):
        cmds.append(f"spinaltrace -s {d['criterion']} ...  # GUI on the same inputs as dynpdg.json")
    cmds.append(f"rvw reduce {S['run']}  # shortest reproduction (seed/latency/cycles)")
    if S.get('replay'):
        cmds.append(f"{out / 'replay.sh'} /tmp/replay  # exact reproduction")
    if not S.get("inflight"):
        cmds.append("re-run with --konata (rvw bundle RUN --konata) to see the instructions in flight")
    return cmds


def render_md(S: dict, out: Path) -> str:
    L = []
    L.append(f"# Failure bundle: {S['signature']}")
    L.append("")
    L.append(f"- **Status**: `{S['status']}`" + (f", code {S['fail_code']}" if S.get("fail_code") is not None else ""))
    if S.get("message"):
        L.append(f"- **Message**: `{str(S['message']).strip()[:400]}`")
    lat = "randomized" if S.get("mem_latency") is None else f"fixed {S['mem_latency']}"
    L.append(f"- **Run**: core `{S.get('core')}` config `{S.get('config')}`, ELF `{S.get('elf')}`, "
             f"seed {S.get('seed')}, memory timing {lat}, max cycles {S.get('max_cycles')}")
    L.append(f"- **Failed at cycle** {S.get('cycles')} after {S.get('instret')} retired instructions")
    src = S.get("source") or {}
    if src:
        parts = [f"{name} {src.get(name + '_repo')}, captured tree {src[name + '_tree_sha256']}"
                 for name in ('core', 'tools') if src.get(name + '_tree_sha256')]
        L.append('- **Source**: ' + '; '.join(parts))
    su = S.get("suspect") or {}
    L.append(f"- **Suspected unit**: {su.get('unit')}")
    for e in su.get("evidence", []):
        L.append(f"  - {e}")
    for key, what in (("rerun", "wave + RVFI trace"), ("rerun-wave", "wave only"),
                      ("rerun_spinaltrace", "SpinalTrace model")):
        rr = S.get(key)
        if rr:
            L.append(f"- **Re-run ({what})**: {rr.get('signature') or rr.get('error')} at cycle {rr.get('cycles')}, "
                     f"{rr.get('wall_s')} s" + (" (reproduced)" if rr.get("reproduced") else
                                                f" (NOT reproduced: inconclusive, {rr['inconclusive']})"
                                                if rr.get("inconclusive") else
                                                " (NOT reproduced)" if "reproduced" in rr else "")
                     + f", `{rr.get('dir')}`")
    for n in S.get("notes", []):
        L.append(f"- Note: {n}")
    L.append("")
    p = S.get("progress") or {}
    if p:
        L.append("## Last progress")
        L.append("")
        L.append(f"- Last retired: #{p.get('last_order')} at cycle {p.get('last_cycle')}: "
                 f"`{p.get('last_pc')}` in `{p.get('last_func')}`: `{p.get('last_text')}`")
        if "cycles_since_last_retire" in p:
            L.append(f"- Cycles from last retirement to the end: **{p['cycles_since_last_retire']}**")
        if p.get("next_pc"):
            L.append(f"- Next (oldest unretired) pc: `{p['next_pc']}` in `{p.get('next_func')}`: "
                     f"`{p.get('next_text')}` ({p.get('next_class')})")
        if p.get("loop"):
            lp = p["loop"]
            L.append(f"- The last {lp['of']}+ retirements cycle over {lp['distinct_pcs']} pcs "
                     f"({lp['pc_lo']}..{lp['pc_hi']})")
        for t in p.get("recent_traps") or []:
            L.append(f"- Trap at cycle {t.get('cycle')}: cause {t.get('cause')} tval {t.get('tval')}")
        L.append("")
        sk = S.get("rvfi_skew") or {}
        if sk.get("rvfi_minus_wave_commit") is not None:
            d = sk["rvfi_minus_wave_commit"]
            L.append(f"- RVFI cycle stamps are **{d} cycle(s) after** the wave's commit signals (measured: "
                     f"{sk['cycles_compared']} cycles, agreement {sk['agreement']}; last retirement stamped "
                     f"{sk['last_rvfi_cycle']} commits in the wave at cycle {sk['last_wave_commit_cycle']}). "
                     "Subtract it before looking up a retirement in the wave.")
        elif sk:
            L.append("- RVFI stamp skew against the wave's commit signals: not measured (no clear match)")
        L.append("")
        L.append("Last retired instructions (`retired.txt`, RVFI cycle stamps):")
        L.append("")
        L.append("```")
        rt = (out / "retired.txt").read_text().splitlines() if (out / "retired.txt").exists() else []
        L.extend(rt[-16:])
        L.append("```")
        L.append("")
    if S.get("snapshot") or S.get("handshakes"):
        w = S.get("wave") or {}
        ck = S.get("clock") or {}
        L.append(f"## Pipeline state at cycle {w.get('snapshot_cycle')} (wave time {w.get('snapshot_time')}; "
                 f"cycle N at time {ck.get('time_of_cycle_1')} + (N - 1) x {ck.get('period')}"
                 + ("" if ck.get("known") else ", assumed") + ")")
        L.append("")
        if not w.get("covers_failure"):
            L.append("**The wave does not reach the failure; this is the state at the end of the wave.**")
            L.append("")
        if S.get("snapshot"):
            L.append(snapshot.render_md(S["snapshot"]))
        if S.get("handshakes"):
            L.append("")
            L.append(f"Channel activity over the window ({w.get('from')}..{w.get('to')}):")
            L.append("")
            L.append(handshakes.render_md(S["handshakes"]))
        L.append("")
    if S.get("inflight"):
        L.append(f"## In flight at the end (Konata, {S.get('inflight_total')} instructions, oldest first)")
        L.append("")
        L.append("```")
        for u in S["inflight"][:24]:
            L.append(f"{u['stage']:>3} since {u['stage_since']:>8} (age {u['age']:>5})  {u['label']}"
                     + (f"  [{u['detail'].splitlines()[0]}]" if u.get("detail") else ""))
        L.append("```")
        L.append("")
    d = S.get("dynpdg")
    if d:
        L.append("## Dependency trace (SpinalTrace)")
        L.append("")
        if d.get("skipped"):
            L.append(f"Skipped: {d['skipped']}. Criterion would be `{d.get('criterion')}`.")
        else:
            if d.get("criterion_note"):
                L.append(f"Note: {d['criterion_note']}.")
                L.append("")
            L.append(f"Criterion `{d.get('criterion')}` traced over the last cycles of `{d.get('wave')}`. "
                     "Statements closest to the traced value first (depth = dependency edges from it, "
                     "cycle relative to the failure); full graph in `dynpdg.json` (open with `spinaltrace`), "
                     "raw summary in `dynpdg.txt`.")
            L.append("")
            if d.get("digest"):
                from .pdgdigest import render_md as dmd
                L.append(dmd(d["digest"]))
            else:
                L.append("```")
                L.append(d.get("summary") or d.get("error") or "")
                L.append("```")
            L.append("")
            L.append(f"Command: `{d.get('command')}` (exit {d.get('exit')})")
        L.append("")
    L.append("## Files")
    L.append("")
    for k, v in S.get("files", {}).items():
        L.append(f"- `{v}` ({k})")
    L.append("")
    L.append("## Next commands")
    L.append("")
    L.append("```sh")
    L.extend(S.get("next", []))
    L.append("```")
    L.append("")
    L.append(f"Replay: `{S['replay']}`" if S.get('replay') else "Replay unavailable. See the notes.")
    L.append("")
    return "\n".join(L)
