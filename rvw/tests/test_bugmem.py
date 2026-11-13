"""Bug-pattern memory: features, matching, duplicates and leave-one-out evaluation."""
import json
import subprocess
import sys

import pytest

from rvw.bugmem.memory import BugMemError, Store, features, score


def bundle(tmp_path, name, status='assert', message='assertion failed at lsu.scala:1241 store queue',
           unit='lsu', next_class='store', channel=None, traps=()):
    d = tmp_path / name
    d.mkdir()
    s = {'schema': 'rvw.bundle/1', 'status': status, 'signature': f'{status}:{message[-20:]}' if status != 'timeout' else 'timeout',
         'message': message, 'suspect': {'unit': unit, 'evidence': []},
         'progress': {'next_class': next_class, 'last_func': 'memcpy', 'recent_traps': [{'cause': c} for c in traps]},
         'handshakes': {'channels': {channel: {'stalled_cycles': 400}} if channel else {}}}
    (d / 'summary.json').write_text(json.dumps(s))
    return str(d)


def test_features_and_score(tmp_path):
    a = features(json.loads(open(bundle(tmp_path, 'a') + '/summary.json').read()))
    assert a['assert_file:lsu.scala'] == 3.0 and a['unit:lsu'] == 2.0 and 'msg:store' in a
    assert not any(k.startswith('msg:1241') for k in a)
    s, shared = score(a, a)
    assert s == 1.0 and shared
    assert score(a, {})[0] == 0.0


def test_add_match_and_duplicates(tmp_path):
    store = Store(tmp_path / 'mem.jsonl')
    e = store.add(bundle(tmp_path, 'old'), 'store queue drops a forwarded value', fix='spinal-boom abc123',
                  scope='riscv-tests rv64ui, small config', label='stq-forward')
    assert e['report']['sha256'] and e['cause'].startswith('store queue')
    with pytest.raises(BugMemError, match='already stored'):
        store.add(bundle(tmp_path, 'old2'), 'again')
    store.add(bundle(tmp_path, 'hang', status='timeout', message='no retirement', unit='frontend',
                     next_class='branch', channel='icache_a'), 'icache miss never refilled', label='icache')
    new = bundle(tmp_path, 'new', message='assertion failed at lsu.scala:1250 store queue')
    r = store.match(new)
    assert r['status'] == 'candidates' and r['candidates'][0]['label'] == 'stq-forward'
    assert 'assert_file:lsu.scala' in r['candidates'][0]['shared']
    assert all(c['label'] != 'icache' for c in r['candidates'])
    far = bundle(tmp_path, 'far', status='fail', message='wrong result', unit='alu', next_class='alu')
    assert store.match(far, min_score=0.5)['status'] == 'no_match'
    with pytest.raises(BugMemError, match='root cause'):
        store.add(far, ' ')


def test_evaluate(tmp_path):
    store = Store(tmp_path / 'mem.jsonl')
    for i in range(3):
        store.add(bundle(tmp_path, f'l{i}', message=f'assertion failed at lsu.scala:{1200 + i} store queue {i}'),
                  'stq', label='lsu')
    for i in range(2):
        store.add(bundle(tmp_path, f'f{i}', status='timeout', message=f'hang {"x" * i}', unit='frontend',
                         next_class='branch', channel='icache'), 'icache', label='fe')
    store.add(bundle(tmp_path, 'single', status='fail', message='bad', unit='alu', next_class='alu'), 'alu', label='alu')
    r = store.evaluate()
    assert r['labelled'] == 6 and r['held_out'] == 5 and r['unmatchable'] == 1
    assert r['top1_accuracy'] == 1.0


def test_cli_and_mcp(tmp_path):
    run = lambda *a: subprocess.run([sys.executable, '-m', 'rvw', 'bugmem', *a, '--store', str(tmp_path / 'm.jsonl')],
                                    capture_output=True, text=True)
    out = run('add', bundle(tmp_path, 'a'), '--cause', 'stq bug', '--label', 'lsu', '--json')
    assert out.returncode == 0, out.stderr
    out = run('match', bundle(tmp_path, 'b', message='assertion failed at lsu.scala:9 store queue'))
    assert out.returncode == 0 and 'stq bug' in out.stdout and 'not diagnosis' in out.stdout
    assert run('add', str(tmp_path / 'missing'), '--cause', 'x').returncode == 2
    from rvw.mcp.registry import Registry
    registry, problems = Registry.discover({'bugmem'})
    try:
        assert not problems
        _, data, error = registry.call_json('bugmem_list', {'store': str(tmp_path / 'm.jsonl')})
        assert not error and len(data['entries']) == 1
    finally:
        registry.jobs.shutdown()
