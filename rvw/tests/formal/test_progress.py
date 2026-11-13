import json
import pytest
from rvw.formal.progress import metrics,Progress

pytestmark=pytest.mark.fast


def test_depth_is_not_requested_depth_or_pdr_frame():
    r=metrics('depth 100\nFrame=42\nChecking assertions in step 7..')
    assert r['depth_reached']==7 and r['pdr_frame']==42
    assert metrics('Frame=9')['depth_reached'] is None
    assert metrics('')['depth_reached'] is None


def test_json_events_include_property_and_unknown_memory(tmp_path,monkeypatch):
    from rvw.formal import progress
    monkeypatch.setattr(progress,'memory',lambda _:None)
    p=tmp_path/'events.jsonl';d=tmp_path/'engine';d.mkdir()
    tracker=Progress(p,'p1','abc:pdr',d)
    tracker.start(999999)
    (d/'engine.log').write_text('Checking assertions in step 3..')
    tracker.stop('timeout')
    rows=[json.loads(x) for x in p.read_text().splitlines()]
    assert [r['event'] for r in rows]==['started','finished']
    assert rows[-1]['depth_reached']==3 and rows[-1]['memory_bytes'] is None
    assert rows[-1]['property_id']=='p1' and rows[-1]['native_status']=='timeout'
    assert rows[-1]['elapsed_s']>=0
