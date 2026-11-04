"""Shrink a failing run while keeping its failure signature.

Modes (run in this order, each starting from the best reproduction so far):

  cycles    Re-run with max cycles = failure cycle + margin. Confirms the failure is
            deterministic for the seed and gives the tightest max-cycles. For timeouts, the hang
            start is the last retirement (needs an RVFI trace) and max cycles becomes
            last retirement + --hang-cycles.
  seeds     Try other seeds with the same memory-timing setting; keep the one that fails
            earliest. Each trial is capped at the best failure cycle + margin, so slower seeds
            stop early.
  latency   Try fixed memory latencies (--latencies) and randomized timing with the best seed;
            reports which settings reproduce, keeps the earliest.
  symbols   Program reduction: for each --symbol NAME (an integer in initialized data, e.g. an
            iteration count), binary-search a smaller value that still fails. Writes patched
            ELF copies. The search finds a value v that fails while v-1 passes; it is the minimum
            only if the failure is monotone in the value. So `exact` is true only with
            --monotone (the caller vouches for it) or --exhaustive (every untested value below
            v is tried in ascending order). A trial that proves nothing (no result, or
            inconclusive by the shared rule `rvw.results.inconclusive_cause`: harness `error`,
            synthesized result, wall-clock timeout, C1 `inconclusive`) stops the search for that
            symbol; it never counts as failing or passing.

Every trial is recorded in reduce.json; the best reproduction's run directory and replay command
are reported, and `reproduced` says whether any trial matched.

An inconclusive result (`rvw.results.inconclusive_cause`: a wall-clock timeout `timeout:wall-clock`,
a harness `error`, a synthesized result, C1 `inconclusive`) proves nothing: an original run with
one is refused, and a trial with one never matches, even through a `re:` signature.

A trial that ends in `timeout` matches only if it is a hang: its RVFI trace shows no retirement in
the last --hang-cycles cycles before the end. Every trial asks for an RVFI trace when the target
signature can be `timeout`, and a trial without one never counts. So a re-run that only hit the
lowered max-cycles cap is never a reproduction.
"""
from __future__ import annotations

import json
import copy
import hashlib
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path

from .. import runs
from ..common.jsonout import say
from ..common.capture import CaptureError
from ..runs import adapter
from ..runs.elf import Elf
from ..runs.inputs import DebugInputs
from ..runs.hang import validate_hang_cycles, hang_check, read_evidence


@dataclass
class Options:
    out: Path | None = None
    signature: str | None = None
    modes: list[str] = field(default_factory=lambda: ["cycles", "seeds", "latency"])
    seeds: int = 12
    seed_start: int = 1
    latencies: list[int] = field(default_factory=lambda: [1, 2, 5, 10, 20, 50])
    symbols: list[str] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    margin: int = 100
    hang_cycles: int = 5000
    project: str | None = None
    jobs: int = 1
    batch: int = 4
    budget: int = 64            # max trials
    timeout: float | None = None
    monotone: bool = False      # symbols: the failure is known to be monotone in the value
    exhaustive: bool = False    # symbols: prove the minimum by trying every untested value below


