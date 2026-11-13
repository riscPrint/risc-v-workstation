"""Debug task protocol: the example pack is solved by the rvw commands it names."""
import json
from pathlib import Path

import pytest

from rvw.wave import tasks
from rvw.wave.vcd import WaveError

PACK = Path(__file__).resolve().parents[2] / 'examples/wave-tasks/tasks.json'


def test_example_pack(gcd_db, tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_WAVE_INDEX_DIR', str(tmp_path / 'cache'))
    r = tasks.run(str(PACK), {'db': str(gcd_db)})
    assert r['solved'] == r['total'] == 4, json.dumps(r, indent=1)
    assert r['compared'] == 0 and 'nothing is compared' in r['comparison']


def test_missing_var_unsolved_and_reference(tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_WAVE_INDEX_DIR', str(tmp_path / 'cache'))
    spec = json.loads(PACK.read_text())
    for name in ('hs.vcd', 'gcd.vcd'):
        (tmp_path / name).write_text((PACK.parent / name).read_text())
    spec['tasks'][2]['expect'] = [{'path': 'first', 'equals': 99}]
    spec['tasks'][3]['reference'] = {'tool': 'Other', 'seconds': 30.0}
    p = tmp_path / 't.json'
    p.write_text(json.dumps(spec))
    r = {t['id']: t for t in tasks.run(str(p))['results']}
    assert r['why-x']['status'] == 'error' and 'missing variable' in r['why-x']['cause']
    assert r['first-stall']['status'] == 'unsolved'
    assert r['handshake-latency']['speedup'] > 1 and r['handshake-latency']['reference']['tool'] == 'Other'
    p.write_text('{"schema": "x"}')
    with pytest.raises(WaveError):
        tasks.run(str(p))
