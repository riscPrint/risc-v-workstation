import pytest
from rvw.wave.mutations import statement_depth

pytestmark = pytest.mark.fast


def test_source_depth_follows_dependency_direction():
    graph = {'vertices': [{'assigns_to':'result', 'timestamp':4},
                          {'file':'src/Core.scala','line':10}, {'file':'src/Core.scala','line':20}],
             'edges':[{'from':0,'to':1}, {'from':1,'to':2}, {'from':2,'to':1}]}
    report = {'chains':[{'signal':'result','dynamic':{'graph':graph}}]}
    assert statement_depth(report, 'src/Core.scala', 20) == 2
    assert statement_depth(report, 'Other.scala', 20) is None
    assert statement_depth(report, 'other/Core.scala', 20) is None


def test_inactive_candidate_does_not_count():
    trace = {'active':2, 'assignments':[{'id':1,'loc':'Core.scala:10'}, {'id':2,'loc':'Core.scala:20'}]}
    report = {'chains':[{'driver_walk':{'trace':trace}}]}
    assert statement_depth(report,'Core.scala',10) is None
    assert statement_depth(report,'Core.scala',20) == 0


def test_private_source_restored_after_compile_exception(tmp_path, monkeypatch):
    from rvw.wave import mutations
    source = tmp_path / 'source'
    source.mkdir()
    path = source / 'Core.scala'
    path.write_text('original\n')
    def fail(*args, **kwargs):
        path.write_text('unexpected\n')
        raise RuntimeError('interrupted compile')
    monkeypatch.setattr(mutations, 'run_group', fail)
    with pytest.raises(RuntimeError):
        mutations.run_cases(source, [{'name':'one','file':'Core.scala','before':'original','after':'mutated'}],
                            [], [], work=tmp_path/'out', project='', db='', binding='', env={})
    assert path.read_text() == 'original\n'


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from rvw.wave import mutations
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'Core.scala').write_text('original')
    calls = []
    behavior = {'comparison': 'mismatch', 'trace': 'explained', 'incomplete': None,
                'returncode': 0, 'timeout': False}
    def command(argv, **kwargs):
        calls.append(argv)
        if argv == ['/bin/echo', 'compile']:
            kwargs['stdout'].write('/fake/scala-library.jar\n')
        else:
            run = __import__('pathlib').Path(argv[-1])
            run.mkdir()
            (run / 'result.json').write_text('{}')
            (run / 'wave.vcd').write_text('causal wave')
        return SimpleNamespace(returncode=behavior['returncode'], timed_out=behavior['timeout'])
    monkeypatch.setattr(mutations, 'run_group', command)
    def open_run(path):
        return SimpleNamespace(dir=path, inconclusive=behavior['incomplete'],
            get=lambda key: {} if key in ('artifacts', 'details') else 'pass', artifact=lambda key: path / 'wave.vcd' if key == 'wave' else None)
    monkeypatch.setattr(mutations, 'open_run', open_run)
    monkeypatch.setattr(mutations, 'compare', lambda *a: {'status': 'match', 'trace_complete': True})
    monkeypatch.setattr(mutations, 'explain_run', lambda *a, **k: {
        'status': behavior['trace'], 'cosim': {'status': behavior['comparison'], 'trace_complete': True}, 'chains': []})
    def run(**kwargs):
        return mutations.run_cases(source, [dict(name='one', file='Core.scala', before='original', after='mutated')],
            ['/bin/echo', 'compile'], ['/bin/echo', 'simulate', '{out}'], work=tmp_path/'out', project='', db='', binding='',
            env={}, **kwargs)
    return run, calls, behavior, source, tmp_path/'out'


@pytest.mark.parametrize('comparison,trace,expected', [
    ('inconclusive', 'inconclusive', 'comparison_inconclusive'),
    ('mismatch', 'inconclusive', 'tracing_unresolved'),
    ('match', 'inconclusive', 'no_mismatch'),
])
def test_preserve_comparison_and_trace_limits(campaign, comparison, trace, expected):
    run, calls, behavior, source, work = campaign
    behavior.update(comparison=comparison, trace=trace)
    assert run()[-1]['status'] == expected
    assert (source/'Core.scala').read_text() == 'original'