class Reducer:
    def __init__(self, run_dir: str, o: Options):
        o = copy.deepcopy(o)
        validate_hang_cycles(o.hang_cycles)
        self.o = o
        path = Path(run_dir).resolve()
        directory = path if path.is_dir() else path.parent
        self.out = Path(o.out or (directory / 'reduce')).resolve()
        self.inputs = DebugInputs()
        self.run = runs.open_run(run_dir, capture=self.inputs.capture)
        self.core = self.run.get("core")
        orig = runs.signature(self.run.data)
        self.sig = o.signature or orig
        if orig == "pass":
            raise ValueError(f"{self.run.dir}: the run passed; nothing to reduce")
        if self.run.inconclusive:
            raise ValueError(f"{self.run.dir}: the run is inconclusive ({self.run.inconclusive}); re-run the "
                             "test alone and reduce that run")
        if not runs.signature_matches(orig, self.sig):
            raise ValueError(f"{self.run.dir}: the run's signature {orig} does not match --signature {self.sig}")
        self.notes: list[str] = []
        if orig == "timeout":
            hung, why = hang_check(self.run, o.hang_cycles)
            if hung is False:
                raise ValueError(f"{self.run.dir}: the timeout is not a hang ({why}; --hang-cycles "
                                 f"{o.hang_cycles}): the program was still retiring when max cycles ran out")
            self.notes.append(f"original timeout: {why}" if hung else
                              f"original timeout: {why}; only trials with a usable trace can show a hang")
        # Trials need an RVFI trace whenever `timeout` could count as the target signature
        self.want_trace = runs.signature_matches("timeout", self.sig)
        self.out.mkdir(parents=True, exist_ok=True)
        self.report_dir = adapter.fresh_dir(self.out / "reports")
        self.trials: list[dict] = []
        self.symbol_results: dict[str, dict] = {}
        self.stream_results: dict[str, dict] = {}
        cfg, _ = self.inputs.config(self.core, project=o.project)
        self.base = self.inputs.command(self.run, cfg)
        elf = Path(self.base.get('elf'))
        if self.want_trace:
            self.base = self.base.set(rvfi_trace=True)
        self.best = {"cycles": self.run.get("cycles"), "cmd": self.base, "dir": str(self.run.dir),
                     "seed": self.run.get("seed"), "mem_latency": self.run.get("mem_latency"),
                     "elf": str(elf), "max_cycles": self.run.get("max_cycles"), "trial": None}
        self.t0 = time.monotonic()

    def say(self, m: str) -> None:
        say("reduce", m)

    def cap(self) -> int:
        c = self.best["cycles"] or self.run.get("max_cycles") or 200000
        return int(c) + self.o.margin

    def matches(self, r) -> tuple[bool | None, str | None]:
        """(does trial run `r` reproduce the target, why not / hang evidence). None: a timeout whose
        RVFI trace cannot tell a hang from the cap; the trial is inconclusive, not a non-match."""
        if r is None:
            return False, None
        if r.inconclusive:           # harness error, synthesized, wall clock, C1 mark (rvw.results rule)
            return None, f"inconclusive: {r.inconclusive}"
        s = runs.signature(r.data)
        if not runs.signature_matches(s, self.sig):
            return False, None
        if s == "timeout":
            hung, why = hang_check(r, self.o.hang_cycles)
            return hung, why
        return True, None

    def trial(self, batch: list[tuple[str, adapter.Command, dict]]) -> list[dict]:
        """Run (label, command, meta) trials; record and return them."""
        batch = batch[: max(0, self.o.budget - len(self.trials))]
        if not batch:
            return []
        outs = [self.out / f"t{len(self.trials) + i:03d}-{lbl}" for i, (lbl, _, _) in enumerate(batch)]
        ats = adapter.execute_many([c for _, c, _ in batch], outs, core=self.core, jobs=self.o.jobs,
                                   timeout=self.o.timeout)
        recs = []
        for (lbl, c, meta), at in zip(batch, ats):
            r, o = at.run, at.dir
            match, why = self.matches(r)
            sig = runs.signature(r.data) if r else None
            rec = {"id": len(self.trials), "label": lbl, "dir": str(o), **meta,
                   "max_cycles": c.get("max_cycles"),
                   "status": r.get("status") if r else ("wall-timeout" if at.timed_out else "no-result"),
                   "signature": runs.signature(r.data) if r else None,
                   "cycles": r.get("cycles") if r else None,
                   "wall_s": r.get("wall_s") if r else None,
                   "lock_wait_s": round(at.lock_wait, 1),
                   "match": bool(match),
                   "capture": r.capture.record() if r is not None and r.capture is not None else None,
                   # False when the trial says nothing either way: no result, the shared rule
                   # (harness error, synthesized, wall clock, C1 `inconclusive`), or a timeout
                   # without hang evidence
                   "conclusive": (r is not None and not r.inconclusive
                                  and match is not None)}
            if r is not None and r.inconclusive:
                rec["inconclusive"] = r.inconclusive
            elif why:
                rec["hang"] = why
            if r is None and at.error:
                rec["error"] = at.error
            rec["_cmd"] = c
            self.trials.append(rec)
            recs.append(rec)
            self.say(f"{lbl}: {rec['signature'] or rec['status']} at {rec['cycles']}"
                     + (" MATCH" if rec["match"] else "") + (f" ({why})" if why else "")
                     + (f" [waited {at.lock_wait:.0f}s for the {self.core} lock]" if at.lock_wait >= 1 else ""))
            if rec["match"] and (self.best["cycles"] is None or rec["cycles"] < self.best["cycles"]
                                 or self.best["trial"] is None or lbl == "confirm"):
                self._take(rec)
        self.save()
        return recs

    # --- modes -------------------------------------------------------------------------------

    def mode_cycles(self):
        if runs.signature(self.run.data) == "timeout":
            path = self.run.artifact("rvfi_trace")
            evidence = read_evidence(str(path)) if path else None
            if evidence is None or not evidence.ok:
                self.say("cycles: timeout without an RVFI trace; skipping (re-run with --rvfi-trace)")
                return
            last = evidence.last_retire or 0
            mc = last + self.o.hang_cycles
            self.say(f"cycles: last retirement at {last}; trying max cycles {mc}")
        else:
            mc = self.cap()
        c = self.best["cmd"].set(max_cycles=mc)
        self.trial([("cycles", c, {"seed": self.best["seed"], "mem_latency": self.best["mem_latency"]})])

    def mode_seeds(self):
        seeds = [s for s in range(self.o.seed_start, self.o.seed_start + self.o.seeds + 1)
                 if s != self.run.get("seed")][: self.o.seeds]
        for i in range(0, len(seeds), self.o.batch):
            group = seeds[i:i + self.o.batch]
            cap = self.cap()
            self.trial([(f"seed{s}", self.best["cmd"].set(seed=s, max_cycles=cap),
                         {"seed": s, "mem_latency": self.best["mem_latency"]}) for s in group])

    def mode_latency(self):
        settings: list[int | None] = list(self.o.latencies)
        if self.best["mem_latency"] is not None:
            settings.append(None)
        cap = self.cap()
        batch = []
        for lat in settings:
            if lat == self.best["mem_latency"]:
                continue
            batch.append((f"lat{'rand' if lat is None else lat}",
                          self.best["cmd"].set(mem_latency=lat, max_cycles=cap),
                          {"seed": self.best["seed"], "mem_latency": lat}))
        for i in range(0, len(batch), self.o.batch):
            self.trial(batch[i:i + self.o.batch])

    def mode_symbols(self):
        for spec in self.o.symbols:
            name, _, size = spec.partition(":")
            src = self.best["elf"]
            try:
                e = Elf(src)
                sym = e.symbols()[name]
                n = int(size) if size else (sym.size if sym.size in (1, 2, 4, 8) else None)
                if n is None:
                    self.say(f"symbol {name}: {sym.size} bytes (an array or struct?); give NAME:BYTES "
                             f"with the element size to shrink its first element")
                    continue
                v0 = e.read_int(name, n)
            except KeyError:
                self.say(f"symbol {name}: not in the ELF symbol table")
                continue
            except (ValueError, OSError) as ex:
                self.say(f"symbol {name}: {ex}")
                continue
            # Establish that hi fails in this invocation before using it as a bound.
            lo, hi = -1, v0
            best_rec = None
            passed: set[int] = set()      # values whose trial ran and did not reproduce
            stopped = None                # why the search stopped early

            def probe(v: int):
                p = self.out / f"{Path(src).name}.{name}={v}"
                e2 = Elf(src)
                e2.write_int(name, v, n)
                e2.save(str(p))
                item = self.inputs.capture.file(p)
                if item.sha256 != hashlib.sha256(e2.data).hexdigest():
                    raise CaptureError('input_not_captured:patched_elf', 'symbol ELF changed before capture')
                p = item.copy
                c = self.best["cmd"].set(elf=str(p), max_cycles=self.cap())
                rec = self.trial([(f"{name}={v}", c, {"seed": self.best["seed"], "elf": str(p),
                                                      "mem_latency": self.best["mem_latency"], "symbols": {name: v}})])
                return rec[0] if rec else None

            self.say(f"symbol {name} = {v0} ({n} bytes): binary search for a smaller failing value")
            upper = probe(v0)
            if upper is None or not upper['match']:
                if upper is None:
                    why = 'the trial budget ran out'
                elif not upper['conclusive']:
                    why = f"{name}={v0} was inconclusive ({upper['signature'] or upper['status']})"
                else:
                    why = f'{name}={v0} did not reproduce the signature'
                self.say(f'symbol {name}: no minimum; {why}')
                self.symbol_results[name] = {
                    'original': v0, 'smallest_failing': None, 'bytes': n,
                    'exact': False, 'exact_by': None, 'elf': src, 'note': why}
                continue
            best_rec = upper
            while hi - lo > 1:
                if len(self.trials) >= self.o.budget:
                    stopped = "the trial budget ran out"
                    break
                mid = (lo + hi) // 2
                rec = probe(mid)
                if rec is None:
                    stopped = "the trial budget ran out"
                    break
                if rec["match"]:
                    hi, best_rec = mid, rec
                elif not rec["conclusive"]:
                    stopped = f"{name}={mid} was inconclusive ({rec['signature'] or rec['status']})"
                    break
                else:
                    lo = mid
                    passed.add(mid)
            exact_by = None
            if stopped is None and self.o.monotone:
                exact_by = "monotone"
            elif stopped is None and self.o.exhaustive:
                # Ascending: the first value that reproduces is the minimum.
                for v in range(0, hi):
                    if v in passed:
                        continue
                    if len(self.trials) >= self.o.budget:
                        stopped = "the trial budget ran out during the exhaustive check"
                        break
                    rec = probe(v)
                    if rec is None:
                        stopped = "the trial budget ran out during the exhaustive check"
                        break
                    if rec["match"]:
                        hi, best_rec = v, rec
                        break
                    if not rec["conclusive"]:
                        stopped = f"{name}={v} was inconclusive ({rec['signature'] or rec['status']})"
                        break
                    passed.add(v)
                if stopped is None:
                    exact_by = "exhaustive"
            if best_rec is not None:
                # The reported value and the returned ELF are the same trial
                self._take(best_rec)
            untested = hi - len([v for v in passed if v < hi])
            why = (stopped if stopped else "" if exact_by else
                   "not proven minimal: the binary search assumes the failure is monotone in the value; "
                   f"{untested} smaller value(s) untested (use --exhaustive, or --monotone if it is)")
            self.say(f"symbol {name}: smallest tested failing value {hi} (was {v0}"
                     + (f"; exact ({exact_by})" if exact_by else f"; {why}") + ")")
            res = {"original": v0, "smallest_failing": hi, "bytes": n,
                   "exact": exact_by is not None, "exact_by": exact_by,
                   "elf": best_rec["elf"] if best_rec else src}
            if why:
                res["note"] = why
            self.symbol_results[name] = res

    def _stream_search(self, name, items, command):
        from .streams import minimize
        best_rec = None
        exhausted = False
        def probe(kept):
            nonlocal best_rec, exhausted
            if len(self.trials) >= self.o.budget:
                exhausted = True
                return None
            c, meta = command(kept)
            recs = self.trial([(f"stream{len(self.trials)}", c,
                               {"seed": self.best["seed"], "mem_latency": self.best["mem_latency"], **meta})])
            rec = recs[0]
            if not rec['conclusive']:
                return None
            if rec['match']:
                best_rec = rec
                self._take(rec)  # Stream size, rather than failure cycle, is the objective.
            return rec['match']
        kept, reason = minimize(items, probe)
        if reason == "inconclusive_or_budget":
            reason = "budget_exhausted" if exhausted else "inconclusive"
        if best_rec is not None:
            self._take(best_rec)
        self.stream_results[name] = {"original": len(items), "remaining": len(kept),
                                     "kept": kept, "completion": reason,
                                     "one_minimal": reason == 'one_minimal', "global_minimum": False}

    def mode_instructions(self):
        if not self.o.instructions:
            raise ValueError("instructions mode needs --instruction-symbol NAME")
        from .streams import instruction_slots
        for name in self.o.instructions:
            src = self.best['elf']
            elf = Elf(src)
            slots = instruction_slots(elf, name)
            base = self.best['cmd']
            def command(kept):
                e = Elf(src)
                keep = set(kept)
                for i, (off, size) in enumerate(slots):
                    if i not in keep:
                        e.data[off:off+size] = bytes.fromhex('0100' if size == 2 else '13000000')
                p = self.out / f'instructions-{len(self.trials)}.elf'
                e.save(str(p))
                item = self.inputs.capture.file(p)
                if item.sha256 != hashlib.sha256(e.data).hexdigest():
                    raise CaptureError('input_not_captured:patched_elf', 'instruction ELF changed before capture')
                return base.set(elf=str(item.copy)), {"elf": str(item.copy), "instructions_kept": kept}
            self._stream_search('instructions:' + name, range(len(slots)), command)

    def mode_irq(self):
        from .streams import irq_entries
        base = self.best['cmd']
        text = base.get('irq_schedule')
        if not text:
            raise ValueError('irq mode needs --irq-schedule in the original replay')
        entries = irq_entries(text)
        # The first event selects schedule mode and sets initial levels. Keep it.
        def command(kept):
            schedule = ','.join([entries[0], *[entries[i] for i in kept]])
            return base.set(irq_schedule=schedule), {"irq_schedule": schedule, "elf": self.best['elf']}
        self._stream_search('irq', range(1, len(entries)), command)

    def _take(self, rec: dict) -> None:
        c = rec["_cmd"]
        self.best.update({"cycles": rec["cycles"], "cmd": c, "dir": rec["dir"], "trial": rec["id"],
                          "seed": rec.get("seed", self.best["seed"]),
                          "mem_latency": rec.get("mem_latency", self.best["mem_latency"]),
                          "elf": rec.get("elf", self.best["elf"]), "max_cycles": c.get("max_cycles")})

    # -----------------------------------------------------------------------------------------

    def reduce(self) -> dict:
        self.say(f"target signature {self.sig}; original fails at cycle {self.run.get('cycles')}")
        for m in self.o.modes:
            if len(self.trials) >= self.o.budget:
                self.say("trial budget exhausted")
                break
            getattr(self, f"mode_{m}")()
        # Confirm the best reproduction with the tightest max cycles
        b = self.best
        if b["cycles"] is not None and b["trial"] is not None and b["max_cycles"] is not None \
                and int(b["max_cycles"]) > int(b["cycles"]) + self.o.margin:
            self.trial([("confirm", b["cmd"].set(max_cycles=int(b["cycles"]) + self.o.margin),
                         {"seed": b["seed"], "mem_latency": b["mem_latency"], "elf": b["elf"]})])
        return self.save(final=True)

    def save(self, final: bool = False) -> dict:
        b = self.best
        rep = {"schema": "rvw.reduce/1", "run": str(self.run.dir), "out": str(self.out), "signature": self.sig,
               "original": {"cycles": self.run.get("cycles"), "seed": self.run.get("seed"),
                            "elf": self.run.get("elf"),
                            "mem_latency": self.run.get("mem_latency"), "max_cycles": self.run.get("max_cycles")},
               "best": {"cycles": b["cycles"], "seed": b["seed"], "mem_latency": b["mem_latency"],
                        "elf": b["elf"], "max_cycles": b["max_cycles"], "dir": b["dir"], "trial": b["trial"],
                        "replay": b["cmd"].set(out="OUT_DIR").shell()},
               "reproducing_settings": sorted({(t.get("seed"), t.get("mem_latency")) for t in self.trials
                                               if t["match"]}, key=lambda x: (str(x[1]), x[0] or 0)),
               "reproduced": any(t["match"] for t in self.trials), "hang_cycles": self.o.hang_cycles,
               "notes": self.notes, "symbols": self.symbol_results, "streams": self.stream_results, "capture": self.inputs.record(),
               "cache_key": None, "source": self.inputs.source_metadata(),
               "trials": [{k: v for k, v in t.items() if k != "_cmd"} for t in self.trials],
               "budget_exhausted": len(self.trials) >= self.o.budget,
               "wall_s": round(time.monotonic() - self.t0, 1), "final": final}
        (self.report_dir / "reduce.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
        if not final:
            import shutil
            import uuid
            temporary = self.out / f'.reduce-{uuid.uuid4().hex}'
            shutil.copyfile(self.report_dir / 'reduce.json', temporary)
            temporary.replace(self.out / 'reduce.json')
        if final:
            (self.report_dir / "reduce.md").write_text(render_md(rep))
            self.inputs.publish(self.out, ["reduce.json", "reduce.md"], source=self.report_dir)
        return rep


def render_md(r: dict) -> str:
    b, o = r["best"], r["original"]
    lat = lambda v: "random" if v is None else f"fixed {v}"
    L = [f"# Reduction of {r['signature']}", ""]
    if not r.get("reproduced"):
        L += ["**No trial reproduced the signature.** The best run below is the original run.", ""]
    L += [f"- Original: seed {o['seed']}, memory {lat(o['mem_latency'])}, fails at cycle {o['cycles']}",
         f"- Best: seed {b['seed']}, memory {lat(b['mem_latency'])}, fails at cycle **{b['cycles']}** "
         f"with max cycles {b['max_cycles']}" + (f", ELF {b['elf']}" if b['elf'] != o.get('elf') else ""),
         f"- Best run: `{b['dir']}`", f"- Replay: `{b['replay']}`",
         f"- {sum(t['match'] for t in r['trials'])}/{len(r['trials'])} trials reproduced the signature "
         f"({r['wall_s']} s)"]
    L += [f"- Note: {n}" for n in r.get("notes") or []]
    for name, sr in (r.get("streams") or {}).items():
        L.append(f"- Stream `{name}`: {sr['original']} -> {sr['remaining']}; {sr['completion']}. "
                 "No global minimum is claimed.")
    for name, sr in (r.get("symbols") or {}).items():
        if sr['smallest_failing'] is None:
            L.append(f"- Symbol `{name}` ({sr['bytes']} bytes): no minimum ({sr['note']})")
            continue
        L.append(f"- Symbol `{name}` ({sr['bytes']} bytes): {sr['original']} -> smallest tested failing "
                 f"{sr['smallest_failing']}" + (f" (exact: {sr.get('exact_by')})" if sr["exact"]
                                                else f" ({sr.get('note') or 'not proven minimal'})")
                 + f", ELF `{sr['elf']}`")
    L += ["", "| # | trial | seed | memory | max cycles | result | cycles | match |",
         "|---|---|---|---|---|---|---|---|"]
    for t in r["trials"]:
        L.append(f"| {t['id']} | {t['label']} | {t.get('seed')} | {lat(t.get('mem_latency'))} | {t['max_cycles']} "
                 f"| {t['signature']} | {t['cycles']} | {'yes' if t['match'] else ''} |")
    L += ["", f"Next: `rvw bundle {b['dir']}`", ""]
    return "\n".join(L)
