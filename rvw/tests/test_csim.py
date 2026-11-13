"""rvw csim: CLI, sweeps, in-process library and RTL event comparison (builds the engine)."""
import json

import pytest

from rvw.cli import main
from rvw.csim import rtl, study
from test_csim_formats import BEQ_8, c2


@pytest.fixture(autouse=True)
def cache(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("RVW_CSIM_CACHE", str(tmp_path_factory.getbasetemp() / "csim-cache"))


def trace_file(tmp_path, rows, n=None):
    last = max(int(r.split()[1]) for r in rows)
    p = tmp_path / 'trace.csim'
    p.write_text('rvw.csim-trace/1\n' + '\n'.join(rows) + f'\nEND {n or last}\n')
    return p


def alternating(tmp_path, n=400):
    return trace_file(tmp_path, [f'B {i + 1} 100 cond {i & 1} 80' for i in range(n)])


def test_cli_run_budget_models(tmp_path, capsys):
    s = tmp_path / 's.json'
    s.write_text(json.dumps({"schema": "rvw.csim-study/1", "name": "x", "branch": {"model": "gshare"}}))
    t = alternating(tmp_path)
    assert main(["csim", "run", str(s), str(t), "--set", "branch.history=4", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    r = out["results"][0]
    assert out["schema"] == "rvw.csim-study-report/1" and out["rtl_comparison"] == "inconclusive"
    assert r["input"]["sha256"] and r["branch"]["direction"]["model"] == "gshare"
    assert out["aggregate"]["weighting"].startswith("arithmetic mean")
    assert main(["csim", "budget", str(s), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["storage"]["direction"]["bits"] == 4096 * 2 + 12
    assert main(["csim", "models", "--json"]) == 0
    assert "tage-sc-l" in json.loads(capsys.readouterr().out)["branch"]["models"]
    assert main(["csim", "run", str(s), str(t), "--set", "branch.bogus=1", "--json"]) == 2
    assert "unknown configuration keys" in json.loads(capsys.readouterr().out)["error"]


def test_sweep_budget_and_pareto(tmp_path):
    t = alternating(tmp_path)
    s = {"branch": {"model": "bimodal"}}
    res = study.sweep(s, [t], {"branch.model": ["bimodal", "gshare", "tage"], "branch.entries": [1024, 4096]},
                      budget_kib=2, metric="direction_mpki", jobs=2)
    assert len(res["rows"]) == 6
    errors = [r for r in res["rows"] if "error" in r]
    assert len(errors) == 2 and all("branch.entries" in r["error"] for r in errors)  # tage has no entries knob
    res = study.sweep(s, [t], {"branch.model": ["bimodal", "gshare", "tage"]}, budget_kib=2, metric="direction_mpki")
    over = [r for r in res["rows"] if not r["within_budget"]]
    assert any(r["parameters"]["branch.model"] == "tage" for r in over)
    assert res["best"]["branch.model"] == "gshare"
    assert all(p["branch.model"] != "tage" for p in res["pareto"]["rows"])


def test_library_matches_engine(tmp_path):
    from rvw.csim.lib import Components
    import random
    rng = random.Random(2)
    rows = [(rng.randrange(64) * 4, rng.randrange(2)) for _ in range(2000)]
    t = trace_file(tmp_path, [f'B {i + 1} {pc:x} cond {tk} 0' for i, (pc, tk) in enumerate(rows)])
    s = {"branch": {"model": "tage-sc-l"}}
    want = study.run(s, [t])["results"][0]["branch"]["direction"]["misses"]
    misses = 0
    with Components(s) as c:
        for pc, tk in rows:
            ticket, pred = c.predict(pc)
            c.history(pc, "cond", tk, 0)
            c.update(ticket, tk)
            misses += pred != tk
        assert c.stats()["direction"]["model"] == "tage-sc-l"
    assert misses == want
    with Components({"memory": {"l1d": {"size_kib": 1, "ways": 16, "latency": 4}, "dram_latency": 100}}) as c:
        assert c.access(0, 0, 0x1000) == 104
        assert c.access(200, 0, 0x1000) == 204
    with pytest.raises(ValueError, match="not available in-process"):
        Components({"frontend": {"fetch_width": 4}})


def c2_branches(tmp_path, outcomes, elf="ab" * 32):
    rows = []
    pc = 0x1000
    for t in outcomes:
        rows.append((pc, pc + 8 if t else pc + 4, BEQ_8, 0, {}))
        pc = pc + 8 if t else pc + 4
    header = {"schema": "rvw.rvfi/1", "xlen": 64, "core": "x", "elf": "a.elf", "elf_sha256": elf}
    return c2(tmp_path, rows, header), rows


def bp_events(tmp_path, rows, flip=(), drop=(), elf="ab" * 32, semantics="first-prediction"):
    p = tmp_path / 'events.jsonl'
    head = {"schema": "rvw.bp-events/1", "elf_sha256": elf, "hart": 0, "counter_semantics": semantics,
            "roi": {"start_order": 0}}
    lines = [json.dumps({k: v for k, v in head.items() if v is not None})]
    for i, (pc, nxt, _, _, _) in enumerate(rows):
        if i in drop:
            continue
        taken = nxt == pc + 8
        pred = taken != (i in flip)
        lines.append(json.dumps({"order": i, "pc": hex(pc), "kind": "cond", "taken": taken, "predicted_taken": pred}))
    p.write_text('\n'.join(lines) + '\n')
    return p


def test_rtl_compare_detects_injected_mismatch(tmp_path):
    trace, rows = c2_branches(tmp_path, [1, 0, 1, 1, 0, 0, 1, 0] * 20)
    s = {"branch": {"model": "perfect"}}
    same = rtl.compare(s, trace, bp_events(tmp_path, rows))
    assert same["status"] == "compared" and same["observed"]["direction"]["agreement"] == 1
    diff = rtl.compare(s, trace, bp_events(tmp_path, rows, flip={17}))
    d = diff["observed"]["direction"]
    assert diff["status"] == "compared" and d["disagree"] == 1 and d["rtl_misses"] == 1 and d["model_misses"] == 0
    assert diff["per_branch"][0]["direction_disagreements"] == 1


@pytest.mark.parametrize("kw,reason", [
    (dict(elf=None), "missing ELF identity"), (dict(elf="cd" * 32), "differs"),
    (dict(drop={3}), "no RTL direction event"), (dict(semantics=None), "counter semantics"),
])
def test_rtl_compare_inconclusive(tmp_path, kw, reason):
    trace, rows = c2_branches(tmp_path, [1, 0] * 10)
    res = rtl.compare({"branch": {"model": "bimodal"}}, trace, bp_events(tmp_path, rows, **kw))
    assert res["status"] == "inconclusive" and any(reason in r for r in res["reasons"])


def test_rtl_compare_kanata_observed_events(tmp_path):
    trace, rows = c2_branches(tmp_path, [1, 0, 1, 0])
    log = ["Kanata\t0004", "C=\t0"]
    for i, (pc, nxt, _, _, _) in enumerate(rows):
        taken = "taken" if nxt == pc + 8 else "not_taken"
        log += [f"I\t{i}\t{i}\t0", f"L\t{i}\t0\t{pc:x}: beq", "C\t1",
                f"#rvw\t1\tprediction\t{i}\tbpd\tdirection\t{taken}\t{taken}\t?\t?\t?\t?\t?", f"R\t{i}\t{i}\t0"]
    k = tmp_path / 'k.log'
    k.write_text('\n'.join(log) + '\n')
    res = rtl.compare({"branch": {"model": "perfect"}}, trace, k, elf_sha256="ab" * 32)
    assert res["event_source"] == "kanata" and res["observed"]["direction"]["events"] == 4
    assert any("counter semantics" in r for r in res["reasons"]) and res["status"] == "inconclusive"
    assert res["inferred"]["basis"].startswith("committed instruction")


STAND_IN = r"""
#pragma once
#include "utils.h"
#include "bt9.h"
// Stand-in reference for the test: a 2-bit bimodal "PREDICTOR" with the CBP 2016 interface.
class PREDICTOR {
    unsigned char t[4096];
 public:
    PREDICTOR() { for (auto& x : t) x = 1; }
    bool GetPrediction(UINT64 pc) { return t[(pc >> 1) & 4095] >= 2; }
    void UpdatePredictor(UINT64 pc, OpType, bool taken, bool, UINT64) {
        unsigned char& c = t[(pc >> 1) & 4095]; if (taken) { if (c < 3) ++c; } else if (c) --c; }
    void TrackOtherInst(UINT64, OpType, bool, UINT64) {}
};
"""


def test_qualify_against_stand_in_reference(tmp_path, monkeypatch):
    import hashlib
    import io
    import tarfile
    from rvw.csim import qualify
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = STAND_IN.encode()
        info = tarfile.TarInfo("ref/bim/predictor.h"); info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    archive = tmp_path / "ref.tar.gz"; archive.write_bytes(buf.getvalue())
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    study_file = tmp_path / "bim.json"; study_file.write_text(json.dumps({"name": "bim", "branch": {"model": "bimodal"}}))
    monkeypatch.setitem(qualify.REFERENCES, "test-bimodal", {"url": "file:///nonexistent", "sha256": sha, "dir": "ref/bim",
                                                             "study": str(study_file), "paper": "test"})
    import random
    rng = random.Random(1)
    t = trace_file(tmp_path, [f'B {i + 1} {rng.randrange(32) * 4:x} cond {rng.randrange(2)} 0' for i in range(3000)])
    res = qualify.qualify("test-bimodal", [t], study=study_file, archive=archive)
    r = res["results"][0]
    assert r["prediction_agreement"] == 1 and r["reference_misses"] == r["model_misses"] and r["within_tolerance"]
    assert res["all_within_tolerance"] is True and res["reference_patch"]["with"].startswith("if (i <= NHIST")
    bad = tmp_path / "bad.tar.gz"; bad.write_bytes(b"x")
    monkeypatch.setitem(qualify.REFERENCES, "test-bad", {**qualify.REFERENCES["test-bimodal"], "sha256": "0" * 64})
    with pytest.raises(ValueError, match="does not match the pinned"):
        qualify.qualify("test-bad", [t], study=study_file, archive=bad)