def test_incomplete_c1_stops_baseline(campaign):
    run, calls, behavior, source, work = campaign
    behavior['incomplete'] = 'missing trace'
    assert run()[0]['status'] == 'c1_incomplete'
    assert len(calls) == 2


@pytest.mark.parametrize('timeout,expected', [(True, 'build_timeout'), (False, 'build_error')])
def test_process_failures(campaign, timeout, expected):
    run, calls, behavior, source, work = campaign
    behavior.update(timeout=timeout, returncode=124 if timeout else 1)
    assert run()[0]['status'] == expected


def test_old_rows_and_partial_run_start_fresh(campaign):
    import json
    run, calls, behavior, source, work = campaign
    work.mkdir()
    (work/'baseline/run').mkdir(parents=True)
    (work/'baseline/run/result.json').write_text('{}')
    (work/'summary.json').write_text(json.dumps([{'name':'baseline','status':'baseline_match'},
                                               {'name':'one','status':'hit'}]))
    rows = run(resume=True)
    assert len(calls) == 4
    assert all(not row['native_reused'] for row in rows)
    assert (work/'baseline/run/result.json').read_text() == '{}'


def fake_identity(key):
    def identity(*args, evidence, **kwargs):
        import json
        evidence.mkdir()
        (evidence/'identity.json').write_text(json.dumps({'key': key()}))
        return key()
    return identity


def test_valid_native_reuse_rechecks_report(campaign, monkeypatch):
    from rvw.wave import mutations
    run, calls, behavior, source, work = campaign
    behavior['comparison'] = 'match'
    # Test evidence lifecycle separately from dependency enumeration below.
    monkeypatch.setattr(mutations, '_identity', fake_identity(lambda: 'complete-test-identity'))
    first = run()
    assert len(calls) == 4
    assert (work/first[1]['attempt']/'run/wave.vcd').read_text() == 'causal wave'
    behavior['comparison'] = 'inconclusive'
    second = run(resume=True)
    assert len(calls) == 4
    assert all(row['native_reused'] for row in second)
    assert second[-1]['status'] == 'comparison_inconclusive'


@pytest.mark.parametrize('damage', ['identity', 'wave', 'result', 'seal', 'summary_identity'])
def test_invalid_reuse_starts_fresh(campaign, monkeypatch, damage):
    from rvw.wave import mutations
    run, calls, behavior, source, work = campaign
    behavior['comparison'] = 'match'
    key = ['first']
    monkeypatch.setattr(mutations, '_identity', fake_identity(lambda: key[0]))
    first = run()
    if damage == 'identity':
        key[0] = 'changed'
    elif damage in ('seal', 'summary_identity'):
        import json
        data = json.loads((work/'summary.json').read_text())
        for row in data:
            if damage == 'seal':
                row.pop('sealed_generation')
            else:
                key[0] = 'changed'
                row['identity'] = 'changed'
        (work/'summary.json').write_text(json.dumps(data))
    else:
        for row in first:
            (work/row['attempt']/'run'/('wave.vcd' if damage == 'wave' else 'result.json')).unlink()
    second = run(resume=True)
    assert len(calls) == 8
    assert all(not row['native_reused'] for row in second)
    assert {r['attempt'] for r in first}.isdisjoint(r['attempt'] for r in second)


@pytest.mark.parametrize('changed', ['source', 'mutation', 'elf', 'project', 'db', 'binding',
                                      'build', 'tool', 'command', 'options', 'env'])
