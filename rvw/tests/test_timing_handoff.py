import json

import pytest

from rvw.sim.timing import capture, check, inspect, replay


def documents(tmp_path):
    for name in ('gates.v', 'cells.v', 'delays.sdf'): (tmp_path / name).write_text('captured ' + name)
    request = dict(schema='rvw.timing-request/1', top='tb', netlist='gates.v', sdf='delays.sdf',
        cell_libraries=['cells.v'], cells=['BUF'], delays=['iopath'], timing_checks=['setup'],
        unknown_behavior='four-state', corner='max')
    caps = dict(schema='rvw.timing-capabilities/1', simulator='fixture', version='1',
        cells=['BUF'], delays=['iopath'], timing_checks=['setup'], corners=['max'], unknown_behavior='four-state')
    path, support = tmp_path / 'request.json', tmp_path / 'caps.json'
    path.write_text(json.dumps(request)); support.write_text(json.dumps(caps))
    return path, support, caps


def test_readiness_is_not_native_or_physical_evidence(tmp_path):
    path, support, caps = documents(tmp_path)
    data = inspect(path, support)
    assert data['status'] == 'declared_compatible' and 'no annotation' in data['evidence']
    request, files = capture(path)
    (tmp_path / 'gates.v').write_text('changed')
    assert files['gates.v'] == b'captured gates.v'
    for field in ('cells', 'delays', 'timing_checks'):
        changed = dict(caps, **{field: []})
        with pytest.raises(ValueError, match='unsupported'): check(request, files, changed)
    with pytest.raises(ValueError, match='behavior mismatch'):
        check(request, files, dict(caps, unknown_behavior='two-state'))


def test_native_result_required_after_handoff(tmp_path):
    path, _, caps = documents(tmp_path)
    class Port:
        def timing_capabilities(self): return caps
        def run_timing(self, request, files): return {'status': 'compiled'}
    with pytest.raises(ValueError, match='native C1'): replay(Port(), path)
