"""Kanata from a core that reuses ROB IDs and flushes a whole ROB tail in one cycle."""
import pytest

from rvw.perf import kanata as kreader
from rvw.probes import api
from test_probes import probe, stream

pytestmark = pytest.mark.fast


def test_first_stage_gating_and_younger_flush(tmp_path):
    probes = [probe(0, "stage", "rename_0", ["id", "pc"], stage="Rn", lane="0", first="true"),
              probe(1, "stage", "issue_0", ["id"], stage="Is", lane="0"),
              probe(2, "retire", "commit_0", ["id"]),
              probe(3, "flush", "reschedule", ["id", "inclusive"], range="younger")]
    rows = [[1, 1, 3],            # late event for ID 3 before it entered: orphan
            [1, 0, 1, 0x100], [1, 0, 2, 0x104], [2, 0, 3, 0x108], [2, 0, 0, 0x10c],
            [3, 1, 1], [3, 1, 2],
            [4, 2, 1], [4, 3, 1, 0],  # 1 retires; 2, 3, 0 (younger) flush
            [5, 1, 2],                # stale completion for flushed ID 2: orphan
            [6, 0, 2, 0x200], [7, 2, 2],
            [8, 0, 3, 0x204], [9, 3, 3, 1]]  # trap: 3 itself flushes (inclusive)
    ev = stream(tmp_path, probes, rows)
    rep = api.run_convert(ev, "kanata", tmp_path / "k.log")
    assert rep == {"format": "Kanata 0004", "instructions": 6, "retired": 2, "flushed": 4, "stall_samples": 0,
                   "predictions": 0, "open": 0, "orphan_events": 2, "stale_closed": 0}
    from rvw.probes.validate import _id_findings
    from rvw.probes.events import read
    assert not [f for f in _id_findings(read(ev)) if f["severity"] == "error"]
    t = kreader.read(tmp_path / "k.log")
    assert sorted(k for k, i in t.instructions.items() if i.flushed) == ["1", "2", "3", "5"]
    assert [s.stage for s in t.instructions["0"].spans] == ["Rn", "Is"]


def test_reused_live_id_and_unanchored_flush(tmp_path):
    probes = [probe(0, "stage", "rename", ["id", "pc"], stage="Rn", lane="0", first="true"),
              probe(1, "stage", "issue", ["id"], stage="Is", lane="0"),
              probe(2, "flush", "reschedule", ["id", "inclusive"], range="younger")]
    rows = [[1, 2, 9, 1], [1, 0, 4, 0x100], [2, 0, 4, 0x100], [3, 1, 4], [4, 0, 4, 0x200]]
    rep = api.run_convert(stream(tmp_path, probes, rows), "kanata", tmp_path / "k.log")
    assert rep["unanchored_flushes"] == 1
    assert rep["stale_closed"] == 1 and rep["instructions"] == 2 and rep["open"] == 1


def test_sampling_bounds_keep_idle_cycles(tmp_path):
    import json
    probes = [probe(0, "stage", "rename", ["id", "pc"], stage="Rn", lane="0", first="true"),
              probe(1, "retire", "commit", ["id"])]
    path = stream(tmp_path, probes, [[8,0,1,0x100], [10,1,1]])
    rows = path.read_text().splitlines()
    end = json.loads(rows[-1]);end.update(first_cycle=1,last_cycle=20)
    rows[-1] = json.dumps(end);path.write_text('\n'.join(rows)+'\n')
    out=tmp_path/'bounds.log';api.run_convert(path,'kanata',out)
    trace=kreader.read(out)
    assert (trace.start,trace.end)==(1,20)
