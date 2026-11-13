"""Paired RTL deltas with one frozen base calibration."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path

from rvw.arch.ledger import store
from rvw.cosim.trace import Trace
from rvw.results.schema import RunResult
from .core import _instructions, run, simulate
from .evidence import digest, plan_max_cycles, verify_captures
from .project import configuration
from .search import set_value


def delta_error(measured, predicted):
    """Relative IPC changes use fractions. A zero measured delta has no ratio."""
    sign = (measured > 0) - (measured < 0)
    predicted_sign = (predicted > 0) - (predicted < 0)
    relative = abs(predicted - measured) / abs(measured) if measured else None
    return dict(sign_match=sign == predicted_sign, absolute_error_pp=100*abs(predicted-measured),
                relative_error=relative, wrong_delta=sign != predicted_sign or
                (relative is not None and relative > .5),
                status="reported" if measured else "zero_measured_delta")


def delta(plan, out):
    p = Path(plan).resolve()
    spec = json.loads(p.read_text())
    if spec.get("schema") != "rvw.ooo-delta-plan/1":
        raise ValueError("expected delta plan")
    path = lambda value: (p.parent/value).resolve()
    cp, cal = path(spec["config"]), path(spec["calibration"])
    calibration = json.loads(cal.read_text())
    if calibration.get("schema") != "rvw.ooo-calibration/1":
        raise ValueError("expected frozen base calibration")
    verify_captures(calibration)
    if digest(cp) != calibration["samples"]["training"][0]["model"]["config_sha256"]:
        raise ValueError("config differs from frozen base calibration")
    base = asdict(configuration(json.loads(cp.read_text())))
    budget = plan_max_cycles(spec)
    variants = spec["variants"]
    if not variants or len({v["id"] for v in variants}) != len(variants):
        raise ValueError("unique nonempty variants required")
    configurations = {}
    for variant in variants:
        changes = variant["changes"]
        if not isinstance(changes, dict) or len(changes) != 1:
            raise ValueError("each variant must change exactly one parameter")
        data = deepcopy(base)
        for key, value in changes.items():
            set_value(data, key, value)
        if data == base:
            raise ValueError("variant must differ from base")
        configuration(data)
        configurations[variant["id"]] = data

    def capture(sample):
        paths = {k: path(sample[k]) for k in ("elf", "c1", "trace")}
        c1 = RunResult.from_dict(json.loads(paths["c1"].read_text()))
        if c1.status != "pass" or c1.why_inconclusive or not c1.cycles or c1.cycles < 1:
            raise ValueError("conclusive C1 pass with positive cycles required")
        if c1.elf_sha256 != digest(paths["elf"]):
            raise ValueError("C1 ELF hash mismatch")
        trace = Trace(paths["trace"])
        try:
            header = trace.header.copy()
            list(trace)
        finally:
            trace.close()
        if any(header[k] != getattr(c1, k) for k in ("core", "config", "elf")):
            raise ValueError("C1/C2 identity mismatch")
        ops = _instructions(paths["trace"].read_bytes(), base["custom_instructions"])
        if len(ops) != c1.instret:
            raise ValueError("C1/C2 instruction count mismatch")
        return c1, ops, paths

    dest = Path(out).resolve()
    dest.mkdir(parents=True, exist_ok=False)
    rows, seen = [], set()
    engine_checked = False
    for sample in spec["samples"]:
        name = sample["id"]
        if name in seen:
            raise ValueError("duplicate sample id")
        seen.add(name)
        measured_base, ops, paths = capture(sample["base"])
        reference = calibration["samples"]["training"][0]["model"]
        trace_hash, c1_hash = digest(paths["trace"]), digest(paths["c1"])
        frozen = [r["model"] for split in calibration["samples"].values() for r in split
                  if r["hashes"]["trace"] == trace_hash
                  and r["hashes"]["c1"] == c1_hash
                  and r["model"]["engine_sha256"] == reference["engine_sha256"]]
        model_base = frozen[0] if engine_checked and frozen else run(cp, paths["trace"], budget)
        engine_checked = True
        if model_base["cycles"] > budget:
            raise ValueError("model cycle budget exhausted")
        if model_base["engine_sha256"] != reference["engine_sha256"]:
            raise ValueError("engine differs from calibration; recalibrate on base")
        if set(sample["variants"]) != set(configurations):
            raise ValueError("each sample must contain every variant")
        for vid, variant_sample in sample["variants"].items():
            measured, other_ops, other_paths = capture(variant_sample)
            if any(getattr(measured, key) != getattr(measured_base, key)
                   for key in ("core", "elf_sha256", "seed", "mem_latency")) or other_ops != ops:
                raise ValueError("pair must use identical program, trace semantics, seed and memory timing")
            # Both predictions use the base stream. No variant cycle enters prediction.
            predicted = simulate(ops, configuration(configurations[vid]), budget)
            predicted["config"] = configurations[vid]
            rtl_delta = measured_base.cycles/measured.cycles-1
            model_delta = predicted["ipc"]/model_base["ipc"]-1
            rows.append(dict(program=name, variant=vid, measured_delta=rtl_delta,
                             predicted_delta=model_delta, **delta_error(rtl_delta, model_delta),
                             rtl_base_ipc=measured_base.instret/measured_base.cycles,
                             rtl_variant_ipc=measured.instret/measured.cycles,
                             model_base=model_base, model_variant=predicted,
                             hashes={k:digest(v) for k,v in other_paths.items()},
                             base_hashes={k:digest(v) for k,v in paths.items()}))
    if not rows:
        raise ValueError("nonempty samples required")
    return store(dest/"report.json", dict(schema="rvw.ooo-delta/1", status="reported",
        calibration_sha256=digest(cal), config_sha256=digest(cp), variants=variants, rows=rows,
        summary=dict(pairs=len(rows), wrong_deltas=sum(r["wrong_delta"] for r in rows)),
        limits=["retrospective paired timing comparison; no new RTL or Spike run",
                "one base calibration; base committed stream reused for all predictions",
                "zero measured delta has no relative error; exact sign comparison",
                "no fidelity verdict; top-down predicates require separate semantic checks"]))
