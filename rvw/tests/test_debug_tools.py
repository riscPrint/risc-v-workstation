"""bundle / reduce / bisect against tests/fake_adapter.py (no real core needed)."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from rvw.common.riscv import classify
from rvw.bundle.make import Options as BOpts, make
from rvw.bundle.trace import loop_info
from rvw.bisect.core import Bisector, Options as XOpts
from rvw.reduce.core import Options as ROpts, Reducer
from rvw.runs import signature
from rvw.runs.adapter import parse_replay

FAKE = str(Path(__file__).parent / "fake_debug_adapter.py")
CFG = """
[core]
name = "fake"
period = 10
source_env = "FAKE_CORE"
[failure]
units = { 'lsu\\.scala' = "LSU" }
[[snapshot]]
name = "Counter"
unit = "LSU"
scope = 'TOP\\.Fake\\.'
values = { count = 'count', busy = 'busy' }
"""


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("RVW_NO_LOCK", "1")
    cfg = tmp_path / "debug.toml"
    cfg.write_text(CFG)
    monkeypatch.setenv("RVW_CORE_CONFIG", str(cfg))


def fake_run(out, *args, env=None):
    subprocess.run([sys.executable, FAKE, "run", "--elf", SYMS_ELF, "--out", str(out), *args],
                   check=True, env={**os.environ, **(env or {})})
    return out


def test_signature():
    assert signature({"status": "assert", "message": "x (lsu.scala:1241) y"}) == "assert:lsu.scala:1241"
    assert signature({"status": "fail", "fail_code": 3}) == "fail:3"
    assert signature({"status": "timeout"}) == "timeout"
    assert signature({"status": "pass"}) == "pass"


def test_parse_replay():
    c = parse_replay("SPINAL_BOOM=/x RiscvSim/boom/run.sh run --elf a.elf --seed 3 --wave --out d")
    assert c.env == {"SPINAL_BOOM": "/x"} and c.sub == "run"
    assert c.get("seed") == "3" and c.get("wave") is True
    c2 = c.set(seed=None, max_cycles=10, wave=False)
    assert "--seed" not in c2.argv() and "--wave" not in c2.argv() and c2.get("max_cycles") == "10"


def test_classify_and_loop():
    assert classify(0x00053503) == "load"      # ld a0,0(a0)
    assert classify(0x00a53023) == "store"     # sd a0,0(a0)
    assert classify(0x4108) == "load"          # c.lw
    assert classify(0x02b50533) == "muldiv"    # mul
    rs = [{"pc": hex(0x100 + 4 * (i % 3))} for i in range(30)]
    assert loop_info(rs)["distinct_pcs"] == 3


def test_bundle_reruns_for_wave(tmp_path):
    run = fake_run(tmp_path / "r", "--seed", "9")          # asserts at 2271, no wave, no trace
    S = make(str(run), BOpts(out=tmp_path / "b", rerun_window=300, cut_cycles=50))
    assert S["signature"] == "assert:lsu.scala:1241"
    assert S["rerun"]["reproduced"] is True
    assert S["suspect"]["unit"] == "LSU"
    snap = {g["name"]: g for g in S["snapshot"]}
    assert snap["Counter"]["values"]["count"] == hex(2271)
    assert S["wave"]["to"] - S["wave"]["from"] == 50 * 10 and S["wave"]["snapshot_cycle"] == 2271
    assert S["progress"]["last_cycle"] <= 2271
    for f in ("summary.md", "summary.json", "retired.txt", "wave-window.vcd", "replay.sh"):
        assert (tmp_path / "b" / f).exists(), f
    md = (tmp_path / "b" / "summary.md").read_text()
    assert "Suspected unit**: LSU" in md and "lsu.scala:1241" in md
    # replay.sh reproduces the failure
    subprocess.run(["bash", str(tmp_path / "b" / "replay.sh"), str(tmp_path / "rep")], check=True,
                   env={**os.environ})
    assert json.loads((tmp_path / "rep" / "result.json").read_text())["status"] == "assert"


def test_reduce(tmp_path):
    run = fake_run(tmp_path / "r", "--seed", "9")
    r = Reducer(str(run), ROpts(out=tmp_path / "red", seeds=6, latencies=[1, 20])).reduce()
    assert r["best"]["cycles"] == 700 and r["best"]["mem_latency"] == 1
    assert r["best"]["max_cycles"] == "800"
    assert (tmp_path / "red" / "reduce.md").exists()


def test_bisect(tmp_path):
    repo = tmp_path / "core"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    g("init", "-q")
    for i in range(1, 9):
        (repo / "f").write_text(str(i))
        if i >= 5:
            (repo / "bug").write_text("")
        g("add", "-A")
        g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", f"change {i}")
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    r = Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=tmp_path / "bis")).bisect()
    assert r["result"]["commit"].endswith("change 5")
    # the original checkout did not move
    assert subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout == head


def test_pdg_digest(tmp_path):
    from rvw.bundle.pdgdigest import digest
    v = lambda f, l, n, t: {"file": f, "line": l, "name": n, "timestamp": t, "sim_data": "1", "module_path": ["m"]}
    d = {"vertices": [v("a.scala", 1, "root", 5), v("a.scala", 2, "x", 4), v("b.scala", 3, "y", 3), v("a.scala", 2, "x", 3)],
         "edges": [{"from": 0, "to": 1, "kind": "Data"}, {"from": 1, "to": 2, "kind": "Conditional"},
                   {"from": 1, "to": 3, "kind": "Data"}]}
    p = tmp_path / "d.json"
    p.write_text(json.dumps(d))
    rows = digest(str(p))
    assert [(r["where"], r["depth"], r["via"]) for r in rows] == [("a.scala:1", 0, "root"), ("a.scala:2", 1, "data"),
                                                                  ("b.scala:3", 2, "conditional")]
    assert rows[1]["hits"] == 2 and rows[1]["t"] == -1


def test_signature_adapter_location_format():
    # RiscvSim/boom prints Scala locations as File.scala:Lnnn
    assert signature({"status": "assert", "message": "FAILURE lsu:L1241 (lsu.scala:L1241)"}) == "assert:lsu.scala:1241"


# --- rvw reduce: review findings ------------------------------------------------------------

SYMS_ELF = str(Path(__file__).parent / "data" / "reduce_symbols.elf")


def test_reduce_refuses_a_timeout_that_is_not_a_hang(tmp_path):
    # Review (O): a run that would pass at 8000, cut at 5000, "reproduced" in 6/7 trials.
    run = fake_run(tmp_path / "r", "--seed", "1", "--max-cycles", "5000", "--rvfi-trace")
    with pytest.raises(ValueError, match="not a hang"):
        Reducer(str(run), ROpts(out=tmp_path / "red", hang_cycles=500, seeds=4, latencies=[5, 20]))


def test_reduce_never_counts_a_capped_timeout(tmp_path):
    # Same run without an RVFI trace: the original can't be judged, so every trial asks for one,
    # and none shows a hang (the program keeps retiring until the cap).
    run = fake_run(tmp_path / "r", "--seed", "1", "--max-cycles", "5000")
    r = Reducer(str(run), ROpts(out=tmp_path / "red", hang_cycles=500, seeds=3, latencies=[5])).reduce()
    assert r["trials"] and not any(t["match"] for t in r["trials"]) and r["reproduced"] is False
    assert all("--rvfi-trace" in json.loads((Path(t["dir"]) / "result.json").read_text())["replay"] or
               (Path(t["dir"]) / "rvfi.jsonl").exists() for t in r["trials"])
    assert "No trial reproduced" in (tmp_path / "red" / "reduce.md").read_text()


def test_reduce_finds_a_real_hang(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_HANG", "3000")
    run = fake_run(tmp_path / "r", "--seed", "1", "--max-cycles", "9000", "--rvfi-trace")
    r = Reducer(str(run), ROpts(out=tmp_path / "red", modes=["cycles"], hang_cycles=1000)).reduce()
    assert r["reproduced"] and r["trials"][0]["match"] and "before the end" in r["trials"][0]["hang"]
    assert int(r["best"]["max_cycles"]) <= 3000 + 1000 + 100


def test_reduce_cli_exit_codes(tmp_path, rvw_cli):
    run = fake_run(tmp_path / "r", "--seed", "9")
    # signature that the original does not have: bad input
    assert rvw_cli("reduce", run, "--out", tmp_path / "a", "--signature", "assert:nothing.scala:1",
                   "--modes", "cycles") == 2
    # nothing reproduces: 1 (the timeout case above, through the CLI)
    to = fake_run(tmp_path / "t", "--seed", "1", "--max-cycles", "5000")
    assert rvw_cli("reduce", to, "--out", tmp_path / "b", "--modes", "cycles,latency", "--latencies", "5",
                   "--hang-cycles", "500") == 1
    assert rvw_cli("reduce", run, "--out", tmp_path / "c", "--modes", "cycles") == 0


def test_reduce_symbol_returns_the_minimum_failing_elf(tmp_path, monkeypatch):
    # Review (S): the reported minimum was 1 but the returned ELF had 50; 0 was never tried.
    from rvw.runs.elf import Elf
    monkeypatch.setenv("FAKE_SYMBOL", "limit>=7")
    run = fake_run_elf(tmp_path / "r", SYMS_ELF, "--seed", "9")
    r = Reducer(str(run), ROpts(out=tmp_path / "red", modes=["symbols"], symbols=["limit"])).reduce()
    assert r["symbols"]["limit"]["smallest_failing"] == 7 and r["reproduced"]
    assert Elf(r["best"]["elf"]).read_int("limit") == 7
    monkeypatch.setenv("FAKE_SYMBOL", "limit>=0")
    r = Reducer(str(run), ROpts(out=tmp_path / "red0", modes=["symbols"], symbols=["limit"])).reduce()
    assert r["symbols"]["limit"]["smallest_failing"] == 0 and Elf(r["best"]["elf"]).read_int("limit") == 0


def test_reduce_symbol_uses_the_element_size(tmp_path, monkeypatch):
    # `table` is unsigned int[4] (16 bytes): never read it as one 16-byte integer.
    monkeypatch.setenv("FAKE_SYMBOL", "limit>=0")
    run = fake_run_elf(tmp_path / "r", SYMS_ELF, "--seed", "9")
    r = Reducer(str(run), ROpts(out=tmp_path / "red", modes=["symbols"], symbols=["table"], budget=3)).reduce()
    assert "table" not in r["symbols"] and not r["trials"]
    r = Reducer(str(run), ROpts(out=tmp_path / "red2", modes=["symbols"], symbols=["table:4"], budget=3)).reduce()
    assert r["symbols"]["table"]["original"] == 7 and r["symbols"]["table"]["bytes"] == 4


def fake_run_elf(out, elf, *args):
    subprocess.run([sys.executable, FAKE, "run", "--elf", elf, "--out", str(out), *args], check=True)
    return out


@pytest.fixture
def rvw_cli():
    def call(*args):
        return subprocess.run([sys.executable, "-m", "rvw", *map(str, args)], capture_output=True,
                              text=True, env={**os.environ}).returncode
    return call


# --- rvw bisect: review findings ------------------------------------------------------------

def make_core(tmp_path, n=8, bug_from=5):
    repo = tmp_path / "core"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True).stdout.strip()
    g("init", "-q")
    for i in range(1, n + 1):
        (repo / "f").write_text(str(i))
        if i >= bug_from:
            (repo / "bug").write_text("")
        g("add", "-A")
        g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", f"change {i}")
    return repo, g


def test_bisect_refuses_a_workdir_whose_clone_is_a_link_to_the_source(tmp_path):
    # Review (O+S, /tmp/review-debug-sol/bisect-probe.log): a pre-existing work dir whose `core`
    # links to the source checkout was used as the "private clone": checkout --force moved the
    # source HEAD and discarded uncommitted work.
    repo, g = make_core(tmp_path)
    head = g("rev-parse", "HEAD")
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    (unsafe / "core").symlink_to(repo, target_is_directory=True)
    (repo / "f").write_text("uncommitted work")
    with pytest.raises(ValueError, match="not an rvw bisect workspace"):
        Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=unsafe)).bisect()
    # Even with a forged marker the link is refused before any git command runs on it.
    (unsafe / ".rvw-bisect.json").write_text(json.dumps({"origin": str(repo.resolve())}))
    with pytest.raises(ValueError, match="not a private clone"):
        Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=unsafe)).bisect()
    assert g("rev-parse", "HEAD") == head and (repo / "f").read_text() == "uncommitted work"


def test_bisect_refuses_a_linked_or_foreign_workdir(tmp_path):
    repo, _ = make_core(tmp_path)
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    real = tmp_path / "real"
    real.mkdir()
    (tmp_path / "link").symlink_to(real)
    with pytest.raises(ValueError, match="symbolic link"):
        Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=tmp_path / "link")).bisect()
    other = tmp_path / "other"
    other.mkdir()
    (other / ".rvw-bisect.json").write_text(json.dumps({"origin": "/somewhere/else"}))
    with pytest.raises(ValueError, match="belongs to a bisect of"):
        Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=other)).bisect()
    # A plain directory inside another repository is not a clone either
    nested = tmp_path / "nested"
    (nested / "core").mkdir(parents=True)
    (nested / ".rvw-bisect.json").write_text(json.dumps({"origin": str(repo.resolve())}))
    with pytest.raises(ValueError, match="not a private clone"):
        Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=nested)).bisect()


def test_bisect_default_workspaces_are_unique_and_locked(tmp_path, monkeypatch):
    # Review (O+S): same-second bisects shared ~/.cache/rvw/bisect/<core>-<time>.
    repo, _ = make_core(tmp_path)
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr("rvw.bisect.core.time.time", lambda: 123456.0)
    a = Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo)))
    b = Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo)))
    a._workspace()
    b._workspace()
    assert a.base != b.base and a.base.parent == b.base.parent
    c = Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=a.base))
    with pytest.raises(ValueError, match="in use by another"):
        c._workspace()


def test_bisect_remove_clone_only_deletes_its_own(tmp_path):
    repo, _ = make_core(tmp_path)
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    work = tmp_path / "bis"
    r = Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=work)).bisect()
    assert r["result"]["commit"].endswith("change 5") and (work / "core" / ".git").is_dir()
    r = Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=work, keep=False)).bisect()
    assert r["result"]["clone_removed"] is False and (work / "core" / ".git").is_dir()
    w2 = tmp_path / "bis2"
    r = Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=w2, keep=False)).bisect()
    assert r["result"]["clone_removed"] is True and not (w2 / "core").exists()
    assert repo.exists() and (repo / ".git").is_dir()


def test_bisect_a_reduced_run(tmp_path, monkeypatch):
    # Review (O): bisecting `rvw reduce`'s best run kept the reduced max cycles, so the good
    # endpoint timed out instead of passing.
    repo, _ = make_core(tmp_path)
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    monkeypatch.setenv("FAKE_CORE", str(repo))
    red = Reducer(str(run), ROpts(out=tmp_path / "red", modes=["cycles"])).reduce()
    assert int(red["best"]["max_cycles"]) == 2371
    bi = Bisector(red["best"]["dir"], XOpts(good="HEAD~7", core_repo=str(repo), workdir=tmp_path / "bis")).bisect()
    assert bi["result"].get("commit", "").endswith("change 5"), bi["result"]
    assert bi["max_cycles"] == 200000 and "unreduced" in bi["max_cycles_from"]
    # A tight run that is not a reduce trial: the good endpoint times out, and the error says why
    tight = fake_run(tmp_path / "t", "--seed", "9", "--max-cycles", "2300", env={"FAKE_CORE": str(repo)})
    bi = Bisector(str(tight), XOpts(good="HEAD~7", core_repo=str(repo), workdir=tmp_path / "bis2")).bisect()
    assert "--max-cycles" in bi["result"]["error"] and not bi["result"].get("first_bad")
    bi = Bisector(str(tight), XOpts(good="HEAD~7", core_repo=str(repo), workdir=tmp_path / "bis3",
                                    max_cycles=10000)).bisect()
    assert bi["result"].get("commit", "").endswith("change 5")


# --- rvw bundle: review findings ------------------------------------------------------------

def test_bundle_rejects_a_wave_that_ends_before_the_failure(tmp_path, monkeypatch):
    # Review (S, /tmp/review-debug-sol/wave-probes.log): a wave window ending at cycle 2261, with
    # BOOM-like reset offset, was accepted for a failure at 2271 and labelled cycle 2277.
    monkeypatch.setenv("FAKE_WAVE_T1", "170")
    run = fake_run(tmp_path / "r", "--seed", "9", "--wave", "--wave-from", "2200", "--wave-to", "2261",
                   "--rvfi-trace")
    S = make(str(run), BOpts(out=tmp_path / "b", rerun_window=300, cut_cycles=50, spinaltrace=False))
    assert "rerun" in S and S["rerun"]["reproduced"]
    assert S["wave"]["covers_failure"] and S["wave"]["snapshot_cycle"] == 2271
    assert {g["name"]: g for g in S["snapshot"]}["Counter"]["values"]["count"] == hex(2271)
    S = make(str(run), BOpts(out=tmp_path / "b2", rerun=False, cut_cycles=50, spinaltrace=False))
    assert not S["wave"]["covers_failure"] and S["wave"]["snapshot_cycle"] == 2261
    assert any("does not cover" in n for n in S["notes"])
    assert "does not reach the failure" in (tmp_path / "b2" / "summary.md").read_text()


def test_bundle_does_not_trust_a_wave_without_a_cycle_mapping(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_NO_DETAILS", "1")
    run = fake_run(tmp_path / "r", "--seed", "9", "--wave", "--rvfi-trace")
    S = make(str(run), BOpts(out=tmp_path / "b", rerun=False, cut_cycles=50, spinaltrace=False))
    assert S["clock"]["known"] is False and not S["wave"]["covers_failure"]
    assert any("time of cycle 1 is unknown" in n for n in S["notes"])


def test_bundle_measures_the_rvfi_skew(tmp_path, monkeypatch):
    # Review (O): RVFI stamps are 2 cycles after the wave's ROB commit on BOOM; say so.
    monkeypatch.setenv("FAKE_COMMIT_SKEW", "2")
    monkeypatch.setenv("FAKE_WAVE_T1", "170")
    cfg = tmp_path / "skew.toml"
    cfg.write_text(CFG.replace('source_env = "FAKE_CORE"', 'source_env = "FAKE_CORE"\ncommit = \'TOP\\.Fake\\.commit$\''))
    monkeypatch.setenv("RVW_CORE_CONFIG", str(cfg))
    run = fake_run(tmp_path / "r", "--seed", "9", "--wave", "--wave-from", "2000", "--rvfi-trace")
    S = make(str(run), BOpts(out=tmp_path / "b", cut_cycles=200, spinaltrace=False))
    sk = S["rvfi_skew"]
    assert sk["rvfi_minus_wave_commit"] == 2 and sk["last_rvfi_cycle"] - sk["last_wave_commit_cycle"] == 2
    assert "2 cycle(s) after" in (tmp_path / "b" / "summary.md").read_text()


def test_replay_sh_substitutes_only_the_out_value(tmp_path):
    # Review (O, make.py:371): every "OUT" substring was replaced (ELF /x/LAYOUT_test.elf broke).
    from rvw.bundle.make import _write_replay
    from rvw.runs import adapter, open_run
    elf_dir = tmp_path / "LAYOUT dir"
    elf_dir.mkdir()
    elf = elf_dir / "OUTPUT_test.elf"
    elf.write_text("")
    run = open_run(fake_run(tmp_path / "r", "--seed", "9", "--elf", str(elf)))
    _write_replay(tmp_path / "replay.sh", adapter.command_for(run), run)
    text = (tmp_path / "replay.sh").read_text()
    assert "OUTPUT_test.elf" in text and '--out "$out"' in text
    subprocess.run(["bash", str(tmp_path / "replay.sh"), str(tmp_path / "rep")], check=True, capture_output=True)
    assert json.loads((tmp_path / "rep" / "result.json").read_text())["elf"] == str(elf)


HS_VCD = """$timescale 1ps $end
$scope module TOP $end
$var wire 1 ! clk $end
$var wire 1 a a_valid $end
$var wire 1 b a_ready $end
$var wire 4 c a_source $end
$var wire 3 d a_opcode $end
$var wire 1 e c_valid $end
$var wire 1 f c_ready $end
$var wire 4 g c_source $end
$var wire 3 h c_opcode $end
$var wire 1 i d_valid $end
$var wire 1 j d_ready $end
$var wire 4 k d_source $end
$var wire 3 l d_opcode $end
$upscope $end
$enddefinitions $end
#0
0!
0a
1b
b0 c
b0 d
0e
1f
b0 g
b0 h
0i
1j
b0 k
b0 l
#5
1!
#10
0!
1a
b11 c
b100 d
#15
1!
#20
0!
0a
1e
b11 g
b110 h
#25
1!
#30
0!
0e
1i
b11 k
b110 l
#35
1!
#40
0!
0i
#45
1!
"""


def test_handshakes_match_responses_by_opcode(tmp_path):
    # Review (O, handshakes.py:68): a D ReleaseAck (source 3) closed the open A Get (source 3).
    from rvw.bundle import handshakes
    w = tmp_path / "hs.vcd"
    w.write_text(HS_VCD)
    ch = {n: {"valid": f"{n}_valid", "ready": f"{n}_ready", "id": f"{n}_source", "opcode": f"{n}_opcode"}
          for n in ("a", "c", "d")}
    cfg = {"scope": r"^TOP\.", "clock": "clk", "requests": ["a", "c"], "responses": ["d"], "channels": ch,
           "opens": {"c": [6, 7]}, "closes": {"d": {"a": [0, 1, 2, 4, 5], "c": [6]}}}
    h = handshakes.analyze(cfg, str(w), None, 10)
    assert [(r["channel"], r["id"], r["opcode"]) for r in h["open_requests"]] == [("a", "0x3", 4)]
    assert h["channels"]["d"]["fires"] == 1


def test_pdg_digest_is_independent_of_file_order(tmp_path):
    import random
    from rvw.bundle.pdgdigest import digest
    v = lambda f, l, n, t: {"file": f, "line": l, "name": n, "timestamp": t, "sim_data": "1", "module_path": ["m"]}
    vs = [v("a.scala", 1, "root", 5), v("b.scala", 2, "x", 4), v("c.scala", 3, "y", 4), v("d.scala", 4, "z", 3)]
    es = [(0, 1, "Data"), (0, 2, "Conditional"), (1, 3, "Data"), (2, 3, "Index")]
    outs = set()
    for seed in range(6):
        rnd = random.Random(seed)
        perm = list(range(len(vs)))
        rnd.shuffle(perm)
        inv = {old: new for new, old in enumerate(perm)}
        d = {"vertices": [vs[i] for i in perm],
             "edges": [{"from": inv[a], "to": inv[b], "kind": k} for a, b, k in rnd.sample(es, len(es))]}
        p = tmp_path / f"d{seed}.json"
        p.write_text(json.dumps(d))
        outs.add(json.dumps(digest(str(p))))
    assert len(outs) == 1


def test_konata_inflight_reads_gzip_without_core_labels(tmp_path):
    import gzip
    from rvw.bundle.trace import konata_inflight
    log = "Kanata\t0004\nC=\t100\nI\t0\t0\t0\nL\t0\t0\t80000000: addi\nL\t0\t1\tidx=7\nS\t0\t0\tF\n" \
          "I\t1\t1\t0\nL\t1\t0\t80000004: ld\nS\t1\t0\tF\nC\t2\nS\t0\t0\tEx\nR\t0\t0\t0\nC\t3\nS\t1\t0\tIs\n" \
          "I\t2\t2\t0\nL\t2\t0\t80000008: sd\nL\t2\t1\trob=3\nC\t1\n"
    p = tmp_path / "k.log.gz"
    with gzip.open(p, "wt") as f:
        f.write(log)
    inflight, end = konata_inflight(str(p))
    assert end == 106 and [(u.id, u.stage, u.since) for u in inflight] == [("1", "Is", 105), ("2", "", 105)]
    assert inflight[0].label == "80000004: ld" and inflight[1].detail == "rob=3" and inflight[1].label == "80000008: sd"


# --- round-2 review findings (/tmp/review2-debug) -------------------------------------------

def test_reduce_refuses_a_wall_clock_timeout(tmp_path, monkeypatch, rvw_cli):
    # Review 2 N1 (probe_wall.py): an original wall-clock timeout was reduced, and every trial that
    # also ran out of wall clock "reproduced" it.
    monkeypatch.setenv("FAKE_WALL_CLOCK", "1")
    run = fake_run(tmp_path / "r", "--seed", "1", "--rvfi-trace")
    assert signature(json.loads((run / "result.json").read_text())) == "timeout:wall-clock"
    for sig in (None, "re:timeout"):
        with pytest.raises(ValueError, match="wall-clock"):
            Reducer(str(run), ROpts(out=tmp_path / "red", signature=sig, modes=["cycles"]))
    assert rvw_cli("reduce", run, "--out", tmp_path / "c", "--modes", "cycles") == 2


def test_reduce_never_matches_a_wall_clock_trial(tmp_path, monkeypatch):
    run = fake_run(tmp_path / "r", "--seed", "9")                  # a real assertion
    monkeypatch.setenv("FAKE_WALL_CLOCK", "1")                      # ... but every trial runs out of time
    r = Reducer(str(run), ROpts(out=tmp_path / "red", signature="re:.", modes=["cycles", "latency"],
                                latencies=[5])).reduce()
    assert r["trials"] and all(t["signature"] == "timeout:wall-clock" for t in r["trials"])
    assert not any(t["match"] for t in r["trials"]) and r["reproduced"] is False


def test_bisect_skips_wall_clock_timeouts_whatever_other_says(tmp_path):
    repo, g = make_core(tmp_path)                                   # bug from change 5
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    # Changes 3 and 4 are "slow": their runs end in a wall-clock timeout. Rewrite them in place.
    g("checkout", "-q", "-b", "slow", "HEAD~6")                     # change 2
    for i in range(3, 9):
        (repo / "f").write_text(str(i))
        if i in (3, 4):
            (repo / "slow").write_text("")
        elif (repo / "slow").exists():
            (repo / "slow").unlink()
        if i >= 5:
            (repo / "bug").write_text("")
        g("add", "-A")
        g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", f"change {i}")
    for other in ("bad", "good"):
        r = Bisector(str(run), XOpts(good="HEAD~7", bad="HEAD", core_repo=str(repo), other=other,
                                     signature="re:assert|timeout", workdir=tmp_path / f"bis-{other}")).bisect()
        steps = [s for s in r["steps"] if s["signature"] == "timeout:wall-clock"]
        assert steps and all(s["verdict"] == "skip" for s in steps), r["steps"]
        res = r["result"]
        assert res.get("commit", "").endswith("change 5") or set(res.get("ambiguous", [])) >= {
            g("rev-parse", "HEAD~3")}, res
        assert not res.get("commit", "").endswith(("change 3", "change 4")), res


def test_bisect_refuses_a_wall_clock_signature(tmp_path, monkeypatch):
    repo, _ = make_core(tmp_path)
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo), "FAKE_WALL_CLOCK": "1"})
    with pytest.raises(ValueError, match="wall-clock"):
        Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=tmp_path / "bis"))


def test_bisect_max_cycles_help_says_what_the_code_does():
    # Review 2 N2: the help promised "at least twice the failure cycle", which the code never did.
    h = subprocess.run([sys.executable, "-m", "rvw", "bisect", "--help"], capture_output=True, text=True,
                       env={**os.environ, "COLUMNS": "400"}).stdout
    line = " ".join(h.split("--max-cycles", 2)[2].split("--hang-cycles")[0].split())
    assert "twice" not in line and "the run's own" in line and "reduce" in line, line


def test_wave_covers_the_failure_only_with_its_edge(tmp_path):
    # Review 2 N3: covers() has no slack. Pinned on purpose: BOOM's wave ends exactly at the failing
    # cycle's edge (cycle 125, time of cycle 1 = 170, period 10: wave end 1410, /tmp/review2-debug/
    # boom-fail). A wave that ends even one unit earlier lacks that edge, and its last values are
    # the cycle before the failure, so it must not count as covering it.
    from rvw.bundle.clock import WaveClock, covers
    clk = WaveClock(10, 170, True, "test")
    run = {"details": {"wave_time_per_cycle": 10, "wave_time_of_cycle_1": 170}}
    def wave(end):
        p = tmp_path / f"w{end}.vcd"
        p.write_text("$timescale 1ps $end\n$scope module TOP $end\n$var wire 1 ! clk $end\n$upscope $end\n"
                     f"$enddefinitions $end\n#0\n0!\n#{end - 5}\n0!\n#{end}\n1!\n")
        return p
    assert clk.time(125) == 1410
    assert covers(run, wave(1410), 125, clk)[0] is True
    assert covers(run, wave(1415), 125, clk)[0] is True
    ok, why = covers(run, wave(1409), 125, clk)
    assert ok is False and "before the failure" in why
    assert covers(run, wave(1401), 125, clk)[0] is False


def test_bundle_wave_window_starting_in_reset_has_no_negative_cycle(tmp_path, monkeypatch):
    # Review 2 N4: with BOOM's reset offset a cut from time 0 said from_cycle -16.
    monkeypatch.setenv("FAKE_WAVE_T1", "170")
    run = fake_run(tmp_path / "r", "--seed", "9", "--wave")          # asserts at 2271
    S = make(str(run), BOpts(out=tmp_path / "b", cut_cycles=3000, rerun=False))
    w = S["wave"]
    assert w["from"] == 0 and w["from_cycle"] == 1 and w["from_reset"] is True
    S = make(str(run), BOpts(out=tmp_path / "b2", cut_cycles=50, rerun=False))
    assert S["wave"]["from_cycle"] == 2271 - 50 and S["wave"]["from_reset"] is False


# Round 3: the C1 `inconclusive` field (unattributed or pending concurrent failures) must never count
# as a reproduction, a bisect verdict or a trusted original run.

def test_reduce_never_matches_an_inconclusive_trial(tmp_path, monkeypatch):
    run = fake_run(tmp_path / "r", "--seed", "9")                  # a real, attributed assertion
    monkeypatch.setenv("FAKE_INCONCLUSIVE", "1")                    # every trial's failure is unattributed
    r = Reducer(str(run), ROpts(out=tmp_path / "red", modes=["cycles", "latency"], latencies=[5])).reduce()
    assert r["trials"] and not any(t["match"] for t in r["trials"]) and r["reproduced"] is False


def test_reduce_and_bisect_refuse_an_inconclusive_original_run(tmp_path):
    repo, _ = make_core(tmp_path)
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo), "FAKE_INCONCLUSIVE": "1"})
    with pytest.raises(ValueError, match="inconclusive"):
        Reducer(str(run), ROpts(out=tmp_path / "red"))
    with pytest.raises(ValueError, match="inconclusive"):
        Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=tmp_path / "bis"))


def test_bisect_skips_inconclusive_steps(tmp_path, monkeypatch):
    repo, g = make_core(tmp_path)                                   # bug from change 5
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    monkeypatch.setenv("FAKE_INCONCLUSIVE", "1")                    # every failing step is unattributed
    r = Bisector(str(run), XOpts(good="HEAD~7", bad="HEAD", core_repo=str(repo), other="bad",
                                 workdir=tmp_path / "bis")).bisect()
    failing = [s for s in r["steps"] if s["signature"] != "pass"]
    assert failing and all(s["verdict"] == "skip" for s in failing), r["steps"]
    assert not r["result"].get("commit", "").endswith("change 5") or r["result"].get("ambiguous"), r["result"]


def test_bundle_notes_an_inconclusive_run(tmp_path):
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_INCONCLUSIVE": "1"})
    S = make(str(run), BOpts(out=tmp_path / "b", rerun=False))
    assert any("inconclusive" in n for n in S["notes"]), S["notes"]


# Round 4: trailing non-retirement events (irq levels, ...) must not hide the last retirement.

def _irq_tail_run(d, last_retire=9970, events=29, end=10000, retired=1):
    d.mkdir(parents=True, exist_ok=True)
    rs = [{"schema": "rvw.rvfi/1", "xlen": 64, "core": "fake"}]
    rs += [{"order": i, "cycle": last_retire - 2 * (retired - 1 - i), "pc": hex(0x80000000 + 4 * i),
            "pc_next": hex(0x80000004 + 4 * i), "insn": "0x00000013", "rd": 0, "rd_wdata": "0x0", "trap": False}
           for i in range(retired)]
    rs += [{"event": "irq", "cycle": last_retire + 1 + j, "levels": hex((j % 2) << 3)} for j in range(events)]
    rs += [{"event": "end", "cycle": end, "status": "timeout"}]
    (d / "rvfi.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rs))
    (d / "result.json").write_text(json.dumps({
        "schema": "rvw.run/1", "core": "fake", "config": "small", "elf": SYMS_ELF,
        "elf_sha256": hashlib.sha256(Path(SYMS_ELF).read_bytes()).hexdigest(),
        "seed": 1, "max_cycles": end, "mem_latency": None, "status": "timeout", "fail_code": None, "message": None,
        "cycles": end, "instret": retired, "wall_s": 0.01, "artifacts": {"rvfi_trace": "rvfi.jsonl"},
        "replay": f"{FAKE} run --elf {SYMS_ELF} --seed 1 --max-cycles {end} --out {d}"}))
    return d


def test_hang_check_reads_past_trailing_events(tmp_path):
    from rvw.bundle.trace import read_rvfi_tail
    from rvw.runs import open_run
    from rvw.runs.hang import hang_check
    run = _irq_tail_run(tmp_path / "r")               # last retirement 30 cycles before the end
    assert [r["cycle"] for r in read_rvfi_tail(str(run / "rvfi.jsonl"), 1).retired] == [9970]
    hung, why = hang_check(open_run(run), 5000)
    assert hung is False and "cycle 9970" in why, why
    with pytest.raises(ValueError, match="not a hang"):
        Reducer(str(run), ROpts(out=tmp_path / "red", modes=[], hang_cycles=5000))


def test_rvfi_tail_finds_n_retirements_before_many_events(tmp_path):
    from rvw.bundle.trace import read_rvfi_tail
    run = _irq_tail_run(tmp_path / "r", last_retire=5000, events=5000, retired=100)
    t = read_rvfi_tail(str(run / "rvfi.jsonl"), 64)
    assert len(t.retired) == 64 and t.retired[-1]["cycle"] == 5000 and t.total == 100
    # an event-only trace is read to its start: nothing retired, which is then known
    only = _irq_tail_run(tmp_path / "e", retired=0, events=20000)
    assert read_rvfi_tail(str(only / "rvfi.jsonl"), 1).retired == []


def test_rvfi_tail_keeps_a_bounded_trap_history(tmp_path):
    """Review 5: scanning back for a retirement kept every trap (50,000 traps: 32 MB). Only the
    most recent ones are kept (the old 2n+16 window)."""
    import tracemalloc
    from rvw.bundle.trace import read_rvfi_tail
    p = tmp_path / "trap-only.jsonl"
    with p.open("w") as f:
        f.write('{"schema":"rvw.rvfi/1"}\n')
        f.write(json.dumps({"order": 0, "cycle": 1, "pc": "0x80000000"}) + "\n")   # the only retirement, at the start
        for i in range(50000):
            f.write(json.dumps({"event": "trap", "cycle": 10 + i, "cause": "0x2", "tval": "0x0", "intr": False}) + "\n")
    tracemalloc.start()
    try:
        t = read_rvfi_tail(str(p), 1)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert [r["cycle"] for r in t.retired] == [1]                     # still found behind the traps
    assert len(t.traps) == 18 and t.traps[-1]["cycle"] == 10 + 49999 and t.traps[0]["cycle"] == 10 + 49982
    assert peak < 1_000_000, peak                                     # was 32 MB; 0.26 MB before round 4


def test_reverse_lines_is_exact_across_chunks(tmp_path):
    from rvw.bundle.trace import reverse_lines
    lines = [("x" * (i % 13)) + str(i) for i in range(300)]
    p = tmp_path / "f.txt"
    p.write_text("\n".join(lines[:150]) + "\n\n" + "\n".join(lines[150:]))     # an empty line, no final newline
    for chunk in (1, 3, 7, 64, 1 << 16):
        assert list(reverse_lines(str(p), chunk)) == lines[::-1], chunk


# Round 4: a re-run is "reproduced", and its wave/trace used, only when it is conclusive.

def test_bundle_never_adopts_an_inconclusive_rerun(tmp_path, monkeypatch):
    run = fake_run(tmp_path / "r", "--seed", "9")                  # attributed assertion, no wave/trace
    monkeypatch.setenv("FAKE_INCONCLUSIVE", "1")                    # every re-run's failure is unattributed
    S = make(str(run), BOpts(out=tmp_path / "b", rerun_window=300, cut_cycles=50, spinaltrace=False))
    for name in ("rerun", "rerun-wave"):
        assert S[name]["reproduced"] is False and "not attributed" in S[name]["inconclusive"], S[name]
    assert not S.get("wave") and not S.get("snapshot"), (S.get("wave"), S.get("snapshot"))
    assert not (tmp_path / "b" / "wave-window.vcd").exists()
    assert any("inconclusive" in n and "not used" in n for n in S["notes"]), S["notes"]
    md = (tmp_path / "b" / "summary.md").read_text()
    assert "(reproduced)" not in md and "inconclusive" in md


def test_bundle_never_counts_a_wall_clock_rerun_as_reproduced(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_WALL_CLOCK", "1")
    run = fake_run(tmp_path / "r", "--seed", "9")                  # timeout:wall-clock at 1024
    S = make(str(run), BOpts(out=tmp_path / "b", rerun_window=300, cut_cycles=50, spinaltrace=False))
    assert S["rerun"]["reproduced"] is False and "wall-clock" in S["rerun"]["inconclusive"], S["rerun"]
    assert not S.get("wave"), S.get("wave")


def _spinaltrace_cfg(tmp_path, monkeypatch):
    cfg = tmp_path / "st.toml"
    cfg.write_text(CFG + f'\n[spinaltrace]\nadapter = "{FAKE}"\n')
    monkeypatch.setenv("RVW_CORE_CONFIG", str(cfg))


def test_bundle_spinaltrace_rerun_must_be_conclusive(tmp_path, monkeypatch):
    _spinaltrace_cfg(tmp_path, monkeypatch)
    run = fake_run(tmp_path / "r", "--seed", "9", "--wave", "--rvfi-trace")     # nothing to re-run for
    monkeypatch.setenv("FAKE_INCONCLUSIVE", "1")
    S = make(str(run), BOpts(out=tmp_path / "b", cut_cycles=50))
    st = S["rerun_spinaltrace"]
    assert st["reproduced"] is False and "not attributed" in st["inconclusive"], st
    assert any("SpinalTrace re-run" in n and "inconclusive" in n for n in S["notes"]), S["notes"]
    assert "inconclusive" in (tmp_path / "b" / "summary.md").read_text()


def test_bundle_spinaltrace_rerun_must_fail_at_the_same_cycle(tmp_path, monkeypatch):
    _spinaltrace_cfg(tmp_path, monkeypatch)
    run = fake_run(tmp_path / "r", "--seed", "9", "--wave", "--rvfi-trace")     # asserts at 2271
    res = json.loads((run / "result.json").read_text())
    res["cycles"] = 2260                                    # the SpinalTrace model will fail at 2271
    (run / "result.json").write_text(json.dumps(res))
    S = make(str(run), BOpts(out=tmp_path / "b", cut_cycles=50))
    st = S["rerun_spinaltrace"]
    assert st["signature"] == S["signature"] and st["cycles"] == 2271 and st["reproduced"] is False, st
    assert any("SpinalTrace re-run" in n and "2271" in n for n in S["notes"]), S["notes"]


# --- review 10 ----------------------------------------------------------------------------------

def test_a_pass_never_matches_a_signature(tmp_path):
    """Review 10: a passing trial matched a permissive signature (`re:.*`) and counted as a
    reproduction (reduce) or a bad commit (bisect)."""
    from rvw.runs import signature_matches
    assert not signature_matches("pass", "re:.*") and not signature_matches("pass", "pass")
    assert signature_matches("assert:lsu.scala:1241", "re:.*")
    run = fake_run(tmp_path / "r", "--seed", "9")                  # asserts; seeds 1, 2 pass
    r = Reducer(str(run), ROpts(out=tmp_path / "red", modes=["seeds"], seeds=2, seed_start=1, margin=10000,
                                signature="re:.*")).reduce()
    passes = [t for t in r["trials"] if t["status"] == "pass"]
    assert passes and not any(t["match"] for t in passes), r["trials"]
    assert r["best"]["dir"] == str(run)
    repo, g = make_core(tmp_path)                                   # bug from change 5
    run = fake_run(tmp_path / "rb", "--seed", "9", env={"FAKE_CORE": str(repo)})
    r = Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), signature="re:.*",
                                 workdir=tmp_path / "bis")).bisect()
    assert all(s["verdict"] == "good" for s in r["steps"] if s["signature"] == "pass"), r["steps"]
    assert r["result"]["commit"].endswith("change 5"), r["result"]


def test_reduce_symbol_is_exact_only_when_proven(tmp_path, monkeypatch):
    """Review 10: the binary search assumed the failure is monotone in the value and claimed
    `exact: true` for 7 although 1 also fails. Without --monotone or an exhaustive check the
    result is the smallest tested failing value, not exact."""
    from rvw.runs.elf import Elf
    monkeypatch.setenv("FAKE_SYMBOL", "limit==1,limit>=7")
    run = fake_run_elf(tmp_path / "r", SYMS_ELF, "--seed", "9")
    r = Reducer(str(run), ROpts(out=tmp_path / "red", modes=["symbols"], symbols=["limit"])).reduce()
    s = r["symbols"]["limit"]
    assert s["smallest_failing"] == 7 and s["exact"] is False and s["exact_by"] is None
    assert Elf(r["best"]["elf"]).read_int("limit") == 7
    assert "not proven" in (tmp_path / "red" / "reduce.md").read_text()
    # --monotone: the caller vouches for it; the boundary is then reported as exact.
    r = Reducer(str(run), ROpts(out=tmp_path / "mono", modes=["symbols"], symbols=["limit"], monotone=True)).reduce()
    assert r["symbols"]["limit"]["exact"] is True and r["symbols"]["limit"]["exact_by"] == "monotone"
    # --exhaustive: every untested value below is tried in order; the first failure is the minimum.
    r = Reducer(str(run), ROpts(out=tmp_path / "ex", modes=["symbols"], symbols=["limit"], exhaustive=True)).reduce()
    s = r["symbols"]["limit"]
    assert s["smallest_failing"] == 1 and s["exact"] is True and s["exact_by"] == "exhaustive"
    assert Elf(r["best"]["elf"]).read_int("limit") == 1
    # An exhaustive check cut by the budget proves nothing.
    r = Reducer(str(run), ROpts(out=tmp_path / "cut", modes=["symbols"], symbols=["limit"], exhaustive=True,
                                budget=8)).reduce()
    assert r["symbols"]["limit"]["exact"] is False


def test_reduce_symbol_stops_on_an_inconclusive_trial(tmp_path, monkeypatch):
    """A trial that proves nothing (wall-clock timeout) must not be read as a pass that moves the
    lower bound up."""
    monkeypatch.setenv("FAKE_SYMBOL", "limit>=7")
    run = fake_run_elf(tmp_path / "r", SYMS_ELF, "--seed", "9")
    monkeypatch.setenv("FAKE_WALL_CLOCK", "1")
    r = Reducer(str(run), ROpts(out=tmp_path / "red", modes=["symbols"], symbols=["limit"], monotone=True)).reduce()
    s = r["symbols"]["limit"]
    assert s["smallest_failing"] is None and s["exact"] is False and len(r["trials"]) == 1


@pytest.mark.parametrize('original', [0, 100])
@pytest.mark.parametrize('claim', ['monotone', 'exhaustive'])
def test_reduce_stale_symbol_upper_bound_reports_no_minimum(tmp_path, monkeypatch, original, claim):
    from rvw.runs.elf import Elf
    elf = Elf(SYMS_ELF)
    elf.write_int('limit', original, 4)
    program = tmp_path / 'program.elf'
    elf.save(str(program))
    monkeypatch.setenv('FAKE_SYMBOL', 'limit>=0')
    run = fake_run_elf(tmp_path / 'r', str(program), '--seed', '9')
    monkeypatch.setenv('FAKE_SYMBOL', 'limit>=1000')
    result = Reducer(str(run), ROpts(out=tmp_path / 'red', modes=['symbols'],
                                   symbols=['limit'], **{claim: True})).reduce()
    symbol = result['symbols']['limit']
    assert symbol['smallest_failing'] is None
    assert symbol['exact'] is False and symbol['exact_by'] is None
    assert not result['reproduced']
    assert len(result['trials']) == 1
    assert result['trials'][0]['symbols'] == {'limit': original}


# Review 11: an empty, invalid or truncated RVFI file counted as "nothing retired", so a run that
# was still retiring reproduced a hang. The trace must be C2, parse, and cover the final interval.

def test_hang_check_needs_a_valid_trace_that_covers_the_end(tmp_path):
    from rvw.runs import open_run
    from rvw.runs.hang import hang_check
    run = _irq_tail_run(tmp_path / "r", last_retire=1000, events=0, end=9000)
    trace = run / "rvfi.jsonl"
    good = trace.read_text()
    assert hang_check(open_run(run), 1000)[0] is True               # valid, end event at 9000
    head = good.splitlines()[0] + "\n"
    retire = good.splitlines()[1] + "\n"
    end = good.splitlines()[-1] + "\n"
    for name, text in [("empty", ""), ("not json", "garbage\n" + retire + end),
                       ("no header", retire + end), ("foreign header", '{"schema": "other/1"}\n' + retire + end),
                       ("header only", head), ("truncated", head + retire + end[:-8]),
                       ("no end event", head + retire),
                       ("end before the run's end", head + retire + end.replace("9000", "5000")),
                       ("records after end", head + end + retire),
                       ("cycles decrease", head + retire + end.replace("9000", "5000") + end),
                       ("record without cycle", head + retire.replace('"cycle"', '"cyc"') + end)]:
        trace.write_text(text)
        hung, why = hang_check(open_run(run), 1000)
        assert hung is None, (name, why)
    # A retirement inside the final interval proves "not a hang" even without an end event.
    trace.write_text(head + retire.replace('"cycle": 1000', '"cycle": 8500'))
    assert hang_check(open_run(run), 1000)[0] is False
    # The original run of a reduction: undetermined is noted, not refused and not a hang.
    trace.write_text("")
    red = Reducer(str(run), ROpts(out=tmp_path / "red", modes=[], hang_cycles=1000))
    assert any("not evidence" in n for n in red.notes), red.notes


def test_reduce_trial_without_hang_evidence_is_inconclusive(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_HANG", "3000")
    run = fake_run(tmp_path / "r", "--seed", "1", "--max-cycles", "9000", "--rvfi-trace")
    monkeypatch.setenv("FAKE_NO_RVFI_END", "1")      # trial traces may have stopped early
    r = Reducer(str(run), ROpts(out=tmp_path / "red", modes=["cycles", "seeds"], seeds=2,
                                hang_cycles=1000)).reduce()
    assert r["trials"] and r["reproduced"] is False, r["trials"]
    timeouts = [t for t in r["trials"] if t["signature"] == "timeout"]
    assert len(timeouts) >= 2 and not any(t["match"] for t in r["trials"]), r["trials"]
    assert all(t["conclusive"] is False and "end event" in t["hang"] for t in timeouts), timeouts


def test_bisect_timeout_without_hang_evidence_is_skipped(tmp_path, monkeypatch):
    repo = tmp_path / "core"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
    g("init", "-q")
    for i in range(1, 5):
        (repo / "f").write_text(str(i))
        g("add", "-A")
        g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", f"change {i}")
    monkeypatch.setenv("FAKE_HANG", "3000")
    run = fake_run(tmp_path / "r", "--seed", "1", "--max-cycles", "9000", "--rvfi-trace",
                   env={"FAKE_CORE": str(repo)})
    monkeypatch.setenv("FAKE_NO_RVFI_END", "1")
    r = Bisector(str(run), XOpts(good="HEAD~3", core_repo=str(repo), workdir=tmp_path / "bis",
                                 other="good")).bisect()
    timeouts = [s for s in r["steps"] if s["signature"] == "timeout"]
    assert timeouts and all(s["verdict"] == "skip" for s in timeouts), r["steps"]
    assert not r["result"].get("commit"), r["result"]


# Review 12: one conclusiveness rule (rvw.results.inconclusive_cause). A harness `error`, a
# synthesized result, a wall-clock timeout and C1 `inconclusive` neither reproduce nor rule out a
# failure, in reduce, bisect and bundle alike.

def test_reduce_symbol_search_stops_on_a_harness_error(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_SYMBOL", "limit>=7")
    run = fake_run_elf(tmp_path / "r", SYMS_ELF, "--seed", "9")
    monkeypatch.setenv("FAKE_ERROR", "1")
    for name, extra in (("ex", {"exhaustive": True}), ("mono", {"monotone": True}), ("re", {"signature": "re:.*"})):
        r = Reducer(str(run), ROpts(out=tmp_path / name, modes=["symbols"], symbols=["limit"], budget=150,
                                    **extra)).reduce()
        s = r["symbols"]["limit"]
        assert len(r["trials"]) == 1 and r["trials"][0]["status"] == "error", (name, r["trials"])
        t = r["trials"][0]
        assert t["match"] is False and t["conclusive"] is False and "harness error" in t["inconclusive"]
        assert s["smallest_failing"] is None and s["exact"] is False and "inconclusive" in s["note"], s
        assert r["reproduced"] is False and r["best"]["dir"] == str(run)


def test_reduce_never_matches_a_synthesized_or_error_trial(tmp_path, monkeypatch):
    run = fake_run(tmp_path / "r", "--seed", "9")
    for var in ("FAKE_SYNTH", "FAKE_ERROR"):
        monkeypatch.setenv(var, "1")
        r = Reducer(str(run), ROpts(out=tmp_path / var, modes=["cycles", "latency"], latencies=[1],
                                    signature="re:.*")).reduce()
        assert r["trials"] and not any(t["match"] or t["conclusive"] for t in r["trials"]), r["trials"]
        assert r["reproduced"] is False
        monkeypatch.delenv(var)


def test_reduce_bisect_bundle_treat_a_harness_error_run_as_inconclusive(tmp_path):
    repo, _ = make_core(tmp_path)
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo), "FAKE_ERROR": "1"})
    with pytest.raises(ValueError, match="inconclusive.*harness error"):
        Reducer(str(run), ROpts(out=tmp_path / "red"))
    with pytest.raises(ValueError, match="inconclusive.*harness error"):
        Bisector(str(run), XOpts(good="HEAD~7", core_repo=str(repo), workdir=tmp_path / "bis"))
    S = make(str(run), BOpts(out=tmp_path / "b", rerun=False))
    assert any("inconclusive" in n and "harness error" in n for n in S["notes"]), S["notes"]


def test_bisect_skips_harness_errors_whatever_other_says(tmp_path, monkeypatch):
    repo, _ = make_core(tmp_path)                                   # bug from change 5
    run = fake_run(tmp_path / "r", "--seed", "9", env={"FAKE_CORE": str(repo)})
    monkeypatch.setenv("FAKE_ERROR", "1")                           # the harness fails at every step
    r = Bisector(str(run), XOpts(good="HEAD~7", bad="HEAD", core_repo=str(repo), other="good",
                                 workdir=tmp_path / "bis")).bisect()
    assert r["steps"] and all(s["verdict"] == "skip" for s in r["steps"]), r["steps"]
    assert not r["result"].get("commit"), r["result"]


def test_one_conclusiveness_rule_for_c1_and_c3():
    from rvw.results import RunResult, TestEntry, inconclusive_cause, run_signature
    cases = [({"status": "error", "message": "harness"}, "harness error"),
             ({"status": "assert", "message": "x", "synthesized": True}, "rvw wrote"),
             ({"status": "timeout", "wall_clock_timeout": True}, "wall-clock"),
             ({"status": "pass", "inconclusive": "overlap"}, "overlap"),
             ({"status": "pass", "inconclusive": True}, "marked"),
             ({"status": "assert", "message": "x"}, None), ({"status": "pass"}, None),
             ({"status": "timeout"}, None)]
    for d, want in cases:
        r = RunResult.from_dict({"schema": "rvw.run/1", **d})
        extra = {k: v for k, v in d.items() if k not in ("status", "message")}
        e = TestEntry(id="t", status=d["status"], signature=run_signature(r), extra=extra)
        why = r.why_inconclusive
        assert (why is None) == (want is None) and (want is None or want in why), (d, why)
        assert e.conclusive == (want is None), d
        assert (inconclusive_cause(d["status"], extra, run_signature(r)) is None) == (want is None)


@pytest.mark.parametrize('opcode', ['bxxx', 'bzzz', 'b1x0', 'missing', 'uninitialized'])
@pytest.mark.parametrize('matching_rules', [True, False])
def test_handshakes_unknown_response_opcode_keeps_requests_open(tmp_path, opcode, matching_rules):
    """Review 15: an unknown D opcode must not close A and C requests with the same id."""
    from rvw.bundle import handshakes
    wave = HS_VCD.replace('b110 l', opcode + ' l')
    if opcode == 'missing':
        wave = HS_VCD.replace('$var wire 3 l d_opcode $end\n', '')
        wave = '\n'.join(line for line in wave.splitlines() if not line.endswith(' l')) + '\n'
    elif opcode == 'uninitialized':
        wave = HS_VCD.replace('b0 l\n', '').replace('b110 l\n', '')
    path = tmp_path / 'unknown.vcd'
    path.write_text(wave)
    channels = {n: {'valid': f'{n}_valid', 'ready': f'{n}_ready',
                    'id': f'{n}_source', 'opcode': f'{n}_opcode'} for n in ('a', 'c', 'd')}
    cfg = {'scope': r'^TOP\.', 'clock': 'clk', 'requests': ['a', 'c'], 'responses': ['d'],
           'channels': channels, 'opens': {'c': [6, 7]}}
    if matching_rules:
        cfg['closes'] = {'d': {'a': [0, 1, 2, 4, 5], 'c': [6]}}
    result = handshakes.analyze(cfg, str(path), None, 10)
    assert [(r['channel'], r['id']) for r in result['open_requests']] == [('a', '0x3'), ('c', '0x3')]
    response = result['channels']['d']
    assert response['fires'] == response['unknown_opcode_fires'] == 1
    assert response['last_unknown_opcode'] == {'time': 35,
                                              'value': None if opcode in ('missing', 'uninitialized') else opcode}
    assert 'unknown opcode' in handshakes.render_md(result)


@pytest.mark.parametrize('layout', ['indent', 'combined', 'split'])
def test_handshakes_whitespace_records(tmp_path, layout):
    from rvw.bundle.handshakes import analyze
    channels = {n: {'valid': f'{n}_valid', 'ready': f'{n}_ready',
                    'id': f'{n}_source', 'opcode': f'{n}_opcode'} for n in ('a', 'c', 'd')}
    cfg = {'scope': r'^TOP\.', 'clock': 'clk', 'channels': channels,
           'requests': ['a', 'c'], 'responses': ['d'], 'opens': {'c': [6, 7]},
           'closes': {'d': {'a': [0, 1, 2, 4, 5], 'c': [6]}}}
    p = tmp_path / 'hs.vcd'
    p.write_text(HS_VCD)
    expected = analyze(cfg, str(p), 45, 10)
    if layout == 'indent':
        text = '\n'.join('  ' + line for line in HS_VCD.splitlines())
    elif layout == 'combined':
        text = ' '.join(HS_VCD.split())
    else:
        text = '\n'.join(HS_VCD.split())
    p.write_text(text)
    assert analyze(cfg, str(p), 45, 10) == expected


@pytest.mark.parametrize('order', [('a', 'd'), ('d', 'a')])
@pytest.mark.parametrize('opcode_rules', [False, True])
@pytest.mark.parametrize('prior_request', [False, True])
def test_handshakes_same_edge_response_preserves_new_request(tmp_path, order, opcode_rules, prior_request):
    """Review 16: responses can close only requests open before this edge."""
    from rvw.bundle.handshakes import analyze
    p = tmp_path / 'reuse.vcd'
    text = HS_VCD.split('#0')[0] + '''#0
0! 1a 1b b11 c b100 d 0e 1f b0 g b0 h 0i 1j b11 k b1 l
#5
1!
#10
0! 0a
#15
1!
#20
0! 1a 1i
#25
1!
#30
0! 0a 0i
#35
1!
'''
    if not prior_request:
        text = text.replace('0! 1a 1b', '0! 0a 1b')
    p.write_text(text)
    chans = {n: {'valid': f'{n}_valid', 'ready': f'{n}_ready', 'id': f'{n}_source'} for n in order}
    cfg = {'scope': r'^TOP\.', 'clock': 'clk', 'channels': chans,
           'requests': ['a'], 'responses': ['d']}
    if opcode_rules:
        for n in chans:
            chans[n]['opcode'] = f'{n}_opcode'
        cfg['closes'] = {'d': {'a': [0, 1, 2, 4, 5]}}
    result = analyze(cfg, str(p), 35, 10)
    assert result['channels']['a']['fires'] == (2 if prior_request else 1)
    assert result['channels']['d']['fires'] == 1
    req = result['open_requests']
    assert len(req) == 1
    assert (req[0]['channel'], req[0]['id'], req[0]['age_cycles']) == ('a', '0x3', 1)
    # A later response closes the new request, including the conservative zero-latency case.
    p.write_text(text + '#40\n0! 1i\n#45\n1!\n')
    assert analyze(cfg, str(p), 45, 10)['open_requests'] == []


@pytest.mark.parametrize('name', ['elf', 'seed', 'mem_latency'])
def test_reduce_symbol_names_do_not_replace_run_metadata(tmp_path, monkeypatch, name):
    """Review 16: user symbol names must not replace C1 fields in trial reports."""
    import struct
    from rvw.runs.elf import Elf
    elf = Elf(SYMS_ELF)
    # Relocate the string table so any symbol name fits without rebuilding the fixture.
    symtab = next(s for s in elf.sections if s['type'] == 2)
    strtab = elf.sections[symtab['link']]
    old = elf.data[strtab['off']:strtab['off'] + strtab['size']]
    for k in range(symtab['size'] // symtab['entsize']):
        at = symtab['off'] + k * symtab['entsize']
        idx = struct.unpack_from('<I', elf.data, at)[0]
        if elf._str(symtab['link'], idx) == 'limit':
            struct.pack_into('<I', elf.data, at, len(old))
            break
    else:
        pytest.fail('limit symbol missing from fixture')
    strings = old + name.encode() + b'\0'
    at = elf.shoff + symtab['link'] * elf.shentsize + (24 if elf.is64 else 16)
    struct.pack_into('<QQ' if elf.is64 else '<II', elf.data, at, len(elf.data), len(strings))
    elf.data.extend(strings)
    src = tmp_path / 'reserved.elf'
    elf.save(str(src))
    monkeypatch.setenv('FAKE_SYMBOL', f'{name}>=7')
    run = fake_run_elf(tmp_path / 'r', str(src), '--seed', '9', '--mem-latency', '5')
    report = Reducer(str(run), ROpts(out=tmp_path / 'red', modes=['symbols'],
                                   symbols=[name], monotone=True)).reduce()
    assert report['reproduced']
    best = report['best']
    selected = json.loads((Path(best['dir']) / 'result.json').read_text())
    for key in ('seed', 'mem_latency', 'elf', 'cycles'):
        assert best[key] == selected[key]
    command = parse_replay(best['replay'])
    for key in ('seed', 'mem_latency', 'elf'):
        assert command.get(key) == str(selected[key])
    assert Elf(best['elf']).read_int(name) == 7
    for trial in report['trials']:
        actual = json.loads((Path(trial['dir']) / 'result.json').read_text())
        for key in ('seed', 'mem_latency', 'elf'):
            assert trial[key] == actual[key]
        assert trial['symbols'][name] == Elf(actual['elf']).read_int(name)


@pytest.mark.parametrize('threshold', [-5, 0, False, 1.5])
def test_nonpositive_hang_threshold_refused_before_work(monkeypatch, threshold):
    from rvw.runs.hang import hang_check
    def forbidden(*args, **kwargs):
        pytest.fail('invalid hang threshold reached run or adapter work')
    monkeypatch.setattr('rvw.runs.open_run', forbidden)
    monkeypatch.setattr('rvw.runs.adapter.execute_many', forbidden)
    monkeypatch.setattr('rvw.runs.adapter.execute', forbidden)
    with pytest.raises(ValueError, match='hang_cycles.*positive integer'):
        hang_check(None, threshold)
    with pytest.raises(ValueError, match='hang_cycles.*positive integer'):
        Reducer('unused', ROpts(hang_cycles=threshold))
    with pytest.raises(ValueError, match='hang_cycles.*positive integer'):
        Bisector('unused', XOpts(good='unused', hang_cycles=threshold))


@pytest.mark.parametrize('command,extra', [('reduce', []), ('bisect', ['--good', 'unused'])])
@pytest.mark.parametrize('threshold', [-5, 0])
def test_cli_refuses_nonpositive_hang_threshold(tmp_path, command, extra, threshold):
    before = set(tmp_path.iterdir())
    out = subprocess.run([sys.executable, '-m', 'rvw', command, str(tmp_path / 'unused'),
                          *extra, '--hang-cycles', str(threshold), '--json'],
                         capture_output=True, text=True)
    assert out.returncode == 2
    assert 'hang_cycles must be a positive integer' in out.stderr
    assert not out.stdout
    assert set(tmp_path.iterdir()) == before


def test_bundle_requests_shared_spinaltrace_flag_and_skips_missing_model(tmp_path, monkeypatch):
    from rvw.runs import adapter
    execute = adapter.execute
    requested = []
    def record(cmd, *args, **kw):
        requested.append(cmd.get('spinaltrace'))
        return execute(cmd, *args, **kw)
    monkeypatch.setattr(adapter, 'execute', record)
    run = fake_run(tmp_path / 'r', '--seed', '9', '--wave', '--rvfi-trace')
    report = make(str(run), BOpts(out=tmp_path / 'bundle'))
    assert report['dynpdg'].get('skipped')
    assert 'digest' not in report['dynpdg']
    assert 'dynpdg' not in report['files']
    assert requested == [True]
    assert report['rerun_spinaltrace']['reproduced'] is True


@pytest.mark.parametrize('error', ['model unavailable', 'spinaltrace-cli timed out'])
def test_bundle_does_not_claim_an_uncomputed_dependency_trace(tmp_path, error):
    from rvw.bundle.make import render_md, next_commands
    report = {'signature': 'timeout', 'status': 'timeout', 'run': 'run',
              'dynpdg': {'criterion': 'signal:head', 'error': error, 'command': 'cli dyn-pdg'}}
    md = render_md(report, tmp_path)
    assert 'Dependency trace unavailable' in md
    assert 'traced over the last cycles' not in md
    assert 'full graph in' not in md
    assert not any('spinaltrace -s' in cmd for cmd in next_commands(report, tmp_path, {}))
