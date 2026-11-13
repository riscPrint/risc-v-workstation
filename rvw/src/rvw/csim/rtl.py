"""Compare a predictor model with explicit RTL predictor events, branch by branch.

Event sources:
  * `rvw.bp-events/1` JSONL written by a project-owned probe binding;
  * a Kanata log with `#rvw 1 prediction` records (observed outcomes);
  * a Kanata log without them: retirement-inferred redirects only (reported apart).
The model runs on the same C2 trace. Missing identity, missing events or ambiguous
alignment makes the comparison `inconclusive`. No result is ever a match verdict.
"""
from __future__ import annotations

import json
import re
import tempfile
from collections import defaultdict
from pathlib import Path

from . import config as cfg
from . import study as st
from . import traces

EVENTS = "rvw.bp-events/1"
REPORT = "rvw.csim-rtl-compare/1"
PC_LABEL = re.compile(r"^\s*(?:0x)?([0-9a-fA-F]+)\s*:")


def _addr(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    return int(v, 16) if str(v).startswith("0x") else int(v)


def read_bp_events(path: Path) -> tuple[dict, dict[int, dict]]:
    """Return (header, {order: {"pc", "kind", "direction": (pred, act), "target": (pred, act)}})."""
    rows: dict[int, dict] = {}
    with Path(path).open() as f:
        header = json.loads(f.readline())
        if header.get("schema") != EVENTS:
            raise ValueError(f"expected {EVENTS} header")
        for n, line in enumerate(f, 2):
            if not line.strip():
                continue
            r = json.loads(line)
            order = r.get("order")
            if not isinstance(order, int) or order < 0:
                raise ValueError(f"line {n}: order must be a nonnegative integer (speculative events carry no order)")
            if order in rows:
                raise ValueError(f"line {n}: duplicate event for order {order}")
            e = {"pc": _addr(r["pc"]), "kind": r.get("kind", "cond")}
            if "btb_hit" in r:
                if type(r["btb_hit"]) is not bool:
                    raise ValueError("btb_hit must be boolean")
                e["btb_hit"] = r["btb_hit"]
            if "predicted_taken" in r:
                e["direction"] = (bool(r["predicted_taken"]), bool(r["taken"]))
            if "predicted_target" in r:
                e["target"] = (_addr(r["predicted_target"]), _addr(r["target"]))
            rows[order] = e
    return header, rows


def read_kanata(path: Path) -> tuple[dict, dict[int, dict], dict]:
    """Observed prediction events keyed by retirement order, plus inferred redirects."""
    from rvw.perf import kanata

    trace = kanata.read(path)
    committed = [i for i in sorted(trace.instructions.values(), key=lambda i: (i.end if i.end is not None else 1 << 62, i.ordinal))
                 if i.end is not None and not i.flushed]
    order_of = {i.id: n for n, i in enumerate(committed)}
    pcs = {}
    for i in committed:
        m = PC_LABEL.match(i.labels.get("0", ""))
        pcs[i.id] = int(m.group(1), 16) if m else None
    rows: dict[int, dict] = {}
    speculative = 0
    for p in trace.predictions:
        key = p["instruction"]
        if key not in order_of:
            speculative += 1
            continue
        o = order_of[key]
        e = rows.setdefault(o, {"pc": pcs[key], "kind": "cond"})
        if p["kind"] == "direction":
            e["direction_correct"] = p["correct"]
        else:
            e["target_correct"] = p["correct"]
            if p["kind"] == "return":
                e["kind"] = "ret"
    # Inferred redirects: a committed instruction followed by flushed work in fetch order.
    by_fetch = sorted(trace.instructions.values(), key=lambda i: i.ordinal)
    inferred = defaultdict(int)
    last = None
    for i in by_fetch:
        if i.flushed and last is not None and pcs.get(last.id) is not None:
            inferred[last.id] += 1
        elif not i.flushed and i.end is not None:
            last = i
    redirects = {order_of[k]: pcs[k] for k in inferred if k in order_of}
    return {"source": "kanata", "speculative_events": speculative}, rows, redirects


def read_model(path: Path) -> dict[int, dict]:
    rows = {}
    with Path(path).open() as f:
        version = f.readline().strip()
        if version not in ("rvw.csim-predictions/1", "rvw.csim-predictions/2"):
            raise ValueError("bad predictions file")
        for line in f:
            fields = line.split()
            o, pc, kind, taken, pt, tgt, ptgt = fields[:7]
            hit = (None if int(fields[7]) == -2 else int(fields[7]) >= 0) if version.endswith("/2") else None
            rows[int(o)] = {"pc": int(pc, 16), "kind": kind, "taken": taken == "1", "pred_taken": pt == "1",
                            "target": int(tgt, 16), "pred_target": int(ptgt, 16), "btb_hit": hit, "btb_level": int(fields[7]) if version.endswith("/2") else None}
    return rows


def compare(study_path, c2_path, events_path, roi_start: int | None = None, roi_end: int | None = None,
            elf_sha256: str | None = None, top: int = 20) -> dict:
    data = cfg.load(study_path)
    reasons: list[str] = []
    c2 = Path(c2_path)
    with c2.open() as f:
        c2_header = json.loads(f.readline())
    inferred: dict[int, int | None] = {}
    with traces._open_text(Path(events_path)) as f:
        is_kanata = f.readline().startswith("Kanata")
    if not is_kanata:
        header, events = read_bp_events(Path(events_path))
        source = "bp-events"
    else:
        header, events, inferred = read_kanata(Path(events_path))
        source = "kanata"
    # --- identity
    trace_elf = c2_header.get("elf_sha256") or elf_sha256
    event_elf = header.get("elf_sha256")
    if source == "kanata":
        event_elf = event_elf or elf_sha256
    if not trace_elf or not event_elf:
        reasons.append("missing ELF identity on the trace or the events")
    elif trace_elf != event_elf:
        reasons.append("ELF identity differs between trace and events")
    if header.get("hart", 0) not in (0, "0"):
        reasons.append("events are for another hart")
    semantics = header.get("counter_semantics", "unknown")
    if semantics not in ("first-prediction", "final-prediction"):
        reasons.append("counter semantics not declared (first-prediction or final-prediction)")
    if header.get("speculative_events"):
        reasons.append(f"{header['speculative_events']} events for squashed instructions are unsupported")
    roi = header.get("roi") or {}
    start = roi_start if roi_start is not None else int(roi.get("start_order", 0))
    end = roi_end if roi_end is not None else roi.get("end_order")
    # --- model run on the same trace, warmed up to the ROI start
    with tempfile.TemporaryDirectory(prefix="rvw-csim-rtl-") as tmp:
        tmp = Path(tmp)
        csim = tmp / "trace.csim"
        info = traces.from_c2(c2, csim)
        run = json.loads(json.dumps(data))
        pred_file = tmp / "pred.txt"
        run.setdefault("report", {})["predictions_file"] = str(pred_file)
        run["warmup_instructions"] = start
        if end is not None:
            run["simulation_instructions"] = int(end) - start + 1
        rep = st._engine(cfg.to_kv(run), csim, "csim", None)
        model = read_model(pred_file)
    # The C2 converter numbers instructions from 1: ordinal = order - first + 1.
    first = None
    with c2.open() as f:
        f.readline()
        for line in f:
            r = json.loads(line)
            if "event" not in r:
                first = int(r["order"]); break
    first = first or 0
    d = defaultdict(int); t = defaultdict(int)
    for side in ('rtl', 'model'):
        for status in ('btb-miss','not-predicted','wrong-target','correct','not-taken','unknown'):
            t[side + '_' + status] = 0
    per = defaultdict(lambda: defaultdict(int))
    misaligned = missing = 0
    for ordn, m in model.items():
        order = ordn - 1 + first
        e = events.get(order)
        is_dir = m["kind"] == "cond"
        if e is None:
            if is_dir:
                missing += 1
            continue
        if e.get("pc") is not None and e["pc"] != m["pc"]:
            misaligned += 1
            continue
        b = per[m["pc"]]
        b["kind"] = m["kind"]
        b["executed"] += 1
        if is_dir and ("direction" in e or "direction_correct" in e):
            model_ok = m["pred_taken"] == m["taken"]
            if "direction" in e:
                rp, ra = e["direction"]
                if ra != m["taken"]:
                    misaligned += 1
                    continue
                rtl_ok = rp == ra
                d["disagree"] += rp != m["pred_taken"]
            else:
                rtl_ok = bool(e["direction_correct"])
                d["disagree"] += rtl_ok != model_ok  # same outcome: prediction agreement follows correctness
            d["events"] += 1
            d["rtl_misses"] += not rtl_ok; d["model_misses"] += not model_ok
            d["both_wrong"] += not rtl_ok and not model_ok
            d["rtl_only_wrong"] += not rtl_ok and model_ok; d["model_only_wrong"] += rtl_ok and not model_ok
            b["rtl_direction_misses"] += not rtl_ok; b["model_direction_misses"] += not model_ok
            b["direction_disagreements"] += (not rtl_ok) != (not model_ok)
        elif is_dir:
            missing += 1
        if "target" in e or "target_correct" in e:
            from .target_status import classify
            model_status = classify(taken=m['taken'], predicted_taken=m['pred_taken'],
                                    btb_hit=m.get('btb_hit') if m['kind'] in ('cond','jump','call') else None, predicted_target=None if m.get('btb_level') == -2 and m['kind'] in ('cond','jump','call') else m['pred_target'], target=m['target'])
            rtl_status = classify(taken=m['taken'], predicted_taken=e.get('direction', (None,None))[0],
                                  btb_hit=e.get('btb_hit') if m['kind'] in ('cond','jump','call') else None, predicted_target=e.get('target',(None,None))[0], target=m['target'])
            t['model_' + model_status] += 1
            t['rtl_' + rtl_status] += 1
            t['status_disagreements'] += model_status != rtl_status
            comparable = model_status in ('correct','wrong-target') and rtl_status in ('correct','wrong-target')
            t['address_comparable'] += comparable
            t['address_disagreements'] += comparable and e['target'][0] != m['pred_target']
            model_ok = model_status in ('correct', 'not-taken')
            rtl_ok = rtl_status in ('correct', 'not-taken') if rtl_status != 'unknown' else (not m['taken'] or bool(e.get('target_correct',False)))
            t["events"] += 1
            t["rtl_misses"] += not rtl_ok; t["model_misses"] += not model_ok
            t["disagree"] += rtl_ok != model_ok
            b["rtl_target_misses"] += not rtl_ok; b["model_target_misses"] += not model_ok
    extra = sum(1 for o in events if (o - first + 1) not in model and (end is None or o <= int(end)) and o >= start)
    if missing:
        reasons.append(f"{missing} conditional branches in the ROI have no RTL direction event")
    if misaligned:
        reasons.append(f"{misaligned} events do not align with the trace (PC or outcome differs)")
    if extra:
        reasons.append(f"{extra} events have no matching branch in the trace ROI")
    if not d["events"] and not t["events"]:
        reasons.append("no comparable events")
    measured = rep["trace"]["measured_instructions"]

    def summary(c):
        if not c["events"]:
            return {"events": 0}
        out = dict(c)
        out["rtl_mpki"] = 1000 * c["rtl_misses"] / measured
        out["model_mpki"] = 1000 * c["model_misses"] / measured
        out["agreement"] = 1 - c["disagree"] / c["events"]
        return out

    rows = sorted(({"pc": hex(pc), **dict(v)} for pc, v in per.items()),
                  key=lambda r: -(r.get("direction_disagreements", 0) + abs(r.get("rtl_target_misses", 0) - r.get("model_target_misses", 0))))
    inferred_section = None
    if source == "kanata":
        mm = sum(1 for o in model.values() if o["pred_taken"] != o["taken"] or (o["taken"] and o["pred_target"] != o["target"]))
        inferred_section = {"basis": "committed instruction followed by squashed work in fetch order; not an observed predictor outcome",
                            "rtl_inferred_redirects": len(inferred), "model_redirects": mm}
    return {"schema": REPORT, "status": "inconclusive" if reasons else "compared", "reasons": reasons,
            "event_source": source, "counter_semantics": semantics, "roi": {"start_order": start, "end_order": end},
            "study": data.get("name"), "study_sha256": cfg.digest(data), "fidelity": (data.get("source") or {}).get("fidelity", "unqualified"),
            "trace": {"path": str(c2), **info}, "events": str(events_path),
            "observed": {"direction": summary(d), "target": summary(t)}, "inferred": inferred_section,
            "per_branch": rows[:top], "measured_instructions": measured,
            "note": "Agreement is a measured model gap, not an RTL correctness or fidelity verdict."}
