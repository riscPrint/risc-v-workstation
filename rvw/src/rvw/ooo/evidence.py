"""Saved C1/C2 calibration. Whole-program regions only; no RTL jobs run here."""
from hashlib import sha256
from pathlib import Path
import json

from rvw.arch.statistics import correlation
from rvw.arch.ledger import store, now
from rvw.cosim.trace import Trace
from rvw.results.schema import RunResult
from .core import run


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def plan_max_cycles(data):
    """Optional model cycle budget of a calibration plan (default one million)."""
    value = data.get("max_cycles", 1_000_000)
    if type(value) is not int or value < 1:
        raise ValueError("max_cycles must be a positive integer")
    return value


def calibrate(plan, out, project=None):
    """Score a frozen model on saved training/held-out evidence without fitting."""
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    plan = Path(plan).resolve()
    data = json.loads(plan.read_text())
    if data.get("schema") != "rvw.ooo-calibration-plan/1":
        raise ValueError("invalid calibration plan")
    def path(value):
        return (plan.parent / value).resolve()
    config, event_map = path(data["config"]), path(data["event_map"])
    max_cycles = plan_max_cycles(data)
    mapping = json.loads(event_map.read_text())
    if not isinstance(mapping, dict):
        raise ValueError("event map must be an object")
    for name, spec in mapping.items():
        if not isinstance(spec, dict) or any(not spec.get(k) for k in
            ("model_event", "rtl_event", "edge", "unit", "identity", "family")):
            raise ValueError("event map needs edge, unit, identity and family")
        if spec.get("region") != "whole-program":
            raise ValueError("only whole-program event regions are supported")
    captures = {str(p): digest(p) for p in (plan, config, event_map)}
    splits = {"training": [], "heldout": []}
    seen_elf, seen_trace, seen_ids = {}, {}, set()
    for sample in data["samples"]:
        split = sample["split"]
        if split not in splits or sample["id"] in seen_ids:
            raise ValueError("invalid split or duplicate sample id")
        seen_ids.add(sample["id"])
        paths = {k: path(sample[k]) for k in ("elf", "trace", "c1", "events")}
        hashes = {k: digest(p) for k, p in paths.items()}
        for key, seen in (("elf", seen_elf), ("trace", seen_trace)):
            if hashes[key] in seen and seen[hashes[key]] != split:
                raise ValueError("training/heldout overlap by " + key)
            seen[hashes[key]] = split
        captures.update({str(p): hashes[k] for k, p in paths.items()})
        c1 = RunResult.from_dict(json.loads(paths["c1"].read_text()))
        if c1.status != "pass" or c1.why_inconclusive:
            raise ValueError("C1 must be a conclusive pass")
        if c1.elf_sha256 != hashes["elf"]:
            raise ValueError("C1 ELF hash mismatch")
        trace = Trace(paths["trace"])
        try:
            header = trace.header.copy()
            list(trace)
        finally:
            trace.close()
        if header["core"] != c1.core or header["config"] != c1.config:
            raise ValueError("C1/C2 core or configuration mismatch")
        if header["elf"] != c1.elf:
            raise ValueError("C1/C2 ELF identity mismatch")
        predicted = run(config, paths["trace"], max_cycles)
        if predicted["instret"] != c1.instret:
            raise ValueError("whole-program C1/C2 instruction count mismatch")
        if type(c1.cycles) is not int or c1.cycles < 1:
            raise ValueError("positive C1 cycles required")
        observed = json.loads(paths["events"].read_text())
        if observed.get("c1_sha256") != hashes["c1"] or observed.get("trace_sha256") != hashes["trace"]:
            raise ValueError("RTL events are not bound to C1/C2 evidence")
        errors = {}
        for name, spec in mapping.items():
            measured = observed.get("counts", {}).get(spec["rtl_event"])
            modeled = predicted["events"].get(spec["model_event"], 0)
            if measured is None:
                errors[name] = dict(status="missing", measured=None, modeled=modeled, error_percent=None)
            elif type(measured) is not int or measured < 0:
                raise ValueError("event counts must be nonnegative integers")
            else:
                errors[name] = dict(status="reported" if measured else "zero_denominator",
                                    measured=measured, modeled=modeled,
                                    error_percent=100*(modeled/measured-1) if measured else None)
        rtl_ipc = c1.instret / c1.cycles
        splits[split].append(dict(id=sample["id"], hashes=hashes, events=errors,
            identity={k: getattr(c1, k) for k in ("core", "config", "elf", "elf_sha256", "seed", "mem_latency")},
            ipc_error_percent=100*(predicted["ipc"]/rtl_ipc-1), model=predicted,
            rtl_cycles=c1.cycles, rtl_ipc=rtl_ipc))
    if not splits["training"] or not splits["heldout"]:
        raise ValueError("training and heldout samples required")
    held = splits["heldout"]
    correlations = {name: correlation([(r["events"][name]["modeled"], r["events"][name]["measured"])
        for r in held if r["events"][name]["measured"] is not None]) for name in mapping}
    enough = len(held) >= 5 and len({s["family"] for s in mapping.values()}) >= 3
    ipc_ok = all(abs(r["ipc_error_percent"]) <= 10 for r in held)
    event_ok = bool(mapping) and all(e["error_percent"] is not None and abs(e["error_percent"]) <= 15
                   for r in held for e in r["events"].values())
    return store(out, dict(schema="rvw.ooo-calibration/1", created_at=now(),
        status="reported", accuracy_status="inconclusive", captures=captures,
        samples=splits, correlations=correlations,
        budgets=dict(ipc_percent=10, nonzero_event_percent=15, sufficient_coverage=enough,
                     observed_ipc_within_budget=ipc_ok, observed_events_within_budget=event_ok),
        limits=["saved whole-program observations only; no fitting performed",
                "event mappings are producer declarations, not independently verified",
                "no native RTL speed qualification; no fidelity verdict"]))


