import json

import pytest

from rvw.sim import checkpoint
from rvw.sim.reverse import reverse_step
from rvw.sim.live import _port
from test_live_checkpoint import PORT


def test_restore_nearest_checkpoint_and_forward_execution(tmp_path):
    source = PORT.replace("state['counters'] = {'cycles': self.cycle}",
                          "state['counters'] = {'instructions': self.cycle}")
    source = source.replace("['counters']['cycles']", "['counters']['instructions']")
    source = source.replace('    def close(self): pass', '''    def replay_to_instruction(self, target, *, max_seconds):
        assert max_seconds == 7
        assert self.cycle == 8
        self.cycle = target
    def close(self): pass''')
    (tmp_path / 'port.py').write_text(source)
    manifest = tmp_path / 'adapter.json'
    manifest.write_text(json.dumps(dict(schema='rvw.snapshot-adapter/1', module='port.py',
        identity_files={key: ['port.py'] for key in checkpoint.IDENTITIES})))
    paths = []
    for count in (2, 8, 20):
        port, identity = _port(manifest)
        port.advance('instructions', count)
        path = tmp_path / f'{count}.json'
        checkpoint.save(port, path, identity=identity)
        paths.append(path)
    out = tmp_path / 'reverse.json'
    result = reverse_step(manifest, paths, out, current=25, target=11, max_seconds=7)
    assert result['available_history'] == [2, 8, 20]
    assert result['restored_instruction'] == 8
    _, state, _ = checkpoint.load(out, identity=identity)
    assert state['counters']['instructions'] == 11
    with pytest.raises(ValueError, match='outside available history'):
        reverse_step(manifest, paths, out, current=25, target=1)
    with pytest.raises(ValueError, match='precede'):
        reverse_step(manifest, paths, out, current=25, target=26)
