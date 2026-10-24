"""C8: named read boundaries must consume one captured input set."""
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from race_injection import race_injector
from rvw.perf import analysis, cli
from perf_fixtures import analyze


RAW = b'Kanata\t0004\nC=\t0\nI\t0\t0\t0\nC\t1\nR\t0\t0\t0\n'
OTHER = RAW.replace(b'C\t1', b'C\t9')


@pytest.mark.parametrize('compressed', [False, True])
@pytest.mark.parametrize('replace,revert,when', [(True, False, 'after'), (False, True, 'before')])
def test_trace_parse_and_hash_use_same_capture(tmp_path, race_injector, compressed, replace, revert, when):
    trace = tmp_path / ('trace.log.gz' if compressed else 'trace.log')
    raw, other = (gzip.compress(RAW), gzip.compress(OTHER)) if compressed else (RAW, OTHER)
    trace.write_bytes(raw)
    hook = race_injector.file(analysis, 'read', trace, other, when=when, replace=replace, revert=revert)
    report = analyze(trace)
    assert hook.fired
    assert report['summary']['cycles'] == 2
    assert report['trace_sha256'] == hashlib.sha256(raw).hexdigest()
    captured, = report['capture']['files']
    assert captured['resolved'] == str(trace)
    assert captured['sha256'] == report['trace_sha256']


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_counters_captured_before_trace_parse(tmp_path, race_injector, replace, revert):
    trace = tmp_path / 'trace.log'
    trace.write_bytes(RAW)
    result = tmp_path / 'result.json'
    counters = dict(schema='rvw.run/1', status='pass', cycles=2, instret=1,
                    artifacts={'konata': trace.name})
    result.write_text(json.dumps(counters))
    original = result.read_bytes()
    changed = json.dumps({**counters, 'cycles': 10}).encode()
    hook = race_injector.file(analysis, 'load_run', result, changed, when='before', replace=replace, revert=revert)
    report = analyze(trace)
    assert hook.fired
    assert report['cross_check']['exact_counter_match']
    assert report['cross_check']['artifact_matches']
    assert report['cross_check']['result_sha256'] == hashlib.sha256(original).hexdigest()


@pytest.mark.parametrize('saved', [False, True])
def test_compare_captures_both_inputs_before_first_analysis(tmp_path, race_injector, saved):
    base, candidate = tmp_path / 'base.log', tmp_path / 'candidate.log'
    base.write_bytes(RAW)
    candidate.write_bytes(RAW)
    if saved:
        first, second = analyze(base), analyze(candidate)
        base, candidate = base.with_suffix('.json'), candidate.with_suffix('.json')
        base.write_text(json.dumps(first))
        candidate.write_text(json.dumps(second))
        changed = json.loads(json.dumps(second))
        changed['summary']['cycles'] = 100
        replacement = json.dumps(changed).encode()
        target, boundary = json, 'load'
    else:
        target, boundary, replacement = analysis, 'read', OTHER
    hook = race_injector.file(target, boundary, candidate, replacement, when='after', replace=True)
    report = cli.execute_json(['compare', str(base), str(candidate)])
    assert hook.fired
    assert not report['differences']
    assert len(report['capture']['files']) == 2


def test_explicit_missing_counter_input_refuses(tmp_path):
    trace = tmp_path / 'trace.log'
    trace.write_bytes(RAW)
    with pytest.raises(ValueError, match='input_not_captured'):
        analyze(trace, result=tmp_path / 'missing.json')


def test_artifact_symlink_is_pinned_before_parsing(tmp_path, race_injector):
    trace, other, alias = tmp_path / 'trace.log', tmp_path / 'other.log', tmp_path / 'alias.log'
    trace.write_bytes(RAW)
    other.write_bytes(OTHER)
    alias.symlink_to(trace.name)
    (tmp_path / 'result.json').write_text(json.dumps(dict(schema='rvw.run/1', status='pass',
        cycles=2, instret=1, artifacts={'konata': alias.name})))
    def retarget():
        alias.unlink()
        alias.symlink_to(other.name)
    hook = race_injector.at(analysis, 'read', retarget, when='before')
    report = analyze(trace)
    assert hook.fired
    assert report['cross_check']['artifact_matches']
    assert len(report['capture']['files']) == 2


def test_c1_symlink_keeps_artifacts_relative_to_lookup_directory(tmp_path, race_injector):
    run, storage = tmp_path / 'run', tmp_path / 'storage'
    run.mkdir()
    storage.mkdir()
    trace = run / 'trace.log'
    trace.write_bytes(RAW)
    (storage / trace.name).write_bytes(OTHER)
    counters = dict(schema='rvw.run/1', status='pass', cycles=2, instret=1,
                    artifacts={'konata': trace.name})
    target = storage / 'counters.json'
    target.write_text(json.dumps(counters))
    (run / 'result.json').symlink_to(target)
    changed = json.dumps({**counters, 'cycles': 10}).encode()
    hook = race_injector.file(analysis, 'read', target, changed, when='before', replace=True)
    report = analyze(trace)
    assert hook.fired
    assert report['cross_check']['artifact_matches']
    assert report['cross_check']['exact_counter_match']
    assert any(f['symlinks'] for f in report['capture']['files'])


@pytest.mark.parametrize('declaration,expected', [(None, None), ('trace.log', True),
                                                  ('missing.log', False), ('other.log', False)])
def test_counter_artifact_association_keeps_three_states(tmp_path, declaration, expected):
    trace = tmp_path / 'trace.log'
    trace.write_bytes(RAW)
    (tmp_path / 'other.log').write_bytes(RAW)
    (tmp_path / 'result.json').write_text(json.dumps(dict(schema='rvw.run/1', status='pass',
        cycles=2, instret=1, artifacts={} if declaration is None else {'konata': declaration})))
    report = analyze(trace)
    assert report['cross_check']['artifact_matches'] is expected
    assert len(report['capture']['files']) == 2


@pytest.mark.parametrize('kind', ['broken_link', 'directory', 'fifo'])
def test_unreadable_declared_artifact_refuses(tmp_path, kind):
    import os
    trace, artifact = tmp_path / 'trace.log', tmp_path / 'artifact.log'
    trace.write_bytes(RAW)
    if kind == 'broken_link':
        artifact.symlink_to('missing.log')
    elif kind == 'directory':
        artifact.mkdir()
    else:
        os.mkfifo(artifact)
    (tmp_path / 'result.json').write_text(json.dumps(dict(schema='rvw.run/1', status='pass',
        cycles=2, instret=1, artifacts={'konata': artifact.name})))
    with pytest.raises((OSError, ValueError)):
        analyze(trace)
