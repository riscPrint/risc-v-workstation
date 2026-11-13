"""Fast adapter contract checks with an executable bench fixture, no simulator."""
import json
from pathlib import Path
import pytest
from rvw.uvm import flow
from rvw.results import load_results, load_run
from rvw.sim.uvm import sha


def manifest(tmp_path, **extra):
    (tmp_path / 'top.sv').write_text('module top; endmodule')
    obj = dict(schema='rvw.uvm/1', name='fixture', top='top', sources=['top.sv'], tests=['smoke'])
    obj.update(extra)
    p = tmp_path / 'bench.json'
    p.write_text(json.dumps(obj))
    return p


def binary_fixture(tmp_path, text='RVW_UVM_DONE smoke checks=8', code=0):
    p = manifest(tmp_path)
    build = tmp_path / 'build'
    (build / 'obj').mkdir(parents=True)
    binary = build / 'obj/simulation'
    binary.write_text(f'#!/bin/sh\nprintf "%s\\n" "{text}"\nexit {code}\n')
    binary.chmod(0o755)
    (build / 'build.json').write_text(json.dumps(dict(status='pass', manifest=flow.load(p),
        input_sha256={str(p): sha(p)}, binary_sha256=sha(binary))))
    return build


def test_load_resolves_sources(tmp_path):
    p = manifest(tmp_path)
    assert flow.load(p)['sources'] == [str(tmp_path / 'top.sv')]


@pytest.mark.parametrize('extra', [dict(tests=[]), dict(tests=['x','x']), dict(plusargs=['+UVM_TESTNAME=x']), dict(bindings=[]), dict(schema='x')])
def test_invalid_manifest(tmp_path, extra):
    with pytest.raises(ValueError): flow.load(manifest(tmp_path, **extra))


@pytest.mark.parametrize('text,code,timed,status', [
    ('RVW_UVM_DONE smoke checks=2',0,False,'pass'),
    ('RVW_UVM_DONE smoke checks=0',0,False,'error'),
    ('RVW_UVM_DONE other checks=2',0,False,'error'),
    ('UVM_FATAL : 1\nRVW_UVM_DONE smoke checks=2',0,False,'fail'),
    ('UVM_ERROR @ 3: error',0,False,'fail'),
    ('UVM_ERROR : 0\nUVM_FATAL : 0\nRVW_UVM_DONE smoke checks=2',0,False,'pass'),
    ('RVW_UVM_DONE smoke checks=2',1,False,'fail'),
    ('RVW_UVM_DONE smoke checks=2',0,True,'timeout'),
    ('RVW_UVM_DONE smoke checks=2\nRVW_UVM_DONE smoke checks=2',0,False,'error'),
])
def test_completion(text, code, timed, status):
    assert flow.evidence(text,'smoke',code,timed)[0] == status


def test_regress_c1_c3(tmp_path):
    build = binary_fixture(tmp_path)
    report = flow.regress(build, tmp_path / 'runs', seeds=[1,31])
    assert len(report['tests']) == 2
    assert len(load_results(tmp_path / 'runs').tests) == 2
    assert load_run(tmp_path / 'runs/smoke-31').status == 'pass'
    assert '+verilator+seed+31' in json.loads((tmp_path / 'runs/smoke-31/result.json').read_text())['command']


def test_zero_exit_without_checks_is_inconclusive(tmp_path):
    build = binary_fixture(tmp_path, text='finished')
    report = flow.run(build, tmp_path / 'run', test='smoke')
    assert report['status'] == 'error' and report['inconclusive']


def test_changed_input_refused(tmp_path):
    build = binary_fixture(tmp_path)
    (tmp_path / 'bench.json').write_text('{}')
    with pytest.raises(ValueError, match='inputs changed'):
        flow.run(build, tmp_path / 'run', test='smoke')


def test_changed_binary_refused(tmp_path):
    build = binary_fixture(tmp_path)
    (build / 'obj/simulation').write_text('changed')
    with pytest.raises(ValueError, match='binary changed'):
        flow.run(build, tmp_path / 'run', test='smoke')


def test_unknown_test_refused(tmp_path):
    build = binary_fixture(tmp_path)
    with pytest.raises(ValueError, match='not declared'):
        flow.regress(build, tmp_path / 'run', tests=['absent'])


def test_feature_table_missing_is_not_support(tmp_path):
    from rvw.uvm.features import table, markdown
    build = binary_fixture(tmp_path)
    flow.regress(build, tmp_path / 'runs')
    report = table(tmp_path / 'runs')
    assert all(r['status'] == 'not established' for r in report['features'])
    assert '| Feature |' in markdown(report)


def test_cli_paths():
    from rvw.cli import build_parser
    parser = build_parser()
    assert parser.parse_args(['uvm','list','bench.json']).action == 'list'
    assert parser.parse_args(['regress','uvm','--out','run']).out == Path('run')


def test_build_command_and_pin(tmp_path, monkeypatch):
    from types import SimpleNamespace
    manifest_path = manifest(tmp_path, build_args=['-CFLAGS','-DUSER_DPI=1'])
    library = tmp_path / 'library'
    (library / 'src').mkdir(parents=True)
    monkeypatch.setattr(flow.shutil, 'which', lambda _: '/bin/verilator')
    monkeypatch.setattr(flow.uvm, 'unpack', lambda archive, out: library)
    commands = []
    def execute(command, **kwargs):
        commands.append(command)
        out = Path(command[command.index('--Mdir')+1])
        out.mkdir()
        (out / 'simulation').write_text('fixture')
        return SimpleNamespace(returncode=0, timed_out=False)
    monkeypatch.setattr(flow, 'run_group', execute)
    result = flow.build(manifest_path, tmp_path / 'build', archive=tmp_path / 'archive')
    assert result['status'] == 'pass'
    assert result['uvm_commit'] == flow.uvm.COMMIT
    assert '+define+UVM_NO_DPI' in commands[0]
    assert '-DUSER_DPI=1' in commands[0]
    assert 'coveragep()->write' in (tmp_path / 'build/main.cpp').read_text()


def test_coverage_merge_command(tmp_path, monkeypatch):
    from types import SimpleNamespace
    inputs = [tmp_path / 'one.dat', tmp_path / 'two.dat']
    for p in inputs: p.write_text('native coverage')
    out = tmp_path / 'merged.dat'
    def execute(command, **kwargs):
        assert command == ['verilator_coverage','--write',str(out),*map(str,inputs)]
        out.write_text('merged')
        return SimpleNamespace(returncode=0, timed_out=False)
    monkeypatch.setattr(flow, 'run_group', execute)
    assert flow.coverage_merge(inputs, out)['sha256'] == sha(out)
    with pytest.raises(ValueError, match='exists'): flow.coverage_merge(inputs, out)


def test_regression_preserves_wall_timeout(tmp_path, monkeypatch):
    from types import SimpleNamespace
    build = binary_fixture(tmp_path)
    def execute(command, **kwargs):
        kwargs['stdout'].write('RVW_UVM_DONE smoke checks=8\n')
        return SimpleNamespace(returncode=124,timed_out=True)
    monkeypatch.setattr(flow,'run_group',execute)
    report=flow.regress(build,tmp_path/'runs')
    assert report['tests'][0]['status']=='timeout'
    assert report['tests'][0]['wall_clock_timeout'] is True
    assert report['tests'][0]['signature']=='timeout:wall-clock'
