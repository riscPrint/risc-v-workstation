"""Native protocol fixtures. These tests do not claim RTL verification."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from rvw.farm.executor import cancel, execute
from rvw.farm.resources import reserve
from test_native_farm import IDENTITY, adapter


def test_reservations_limits_locks_and_release(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    config = tmp_path / '.config/rvw'
    config.mkdir(parents=True)
    (config / 'farm-capacity.json').write_text(json.dumps({'cpu': 2, 'memory_bytes': 100}))
    root = tmp_path / 'reservations'
    with reserve({'cpu': 1, 'memory_bytes': 70, 'locks': ['native-build']}, .2, root) as report:
        assert report['memory_bytes'] == 70
        for resources in ({'cpu': 2}, {'memory_bytes': 40}, {'locks': ['native-build']}):
            with pytest.raises(ValueError, match='wait timeout'):
                with reserve(resources, .1, root):
                    pytest.fail('reservation conflict was admitted')
    assert json.loads((root / 'reservations.json').read_text()) == []
    with pytest.raises(ValueError, match='exceeds'):
        with reserve({'cpu': 3}, .1, root):
            pass
    with pytest.raises(RuntimeError):
        with reserve({'cpu': 2, 'memory_bytes': 100}, .1, root):
            raise RuntimeError('cancel fixture')
    assert json.loads((root / 'reservations.json').read_text()) == []


def test_two_hosts_cancel_acknowledges_child_kill(tmp_path, adapter):
    options = os.environ.get('RVW_TEST_SSH_OPTIONS')
    if not options:
        pytest.skip('native localhost SSH required')
    script = Path(adapter[1])
    text = script.read_text().replace('    manifest = pathlib.Path', '''    import subprocess, time, signal
    child = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(120)'])
    pathlib.Path(__file__ + '.started-' + str(__import__('os').getpid())).write_text(str(child.pid))
    time.sleep(120)
    manifest = pathlib.Path''')
    script.write_text(text)
    hosts = [{'name': name, 'address': 'localhost', 'python': sys.executable,
              'ssh_options': json.loads(options), 'resources': {'cpu': 1, 'memory_bytes': 1024, 'locks': [name]}}
             for name in ('host-a', 'host-b')]
    elf = tmp_path / 'test.elf'; elf.write_bytes(b'pass')
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(''.join(json.dumps({'elf': str(elf), 'config': 'test', 'seed': i}) + '\n' for i in range(2)))
    output = tmp_path / 'out'
    result = []
    thread = threading.Thread(target=lambda: result.append(execute(hosts, manifest, adapter, [*adapter, 'identity'], IDENTITY, output, timeout=30)))
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while len(list(tmp_path.glob('adapter.py.started-*'))) < 2 and time.monotonic() < deadline:
            time.sleep(.1)
        assert len(list(tmp_path.glob('adapter.py.started-*'))) == 2
        report = cancel(output)
        assert report['status'] == 'cancelled', report
        assert all(r['process_groups_gone'] and r['groups'] for r in report['shards'])
        from rvw.farm.worker import groups_gone
        assert all(groups_gone(r['groups']) for r in report['shards'])
        root = Path.home() / '.cache/rvw/farm'
        workers = [json.loads((root / 'shards' / r['token'] / 'state.json').read_text())['pid'] for r in report['shards']]
        assert not any(r['pid'] in workers for r in json.loads((root / 'reservations.json').read_text()))
    finally:
        if thread.is_alive():
            cancel(output)
        thread.join(40)
    assert not thread.is_alive()
    assert result[0]['status'] == 'inconclusive'
    assert all(s['cancellation']['acknowledged'] for s in result[0]['shards'])


def test_separate_process_waits_for_host_capacity(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    config = tmp_path / '.config/rvw'; config.mkdir(parents=True)
    (config / 'farm-capacity.json').write_text(json.dumps({'cpu': 1, 'memory_bytes': 100}))
    code = '''from rvw.farm.resources import reserve
import pathlib,sys,json
pathlib.Path(sys.argv[1]).write_text('waiting')
with reserve({'cpu':1,'memory_bytes':80,'locks':['build']}, 5) as report:
    pathlib.Path(sys.argv[2]).write_text(json.dumps(report))
'''
    waiting, acquired = tmp_path / 'waiting', tmp_path / 'acquired'
    with reserve({'cpu': 1, 'memory_bytes': 80, 'locks': ['build']}, 1):
        process = subprocess.Popen([sys.executable, '-c', code, str(waiting), str(acquired)])
        deadline = time.monotonic() + 3
        while not waiting.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert waiting.exists()
        time.sleep(.2)
        assert not acquired.exists()
    assert process.wait(timeout=6) == 0
    assert json.loads(acquired.read_text())['queued_s'] >= .1


def test_fifo_prevents_small_request_bypassing_large_waiter(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    config = tmp_path / '.config/rvw'; config.mkdir(parents=True)
    (config / 'farm-capacity.json').write_text(json.dumps({'cpu': 2, 'memory_bytes': 100}))
    root = tmp_path / 'reservations'
    order, errors = [], []
    def run(cpu):
        try:
            with reserve({'cpu': cpu}, 3, root):
                order.append(cpu)
                time.sleep(.1)
        except Exception as exc:
            errors.append(exc)
    with reserve({'cpu': 1}, 1, root):
        large = threading.Thread(target=run, args=(2,)); large.start()
        deadline = time.monotonic() + 2
        while not json.loads((root / 'queue.json').read_text()) and time.monotonic() < deadline:
            time.sleep(.02)
        assert json.loads((root / 'queue.json').read_text())
        small = threading.Thread(target=run, args=(1,)); small.start()
        time.sleep(.2)
        assert order == []
    large.join(4); small.join(4)
    assert not errors
    assert order == [2, 1]
    assert json.loads((root / 'queue.json').read_text()) == []


def test_wait_timeout_removes_ticket(tmp_path):
    with reserve({'locks': ['build']}, 1, tmp_path):
        with pytest.raises(ValueError, match='wait timeout'):
            with reserve({'locks': ['build']}, .1, tmp_path):
                pass
        assert json.loads((tmp_path / 'queue.json').read_text()) == []


def test_recovery_retains_failures_and_missing_cells(tmp_path):
    from rvw.farm.executor import recover, save_json
    save_json(tmp_path / 'plan.json', {'schema': 'rvw.farm/1', 'expected_cells': 3,
        'plan': [{'id': str(i)} for i in range(3)], 'shards': [
            {'host': 'a', 'expected_cells': ['0', '2']}, {'host': 'b', 'expected_cells': ['1']}]})
    save_json(tmp_path / 'progress-0.json', {'host': 'a', 'expected_cells': ['0', '2'],
        'status': 'inconclusive', 'cells': [{'id': '0', 'status': 'fail', 'inconclusive': None}]})
    report = recover(tmp_path)
    assert report['status'] == 'inconclusive'
    assert report['shards'][0]['cells'][0]['status'] == 'fail'
    assert report['shards'][0]['missing_cells'] == ['2']
    assert report['shards'][1]['missing_cells'] == ['1']
    assert not (tmp_path / 'farm.json').exists()  # Read-only.
    save_json(tmp_path / 'farm.json', {**report, 'status': 'complete'})
    assert recover(tmp_path)['status'] == 'complete'


def test_controller_checkpoint_survives_dispatch_crash(tmp_path, adapter, monkeypatch):
    from rvw.farm import executor
    elf = tmp_path / 'test.elf'; elf.write_bytes(b'fail')
    manifest = tmp_path / 'manifest.jsonl'
    manifest.write_text(json.dumps({'elf': str(elf), 'config': 'test', 'seed': 4}))
    def crash(*args, **kwargs):
        raise KeyboardInterrupt('controller fixture')
    monkeypatch.setattr(executor, 'run_group', crash)
    monkeypatch.setattr(executor, 'cancel_host', lambda _: {'acknowledged': False})
    out = tmp_path / 'out'
    with pytest.raises(KeyboardInterrupt):
        execute([{'name': 'a', 'address': 'localhost'}], manifest, adapter,
                [*adapter, 'identity'], IDENTITY, out)
    report = executor.recover(out)
    assert report['status'] == 'inconclusive'
    assert report['plan'][0]['options']['seed'] == 4
    assert report['shards'][0]['missing_cells'] == ['0']


def test_native_limit_is_inherited_by_adapter_children(tmp_path):
    from rvw.farm.limits import command
    from rvw.common.proc import run_group
    code = 'import resource,json; print(json.dumps(resource.getrlimit(resource.RLIMIT_FSIZE)))'
    result = run_group(command([sys.executable, '-c',
        'import subprocess,sys; subprocess.run([sys.executable,"-c",sys.argv[1]],check=True)', code],
        {'file_bytes': 4096}), capture=True, timeout=5)
    assert result.returncode == 0
    assert json.loads(result.stdout) == [4096, 4096]


def test_native_file_limit_stops_oversize_write(tmp_path):
    from rvw.farm.limits import command
    from rvw.common.proc import run_group
    output = tmp_path / 'large'
    result = run_group(command([sys.executable, '-c',
        'import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(b"x"*8192)', str(output)],
        {'file_bytes': 1024}), capture=True, timeout=5)
    assert result.returncode != 0
    assert output.stat().st_size <= 1024


def test_native_limits_refuse_unsupported_or_bad_values(monkeypatch):
    from rvw.farm import limits
    for value in ({'cpu_seconds': True}, {'open_files': 0}, {'rss': 100}):
        with pytest.raises(ValueError):
            limits.validate(value)
    monkeypatch.setattr(limits.sys, 'platform', 'darwin')
    with pytest.raises(ValueError, match='unsupported'):
        limits.validate({'address_space_bytes': 1000000000})
