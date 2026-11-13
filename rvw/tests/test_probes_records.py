"""rvw probes mmu-walks and fault-sites converters (synthetic streams)."""
import json

import pytest

from rvw.fault import campaign
from rvw.probes import api
from rvw.regress.mmu_walk import check_c2, walk

pytestmark = pytest.mark.fast

ROOT = 0x80010000
# Sv32: level-1 PTE points to a table at 0x80011000; level-0 leaf maps va 0x00400000 to 0x80020000.
MEMORY = {ROOT + 4 * 1: (0x80011000 >> 12) << 10 | 0x1,
          0x80011000: (0x80020000 >> 12) << 10 | 0xcf}
ACCESS = dict(mode="sv32", root=ROOT, va=0x00400010, access="load", memory=MEMORY)


def write(path, lines):
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return path


def probes():
    meta = {"walker": "ptw"}
    return [
        {"id": 0, "kind": "walk", "name": "ptw_response", "meta": dict(meta, event="response"),
         "fields": [["address", 34], ["data", 32], ["level", 2], ["fault", 1]]},
        {"id": 1, "kind": "walk", "name": "ptw_result", "meta": dict(meta, event="result", mode="sv32"),
         "fields": [["va", 32], ["access", 2], ["root", 34], ["status", 2], ["pa", 34]]},
        {"id": 2, "kind": "fault", "name": "pc", "meta": {"path": "core.fetch_pc"}, "fields": [["value", 32]]},
    ]


def stream(tmp_path, rows, name="probe-events.jsonl", plist=None):
    head = {"schema": "rvw.probe-events/1", "identity": {"elf_sha256": "aa"}, "probes": plist or probes()}
    return write(tmp_path / name, [head, *rows, {"end": True, "cycles": 100, "counters": {}, "events": {}}])


def c2(tmp_path, n=3):
    head = {"schema": "rvw.rvfi/2", "xlen": 32, "isa": "rv32im_zicsr", "core": "x", "config": "c", "elf": "a.elf", "elf_sha256": "aa", "capabilities": ["csr"], "csr_snapshot": ["0x340"]}
    recs = [{"order": i, "cycle": 10 * (i + 1), "pc": hex(0x100 + 4 * i), "pc_next": hex(0x104 + 4 * i),
             "insn": "0x13", "mode": 1, "trap": False, "intr": False, "halt": False, "rs1": 0, "rs1_rdata": "0x0",
             "rs2": 0, "rs2_rdata": "0x0", "rd": 0, "rd_wdata": "0x0", "mem_addr": "0x0", "mem_rmask": 0,
             "mem_wmask": 0, "mem_rdata": "0x0", "mem_wdata": "0x0", "mem_fault": False, "csr_state": {"0x340": "0x0"}} for i in range(n)]
    return write(tmp_path / "rvfi.jsonl", [head, *recs, {"event": "end", "cycle": 99, "status": "pass"}])


def reference_rows(cycle, access=ACCESS, data_override=None):
    ref = walk(**access)
    rows = [[cycle + i, 0, r["address"], (data_override if data_override is not None and i == 1 else r.get("data", 0)),
             r["level"], int(r["fault"])] for i, r in enumerate(ref["reads"])]
    status = {"success": 0, "page-fault": 1, "access-fault": 2}[ref["status"]]
    rows.append([cycle + len(rows), 1, access["va"], 0, access["root"], status, ref.get("pa", 0)])
    return rows


def test_mmu_walks_round_trip_through_the_walk_checker(tmp_path):
    ev = stream(tmp_path, reference_rows(12))
    out = tmp_path / "walks.jsonl"
    rep = api.run_convert(ev, "mmu-walks", out, c2=c2(tmp_path))
    assert rep == {"format": "C2 with mmu_walks", "walks": 1, "attached": 1, "unattached": 0}
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert "mmu_walks" in rows[2] and rows[2]["mmu_walks"][0]["reads"][0]["level"] == 1  # retired at cycle 20
    assert check_c2(out, [ACCESS])["status"] == "consistent"


def test_mmu_walks_wrong_pte_data_is_a_checker_mismatch(tmp_path):
    ev = stream(tmp_path, reference_rows(12, data_override=0x123))
    out = tmp_path / "walks.jsonl"
    api.run_convert(ev, "mmu-walks", out, c2=c2(tmp_path))
    assert check_c2(out, [ACCESS])["status"] == "mismatch"


def test_mmu_walks_after_last_retirement_are_reported(tmp_path):
    ev = stream(tmp_path, reference_rows(95))
    rep = api.run_convert(ev, "mmu-walks", tmp_path / "w.jsonl", c2=c2(tmp_path))
    assert rep["unattached"] == 1 and rep["status"] == "incomplete"


def test_mmu_walks_refuse_unknown_codes_and_missing_result_probe(tmp_path):
    bad = stream(tmp_path, [[12, 1, 0x400010, 3, ROOT, 0, 0]])
    with pytest.raises(ValueError, match="not a known code"):
        api.run_convert(bad, "mmu-walks", tmp_path / "w.jsonl", c2=c2(tmp_path))
    none = stream(tmp_path, [], name="n.jsonl", plist=probes()[:1])
    with pytest.raises(ValueError, match="no walk result probe"):
        api.run_convert(none, "mmu-walks", tmp_path / "x.jsonl", c2=c2(tmp_path))


def test_mmu_observations_skip_walk_results(tmp_path):
    ev = stream(tmp_path, reference_rows(12))
    rep = api.run_convert(ev, "mmu", tmp_path / "o.jsonl")
    assert rep["counts"] == {"walk_response": 2}


def test_fault_sites_feed_the_fault_plan(tmp_path):
    ev = stream(tmp_path, [])
    out = tmp_path / "sites.json"
    assert api.run_convert(ev, "fault-sites", out) == {"format": "rvw fault sites", "sites": 1, "bits": 32}
    sites = campaign.listed_sites(out)
    assert sites == [{"path": "core.fetch_pc", "width": 32, "clock_domain": None}]
    plan = campaign.plan(sites, kinds=("flip",), window=(0, 10), samples=4, seed=3)
    assert len(plan["faults"]) == 4 and {f["site"] for f in plan["faults"]} == {"core.fetch_pc"}
    nopath = stream(tmp_path, [], name="np.jsonl", plist=[dict(probes()[2], id=0, meta={})])
    with pytest.raises(ValueError, match="no register path"):
        api.run_convert(nopath, "fault-sites", tmp_path / "s2.json")


def test_fault_plan_cli_accepts_a_site_list(tmp_path, capsys):
    from rvw.cli import main
    sites = tmp_path / "sites.json"
    sites.write_text(json.dumps({"sites": [{"path": "a.b", "width": 4}, {"path": "a.c", "width": 2}]}))
    assert main(["fault", "plan", "--sites", str(sites), "--exclude", "a.c", "--kinds", "flip", "--window", "0:5",
                 "--samples", "3", "--out", str(tmp_path / "plan.json")]) == 0
    plan = json.loads((tmp_path / "plan.json").read_text())
    assert plan["site_bits"] == 4 and plan["design_db_sha256"]
