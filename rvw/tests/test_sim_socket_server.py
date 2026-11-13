"""Serial service lifetime, timeout and existing adapter C1 validation."""
import json
from pathlib import Path
import sys
import tempfile
import threading

import pytest
from rvw.sim.server import request, serve

pytestmark = pytest.mark.fast


def test_serial_jobs_share_native_process_and_shutdown():
    with tempfile.TemporaryDirectory(prefix='rvws-', dir='/tmp') as directory:
        root = Path(directory)
        adapter = root / 'adapter.py'
        adapter.write_text('''import json, os, sys
for line in sys.stdin:
 job=json.loads(line)
 print(json.dumps(dict(pid=os.getpid(), job=job)), flush=True)
 if job.get('op')=='shutdown': break
''')
        endpoint = root / 'server.sock'
        ready = threading.Event()
        worker = threading.Thread(target=serve, args=(endpoint, [sys.executable, str(adapter)]),
                                  kwargs={'ready': ready}, daemon=True)
        worker.start()
        assert ready.wait(5)
        first = request(endpoint, {'seed': 3}, timeout=5)
        second = request(endpoint, {'seed': 9}, timeout=5)
        assert first['pid'] == second['pid']
        assert second['job']['seed'] == 9
        request(endpoint, {'op': 'shutdown'}, timeout=5)
        worker.join(5)
        assert not worker.is_alive()
        assert not endpoint.exists()


def test_timeout_stops_service_and_native_process():
    with tempfile.TemporaryDirectory(prefix='rvws-', dir='/tmp') as directory:
        endpoint = Path(directory) / 'server.sock'
        ready = threading.Event()
        worker = threading.Thread(target=serve,
                                  args=(endpoint, [sys.executable, '-c', 'import time; time.sleep(30)'], .05),
                                  kwargs={'ready': ready}, daemon=True)
        worker.start()
        assert ready.wait(5)
        with pytest.raises(ValueError, match='timed out'):
            request(endpoint, {'seed': 1}, timeout=5)
        worker.join(5)
        assert not worker.is_alive()
        assert not endpoint.exists()


def test_unsupported_revision_does_not_reach_live_server(tmp_path, monkeypatch):
    from rvw.runs.adapter import Command, execute
    import rvw.sim.server as server
    monkeypatch.setattr(server, 'request', lambda *a, **k: pytest.fail('unsupported revision was submitted'))
    cmd = Command(env={'RVW_ADAPTER_RESOLUTION_ERROR': 'no compatible adapter'},
                  exe=['unused'], opts={'--elf': 'unused'})
    attempt = execute(cmd, tmp_path / 'run', server='unused.sock')
    assert attempt.run is None
    assert 'unsupported revision' in attempt.error


@pytest.mark.parametrize('session,rtl,error', [('same', 'rtl', None), ('other', 'rtl', 'session'),
                                              ('same', 'changed', 'RTL'), (None, 'rtl', 'session')])
def test_live_reproduction_requires_session_and_rtl(session, rtl, error):
    from rvw.sim.server import identity_error
    original = dict(rtl_sha256='rtl', details={'simulation_session': {'id': 'same'}})
    rerun = dict(rtl_sha256=rtl, details={'simulation_session': {'id': session}})
    found = identity_error(original, rerun)
    assert found is None if error is None else error in found


def test_live_command_captures_elf_without_launching_a_source_tree(tmp_path, monkeypatch):
    import hashlib
    from types import SimpleNamespace
    from rvw.common.capture import Capture
    from rvw.runs.inputs import DebugInputs
    monkeypatch.setattr('rvw.runs.inputs.new_capture', lambda: Capture(tmp_path / 'capture'))
    elf = tmp_path / 'program'
    elf.write_bytes(b'captured program')
    inputs = DebugInputs()
    data = dict(elf=str(elf), elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
                replay='unused run --elf ' + str(elf), seed=7, config='project', max_cycles=100)
    run = SimpleNamespace(get=data.get, dir=tmp_path, capture=inputs.capture)
    monkeypatch.setattr(inputs, 'build_tree', lambda *a, **k: pytest.fail('live path launched a source tree'))
    command = inputs.live_command(run)
    assert Path(command.get('elf')).read_bytes() == elf.read_bytes()
    assert command.get('elf') != str(elf)
    inputs.verify()
    data['elf_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='sha256 mismatch'):
        inputs.live_command(run)
    data['elf_sha256'] = hashlib.sha256(elf.read_bytes()).hexdigest()
    data['replay'] += ' --boot-payloads unsupported.json'
    with pytest.raises(ValueError, match='structured input'):
        inputs.live_command(run)