def verify_captures(report):
    for path, expected in report["captures"].items():
        if digest(path) != expected:
            raise ValueError("calibration evidence changed: " + path)


def predict(calibration, config, trace, out, project=None):
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    report = json.loads(Path(calibration).read_text())
    if report.get("schema") != "rvw.ooo-calibration/1":
        raise ValueError("invalid calibration record")
    verify_captures(report)
    prediction = run(config, trace)
    # A new prediction must use exactly the frozen fitted configuration and engine.
    reference = report["samples"]["training"][0]["model"]
    for key in ("config_sha256", "engine_sha256"):
        if prediction[key] != reference[key]:
            raise ValueError("prediction differs from frozen calibration: " + key)
    selected = [r for r in report["samples"]["heldout"] if r["hashes"]["trace"] == prediction["trace_sha256"]]
    if not selected:
        raise ValueError("prediction requires a frozen heldout trace")
    identity = selected[0]["identity"]
    return store(out, dict(schema="rvw.ooo-prediction/1", identity=identity, created_at=now(),
        calibration=str(Path(calibration).resolve()), calibration_sha256=digest(calibration),
        config=str(Path(config).resolve()), trace=str(Path(trace).resolve()),
        prediction=prediction, status="predicted",
        limits=["local timestamp only; trace already exists before prediction",
                "later C1 scoring does not qualify native repeat speed"]))


def score_prediction(prediction, c1, out, project=None):
    """Score later C1 timing separately from the pre-existing prediction."""
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    from datetime import datetime, timezone
    record = json.loads(Path(prediction).read_text())
    if record.get("schema") != "rvw.ooo-prediction/1":
        raise ValueError("invalid prediction record")
    created = datetime.fromisoformat(record["created_at"])
    if created.tzinfo is None or created > datetime.now(timezone.utc):
        raise ValueError("invalid prediction timestamp")
    if Path(c1).stat().st_mtime <= created.timestamp():
        raise ValueError("C1 observation must be recorded after prediction")
    if digest(record["calibration"]) != record["calibration_sha256"]:
        raise ValueError("calibration record changed")
    calibration = json.loads(Path(record["calibration"]).read_text())
    verify_captures(calibration)
    model = run(record["config"], record["trace"])
    for key in ("config_sha256", "trace_sha256", "engine_sha256", "cycles", "instret"):
        if model[key] != record["prediction"][key]:
            raise ValueError("prediction evidence changed: " + key)
    observation = RunResult.from_dict(json.loads(Path(c1).read_text()))
    identity = record["identity"]
    if observation.status != "pass" or observation.why_inconclusive:
        raise ValueError("later C1 must be a conclusive pass")
    if any(getattr(observation, k) != identity[k] for k in ("elf_sha256", "core", "config", "elf", "seed", "mem_latency")):
        raise ValueError("later C1 identity mismatch")
    if observation.instret != model["instret"] or type(observation.cycles) is not int or observation.cycles < 1:
        raise ValueError("later C1 instruction region mismatch")
    rtl_ipc = observation.instret / observation.cycles
    return store(out, dict(schema="rvw.ooo-prediction-score/1", scored_at=now(),
        prediction_sha256=digest(prediction), c1_sha256=digest(c1),
        ipc_error_percent=100*(model["ipc"]/rtl_ipc-1), status="reported",
        accuracy_status="inconclusive",
        limits=["local timestamps only; no trusted chronology or blinding",
                "instruction counts and declared region only; no later C2 stream comparison",
                "native repeat speed and later event qualification not performed"]))
