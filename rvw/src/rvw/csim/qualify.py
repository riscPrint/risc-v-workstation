"""Qualify csim direction models against pinned external reference predictors.

The reference sources are fetched into the csim cache (outside the repository),
checked against a pinned SHA-256 and built with an owner-written harness and
type shim. No reference source enters the repository. The comparison is
statistical (MPKI) and per branch (prediction agreement). Different hashing
means agreement below 1 is expected; it is a measured gap, not a defect claim.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from . import config as cfg
from . import engine
from . import study as st

REFERENCES = {
    "cbp2016-tage-sc-l-64kb": {
        "url": "http://www.jilp.org/cbp2016/code/AndreSeznecLimited.tar.gz",
        "sha256": "5ed93324d8b06f1fc53f47a75f9e445b07c10573a49a08d1e4621dacd5ace181",
        "dir": "AndreSeznecLimited/cbp64KB",
        "study": "tage-sc-l-64kb.json",
        "paper": "A. Seznec, TAGE-SC-L Branch Predictors Again, CBP-5 2016",
    },
    "cbp2016-tage-sc-l-8kb": {
        "url": "http://www.jilp.org/cbp2016/code/AndreSeznecLimited.tar.gz",
        "sha256": "5ed93324d8b06f1fc53f47a75f9e445b07c10573a49a08d1e4621dacd5ace181",
        "dir": "AndreSeznecLimited/cbp8KB",
        "study": "tage-sc-l-8kb.json",
        "paper": "A. Seznec, TAGE-SC-L Branch Predictors Again, CBP-5 2016",
    },
}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str, archive: Path | None = None) -> Path:
    """Return the extracted reference directory. `archive` uses a local copy."""
    ref = REFERENCES[name]
    base = engine.cache_dir() / "refs" / ref["sha256"][:16]
    src = base / ref["dir"]
    if (src / "predictor.h").is_file():
        return src
    base.mkdir(parents=True, exist_ok=True)
    tar = base / "source.tar.gz"
    if archive:
        shutil.copyfile(archive, tar)
    elif not tar.is_file():
        with urllib.request.urlopen(ref["url"], timeout=120) as r, tar.open("wb") as o:
            shutil.copyfileobj(r, o)
    got = _sha(tar)
    if got != ref["sha256"]:
        tar.unlink()
        raise ValueError(f"{name}: archive sha256 {got} does not match the pinned {ref['sha256']}")
    with tarfile.open(tar) as t:
        t.extractall(base, filter="data")
    if not (src / "predictor.h").is_file():
        raise ValueError(f"{name}: predictor.h missing after extraction")
    return src


# Upstream sources read NOSKIP[i] / gtable[i] with i = NHIST + 1 in the allocation
# loop (out of bounds; found with AddressSanitizer on the 8 KB predictor). The
# guard keeps every in-range access identical.
PATCH = ("if (NOSKIP[i])", "if (i <= NHIST && NOSKIP[i])")


def patched(name: str, archive: Path | None = None) -> Path:
    src = fetch(name, archive)
    out = src.parent / (src.name + "-guarded")
    if not (out / "predictor.h").is_file():
        out.mkdir(exist_ok=True)
        for f in src.iterdir():
            text = f.read_text(errors="replace")
            (out / f.name).write_text(text.replace(*PATCH) if f.name == "predictor.h" else text)
    return out


def build(name: str, archive: Path | None = None) -> Path:
    src = patched(name, archive)
    here = engine.source_dir() / "qualify"
    h = hashlib.sha256((here / "ref_harness.cc").read_bytes() + (here / "shim" / "utils.h").read_bytes()
                       + (src / "predictor.h").read_bytes()).hexdigest()[:12]
    out = engine.cache_dir() / "refs" / f"{name}-{h}"
    if out.is_file():
        return out
    cmd = [engine.compiler(), "-std=c++17", "-O2", "-w", f"-I{here / 'shim'}", f"-I{src}", str(here / "ref_harness.cc"), "-o", str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode:
        raise RuntimeError(f"reference build failed:\n{res.stderr[-3000:]}")
    return out


def _preds(path: Path) -> dict[int, tuple[int, bool, bool]]:
    rows = {}
    with path.open() as f:
        if f.readline().strip() != "rvw.csim-predictions/1":
            raise ValueError("bad predictions file")
        for line in f:
            o, pc, kind, taken, pred, *_ = line.split()
            if kind == "cond":
                rows[int(o)] = (int(pc, 16), taken == "1", pred == "1")
    return rows


def default_study(name: str) -> Path:
    return engine.source_dir() / "examples" / REFERENCES[name]["study"]


def qualify(name: str, trace_paths: list, study=None, fmt: str = "auto", tolerance: float = 0.10,
            archive: Path | None = None, top: int = 10) -> dict:
    if name not in REFERENCES:
        raise ValueError(f"unknown reference {name}; known: {', '.join(REFERENCES)}")
    exe = build(name, archive)
    data = cfg.load(study or default_study(name))
    for k in ("btb", "ras", "indirect", "frontend", "memory", "mdp", "vp", "wrong_path"):
        data.pop(k, None)
    data["warmup_instructions"] = 0
    data.pop("simulation_instructions", None)
    rows = []
    with tempfile.TemporaryDirectory(prefix="rvw-csim-qualify-") as tmp:
        tmp = Path(tmp)
        for t in trace_paths:
            path, efmt, info = st.prepare(Path(t), fmt, tmp)
            if efmt != "csim":
                raise ValueError("qualification needs a text trace (csim, c2 or bt9); ChampSim input is unsupported")
            ref_out, our_out = tmp / "ref.pred", tmp / "our.pred"
            res = subprocess.run([str(exe), str(path), str(ref_out)], capture_output=True, text=True)
            if res.returncode:
                raise ValueError(f"reference run failed: {res.stderr.strip()}")
            run = json.loads(json.dumps(data))
            run.setdefault("report", {})["predictions_file"] = str(our_out)
            rep = st._engine(cfg.to_kv(run), path, "csim", None)
            ref, ours = _preds(ref_out), _preds(our_out)
            if ref.keys() != ours.keys():
                raise ValueError("reference and model saw different conditional branches")
            n = len(ref)
            agree = sum(ref[o][2] == ours[o][2] for o in ref)
            ref_miss = sum(r[1] != r[2] for r in ref.values())
            our_miss = sum(r[1] != r[2] for r in ours.values())
            instr = rep["trace"]["instructions"]
            per: dict[int, list[int]] = {}
            for o, (pc, taken, rp) in ref.items():
                v = per.setdefault(pc, [0, 0, 0, 0])
                v[0] += 1; v[1] += rp != taken; v[2] += ours[o][2] != taken; v[3] += rp != ours[o][2]
            worst = sorted(per.items(), key=lambda kv: -abs(kv[1][1] - kv[1][2]))[:top]
            ref_mpki, our_mpki = 1000 * ref_miss / instr, 1000 * our_miss / instr
            within = abs(our_mpki - ref_mpki) <= max(tolerance * ref_mpki, 0.05)
            rows.append({"trace": str(t), "sha256": st.traces.sha256(Path(t)), **info, "instructions": instr,
                         "conditional_branches": n, "reference_misses": ref_miss, "model_misses": our_miss,
                         "reference_mpki": ref_mpki, "model_mpki": our_mpki,
                         "mpki_ratio": our_mpki / ref_mpki if ref_mpki else None,
                         "prediction_agreement": agree / n if n else None, "within_tolerance": within,
                         "model_storage_kib": rep["branch"]["direction"]["storage"]["kib"],
                         "largest_differences": [{"pc": hex(pc), "executed": v[0], "reference_misses": v[1],
                                                  "model_misses": v[2], "disagreements": v[3]} for pc, v in worst]})
    ref = REFERENCES[name]
    return {"schema": "rvw.csim-qualify/1", "status": "reported", "reference": name, "reference_url": ref["url"],
            "reference_sha256": ref["sha256"], "reference_paper": ref["paper"],
            "reference_patch": {"replace": PATCH[0], "with": PATCH[1], "reason": "upstream out-of-bounds read in TAGE allocation"}, "study": data.get("name"),
            "study_sha256": cfg.digest(data), "engine": engine.identity(), "tolerance": tolerance,
            "training": "both models: immediate update, actual path, no warmup", "results": rows,
            "all_within_tolerance": all(r["within_tolerance"] for r in rows) if rows else None,
            "note": "MPKI tolerance is relative to the reference on these traces only. Different index hashing "
                    "makes per-branch agreement below 1 expected. This is not an RTL or bit-exact claim."}