def test_identity_binds_dependencies(tmp_path, changed):
    from rvw.wave.mutations import _identity
    source = tmp_path/'source'
    source.mkdir()
    (source/'Core.scala').write_text('original')
    for name in ('elf', 'project', 'db', 'binding', 'build'):
        (tmp_path/name).write_text(name)
    tool = tmp_path/'tool'
    tool.write_text('#!/bin/sh\nexit 0\n')
    tool.chmod(0o700)
    case = dict(name='one', file='Core.scala', before='original', after='mutated')
    options = dict(project=tmp_path/'project', db=tmp_path/'db', binding=tmp_path/'binding',
                   elf=tmp_path/'elf', env={}, compile_cwd=source, window=80,
                   build_inputs=[tmp_path/'build'], native_tools=[str(tool)], inputs_complete=True)
    command = ['/bin/echo']
    def identity(label):
        return _identity(source, case, command, ['/bin/echo'], evidence=tmp_path/label, **options)
    first = identity('first')
    assert first and first == identity('stable')
    if changed == 'source':
        (source/'Core.scala').write_text('changed')
    elif changed == 'mutation':
        case['after'] = 'other'
    elif changed == 'tool':
        tool.write_text('#!/bin/sh\nexit 1\n')
    elif changed == 'command':
        command.append('new-option')
    elif changed == 'options':
        options['window'] = 90
    elif changed == 'env':
        options['env'] = {'SETTING': 'changed'}
    else:
        (tmp_path/changed).write_text('changed')
    assert identity('changed') != first


@pytest.mark.parametrize('stage', ['compile', 'simulate'])
def test_simulation_and_build_timeouts(campaign, monkeypatch, stage):
    from rvw.wave import mutations
    from rvw.common.proc import Result
    run, calls, behavior, source, work = campaign
    original = mutations.run_group
    def command(argv, **kwargs):
        if argv[1] == stage:
            return Result(124, timed_out=True)
        return original(argv, **kwargs)
    monkeypatch.setattr(mutations, 'run_group', command)
    assert run()[0]['status'] == ('build_timeout' if stage == 'compile' else 'simulation_timeout')
    assert (source/'Core.scala').read_text() == 'original'


def test_match_without_complete_trace_is_inconclusive():
    from rvw.wave.mutations import _verdict
    assert _verdict({'cosim': {'status':'match'}}, {}, 1)['status'] == 'comparison_inconclusive'


def test_simulation_error_is_not_comparison(campaign, monkeypatch):
    from rvw.wave import mutations
    from rvw.common.proc import Result
    run, calls, behavior, source, work = campaign
    original = mutations.run_group
    monkeypatch.setattr(mutations, 'run_group', lambda argv, **kw:
        Result(1) if argv[1] == 'simulate' else original(argv, **kw))
    assert run()[0]['status'] == 'simulation_error'


def test_missing_c1_is_not_compared(campaign, monkeypatch):
    from rvw.wave import mutations
    run, calls, behavior, source, work = campaign
    def missing(path):
        raise ValueError('partial C1')
    monkeypatch.setattr(mutations, 'open_run', missing)
    assert run()[0]['status'] == 'c1_incomplete'


def test_external_causal_artifact_disables_reuse(campaign, monkeypatch):
    from rvw.wave import mutations
    run, calls, behavior, source, work = campaign
    behavior['comparison'] = 'match'
    monkeypatch.setattr(mutations, '_identity', fake_identity(lambda: 'complete-test-identity'))
    original = mutations.open_run
    external = source.parent/'external.pdg'
    external.write_text('causal data outside attempt')
    def open_run(path):
        result = original(path)
        artifact = result.artifact
        result.artifact = lambda name: external if name == 'pdg' else artifact(name)
        return result
    monkeypatch.setattr(mutations, 'open_run', open_run)
    run()
    second = run(resume=True)
    assert len(calls) == 8
    assert not any(row['native_reused'] for row in second)


def test_failed_c1_cannot_earn_baseline_match(campaign, monkeypatch):
    from rvw.wave import mutations
    run, calls, behavior, source, work = campaign
    original = mutations.open_run
    def failed(path):
        result = original(path)
        get = result.get
        result.get = lambda key: 'fail' if key == 'status' else get(key)
        return result
    monkeypatch.setattr(mutations, 'open_run', failed)
    assert run()[0]['status'] == 'baseline_c1_failed'
    assert len(calls) == 2
