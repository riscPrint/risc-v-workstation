"""Envelope tests use a port fixture, not a native RTL restore."""
import json

import pytest

from rvw.sim import checkpoint as ck


class Port:
    def __init__(self):
        self.native = b'native-model-state'
        self.state = {name: {} for name in ck.STATE}
        self.state['counters'] = {'cycles': 17, 'instret': 9}
        self.stopped = True
        self.effects = []
        self.restores = 0

    def quiescent(self): return self.stopped
    def external_effects(self): return self.effects
    def save(self): return self.native, self.state
    def validate_restore(self, native, state):
        if native != b'native-model-state':
            raise ValueError('unsupported native state')
    def restore(self, native, state):
        self.native, self.state = native, state
        self.restores += 1


@pytest.fixture
def identity():
    return {key: 'a' * 64 for key in ck.IDENTITIES}


def test_round_trip_new_instance(tmp_path, identity):
    path = tmp_path / 'checkpoint.json'
    saved = ck.save(Port(), path, identity=identity)
    fresh = Port()
    fresh.state = {}
    restored = ck.restore(fresh, path, identity=identity)
    assert restored['sha256'] == saved['sha256']
    assert fresh.restores == 1
    assert fresh.state['counters'] == {'cycles': 17, 'instret': 9}
    with pytest.raises(FileExistsError):
        ck.save(Port(), path, identity=identity)


@pytest.mark.parametrize('fault', ['truncate', 'digest', 'identity', 'state', 'native', 'schema'])
def test_bad_snapshot_never_mutates_instance(tmp_path, identity, fault):
    import hashlib
    path = tmp_path / 'checkpoint.json'
    ck.save(Port(), path, identity=identity)
    obj = json.loads(path.read_text())
    if fault == 'identity': obj['payload']['identity']['rtl'] = 'b' * 64
    if fault == 'state': del obj['payload']['state']['rng']
    if fault == 'native': obj['payload']['native'] = '!!!'
    if fault == 'schema': obj['payload']['schema'] = 'future/2'
    if fault != 'digest': obj['sha256'] = hashlib.sha256(ck._bytes(obj['payload'])).hexdigest()
    else: obj['sha256'] = '0' * 64
    path.write_bytes(ck._bytes(obj)[:10] if fault == 'truncate' else ck._bytes(obj))
    fresh = Port()
    with pytest.raises(ValueError): ck.restore(fresh, path, identity=identity)
    assert fresh.restores == 0


@pytest.mark.parametrize('phase', ['save', 'restore'])
@pytest.mark.parametrize('fault', ['running', 'external'])
def test_unsupported_boundary_refused(tmp_path, identity, phase, fault):
    path = tmp_path / 'checkpoint.json'
    ck.save(Port(), path, identity=identity)
    port = Port()
    if fault == 'running': port.stopped = False
    else: port.effects = ['host socket']
    with pytest.raises(ValueError):
        if phase == 'save': ck.save(port, tmp_path / 'other.json', identity=identity)
        else: ck.restore(port, path, identity=identity)
    assert port.restores == 0


def test_complete_inventory_and_adapter_validation(tmp_path, identity):
    port = Port()
    port.state['rng'] = None
    with pytest.raises(ValueError): ck.save(port, tmp_path / 'null.json', identity=identity)
    port.state['rng'] = {}
    port.native = b'other build'
    path = tmp_path / 'checkpoint.json'
    ck.save(port, path, identity=identity)
    fresh = Port()
    with pytest.raises(ValueError, match='unsupported native'):
        ck.restore(fresh, path, identity=identity)
    assert fresh.restores == 0
