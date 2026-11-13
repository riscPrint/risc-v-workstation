import json

import pytest

from rvw.sim.live import capture, resume, suffix_check

PORT = '''
from rvw.sim.checkpoint import STATE
class Port:
    def __init__(self): self.cycle = 0
    def advance(self, unit, target): self.cycle = target
    def position(self, unit): return self.cycle
    def quiescent(self): return True
    def external_effects(self): return []
    def save(self):
        state = {key: {} for key in STATE}
        state['counters'] = {'cycles': self.cycle}
        return b'model', state
    def validate_restore(self, native, state): assert native == b'model'
    def restore(self, native, state): self.cycle = state['counters']['cycles']
    def finish(self, out):
        out.mkdir()
        return {'cycles': self.cycle}
    def close(self): pass
def create(options): return Port()
'''


def test_project_port_capture_resume_and_identity(tmp_path):
    (tmp_path / 'port.py').write_text(PORT)
    manifest = tmp_path / 'adapter.json'
    manifest.write_text(json.dumps(dict(schema='rvw.snapshot-adapter/1', module='port.py',
        identity_files={key: ['port.py'] for key in ('rtl', 'native_build', 'harness', 'stimulus')})))
    snapshot = tmp_path / 'snapshot.json'
    assert capture(manifest, snapshot, cycle=8)['status'] == 'saved'
    assert resume(manifest, snapshot, tmp_path / 'out')['result']['cycles'] == 8
    with pytest.raises(ValueError): capture(manifest, snapshot, cycle=8, instruction=4)
    (tmp_path / 'port.py').write_text(PORT + '\n# changed\n')
    with pytest.raises(ValueError, match='identity mismatch'):
        resume(manifest, snapshot, tmp_path / 'out2')


def test_exact_suffix_requires_complete_and_nonempty_evidence(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    prefix = b'{"schema":"rvw.rvfi/1"}\n'
    suffix = b'{"order":0,"cycle":2}\n{"event":"end","cycle":3,"status":"pass"}\n'
    a.write_bytes(prefix + suffix); b.write_bytes(prefix + suffix)
    assert suffix_check(a, b, position=len(prefix))['status'] == 'equivalent'
    with pytest.raises(ValueError): suffix_check(a, b, position=len(prefix) + len(suffix))
    b.write_bytes(prefix + suffix.replace(b'"cycle":2', b'"cycle":1'))
    with pytest.raises(ValueError, match='suffix mismatch'): suffix_check(a, b, position=len(prefix))
