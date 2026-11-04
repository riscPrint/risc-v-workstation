"""C8 debug races at named read boundaries. No scheduling sleeps."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from race_injection import race_injector
from rvw import runs
from rvw.bundle.make import Options as BOpts, make
from rvw.reduce.core import Options as ROpts, Reducer
from rvw.runs import adapter
from rvw.wave import cli, mcp_tools, ops, vcd
from test_debug_tools import CFG, fake_run, make_core
from test_wave import VCD


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_NO_LOCK', '1')
    monkeypatch.setenv('RVW_NO_RUN_MANY', '1')
    monkeypatch.delenv('FAKE_CORE', raising=False)
    cfg = tmp_path / 'debug.toml'
    cfg.write_text(CFG)
    monkeypatch.setenv('RVW_CORE_CONFIG', str(cfg))






def source_adapter(run, tmp_path):
    wrapper = tmp_path / 'source_adapter.py'
    wrapper.write_text(
        "import hashlib,json,os,sys\nfrom pathlib import Path\n"
        "args=sys.argv[2:]; opts={}; i=0\n"
        "while i<len(args):\n"
        " key=args[i]\n"
        " if key in ('--wave','--rvfi-trace','--konata'): opts[key]=True; i+=1\n"
        " else: opts[key]=args[i+1]; i+=2\n"
        "failed=(Path(os.environ['FAKE_CORE'])/'f').read_text()=='8'\n"
        "elf=opts['--elf']; out=Path(opts['--out'])\n"
        "data={'schema':'rvw.run/1','core':'fake','status':'assert' if failed else 'pass',"
        "'cycles':700 if failed else 80,'message':'Assertion failed (lsu.scala:1241)',"
        "'elf':elf,'elf_sha256':hashlib.sha256(Path(elf).read_bytes()).hexdigest()}\n"
        "data.update(config=opts.get('--config','small'),seed=int(opts.get('--seed',1)),"
        "max_cycles=int(opts.get('--max-cycles',200000)),"
        "mem_latency=int(opts['--mem-latency']) if '--mem-latency' in opts else None)\n"
        "(out/'result.json').write_text(json.dumps(data))\n")
    import shlex
    import sys
    result = json.loads((run / 'result.json').read_text())
    result['replay'] = shlex.join([sys.executable, str(wrapper), 'run'])
    (run / 'result.json').write_text(json.dumps(result))

@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_bundle_wave_is_captured_before_coverage_and_cut(tmp_path, race_injector, replace, revert):
    run = fake_run(tmp_path / 'run', '--seed', '9', '--mem-latency', '1', '--wave', '--rvfi-trace')
    wave = run / 'wave.vcd'
    old = wave.read_bytes()
    # A valid but much shorter replacement capture.
    short = old[:old.index(b'#1000\n')]
    hook = race_injector.file(ops, 'cut', wave, short, replace=replace, revert=revert)
    report = make(str(run), BOpts(out=tmp_path / 'bundle', rerun=False, spinaltrace=False))
    assert hook.fired and report['wave']['covers_failure']
    assert report['snapshot'][0]['values']['count'] == hex(700)
    record = report['capture']
    assert any(f['sha256'] == hashlib.sha256(old).hexdigest() for f in record['files'])


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_reduce_core_is_captured_for_trials_and_saved_replay(tmp_path, monkeypatch, race_injector, replace, revert):
    repo, git = make_core(tmp_path)
    monkeypatch.setenv('FAKE_CORE', str(repo))
    run = fake_run(tmp_path / 'run', '--seed', '9', '--mem-latency', '1')
    source_adapter(run, tmp_path)
    hook = race_injector.file(adapter, 'execute_many', repo / 'f', b'changed',
                             replace=replace, revert=revert)
    report = Reducer(str(run), ROpts(out=tmp_path / 'reduce', modes=['cycles', 'seeds'], seeds=2)).reduce()
    assert hook.fired and report['reproduced']
    assert all(t['match'] for t in report['trials'])
    cmd = adapter.parse_replay(report['best']['replay'])
    assert Path(cmd.env['FAKE_CORE']) != repo
    assert adapter.execute(cmd, tmp_path / 'replay').run.get('status') == 'assert'
    assert report['capture']['trees']


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
@pytest.mark.parametrize('kind', ['rvfi_trace', 'konata', 'pdg', 'result'])
def test_bundle_artifact_reads_use_one_capture(tmp_path, race_injector, replace, revert, kind, monkeypatch):
    maker = importlib.import_module('rvw.bundle.make')
    run = fake_run(tmp_path / 'run', '--seed', '9', '--mem-latency', '1', '--wave', '--rvfi-trace')
    result = json.loads((run / 'result.json').read_text())
    if kind == 'rvfi_trace':
        path = run / 'rvfi.jsonl'
        target, attribute = maker.trace, 'read_rvfi_tail'
        replacement = b'{"schema":"rvw.rvfi/1"}\n'
    elif kind == 'konata':
        path = run / 'konata.log'
        path.write_text('Kanata\t0004\nC=\t0\nI\t1\t1\t0\nL\t1\t0\tpc: old\nC=\t10\n')
        result['artifacts']['konata'] = 'konata.log'
        target, attribute = maker.trace, 'konata_inflight'
        replacement = b'Kanata\t0004\nC=\t0\n'
    elif kind == 'pdg':
        path = run / 'pdg.json'
        path.write_text('{"vertices":[{"file":"lsu.scala","line":1241}]}')
        result['artifacts']['pdg'] = 'pdg.json'
        # A local CLI fixture exercises PDG lookup before invoking the external tracer.
        tracer = tmp_path / 'tracer'
        tracer.write_text('#!/bin/sh\nexit 0\n')
        tracer.chmod(0o755)
        monkeypatch.setenv('SPINALTRACE_CLI', str(tracer))
        target, attribute = maker, 'pdg_lines'
        replacement = b'{"vertices":[]}'
    else:
        path = run / 'result.json'
        target, attribute = importlib.import_module('rvw.runs.result'), '_open_read'
        replacement = json.dumps({**result, 'message': 'other.scala:1'}).encode()
    (run / 'result.json').write_text(json.dumps(result))
    original = path.read_bytes()
    hook = race_injector.file(target, attribute, path, replacement, replace=replace, revert=revert)
    report = make(str(run), BOpts(out=tmp_path / 'bundle', rerun=False, spinaltrace=kind == 'pdg'))
    assert hook.fired
    assert any(f['sha256'] == hashlib.sha256(original).hexdigest() for f in report['capture']['files'])
    if kind == 'rvfi_trace':
        assert report['progress']['last_cycle'] == 699
    elif kind == 'konata':
        assert report['inflight_total'] == 1
    elif kind == 'pdg':
        assert report['dynpdg']['criterion'] == 'line:lsu.scala:1241'
    else:
        assert report['signature'] == 'assert:lsu.scala:1241'


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_bisect_refs_resolve_before_clone(tmp_path, monkeypatch, race_injector, replace, revert):
    from rvw.bisect.core import Bisector, Options
    repo, git = make_core(tmp_path)
    good = git('rev-parse', 'HEAD~7')
    bad = git('rev-parse', 'HEAD')
    run = fake_run(tmp_path / 'run', '--seed', '9', env={'FAKE_CORE': str(repo)})
    # Move a requested symbolic ref after the name-resolution boundary.
    ref = repo / '.git' / git('symbolic-ref', 'HEAD')
    hook = race_injector.file(Bisector, 'prepare', ref, (good + '\n').encode(),
                             replace=replace, revert=revert)
    report = Bisector(str(run), Options(good=good, bad='HEAD', core_repo=str(repo), workdir=tmp_path / 'bisect')).bisect()
    assert hook.fired
    assert report['good'] == good and report['bad'] == bad
    assert report['result']['first_bad'] == git('rev-parse', bad + '~3')
    assert all(step['source_capture']['trees'] for step in report['steps'])


def test_published_bundle_generation_survives_replacement(tmp_path, race_injector):
    from rvw.results.generation import open_current
    run = fake_run(tmp_path / 'run', '--seed', '9', '--mem-latency', '1', '--wave', '--rvfi-trace')
    out = tmp_path / 'bundle'
    make(str(run), BOpts(out=out, rerun=False, spinaltrace=False))
    reader = open_current(out)
    original = reader.read_bytes('wave-window.vcd')
    # Replace the compatibility output during the next build. Its staged output stays private.
    hook = race_injector.file(ops, 'cut', out / 'wave-window.vcd', b'not a waveform', replace=True)
    make(str(run), BOpts(out=out, rerun=False, spinaltrace=False, cut_cycles=20))
    assert hook.fired
    current = open_current(out)
    assert current.id != reader.id
    assert reader.read_bytes('wave-window.vcd') == original
    assert current.read_bytes('wave-window.vcd') == (out / 'wave-window.vcd').read_bytes()
    assert current.read_bytes('wave-window.vcd') != b'not a waveform'


def test_bisect_reads_pinned_reduce_generation(tmp_path, race_injector):
    from rvw.bisect.core import Bisector, Options
    from rvw.results.generation import open_current
    repo, git = make_core(tmp_path)
    run = fake_run(tmp_path / 'run', '--seed', '9', env={'FAKE_CORE': str(repo)})
    report = Reducer(str(run), ROpts(out=tmp_path / 'reduce', modes=['cycles'])).reduce()
    generation = open_current(tmp_path / 'reduce')
    best = report['best']['dir']
    root_report = tmp_path / 'reduce' / 'reduce.json'
    changed = json.loads(root_report.read_text())
    changed['original']['max_cycles'] = 1
    # Old clients can replace the compatibility file without changing the pinned generation.
    hook = race_injector.file(Bisector, '_max_cycles', root_report, json.dumps(changed).encode(), replace=True)
    bisector = Bisector(best, Options(good='HEAD~7', core_repo=str(repo), workdir=tmp_path / 'bisect'))
    assert hook.fired and bisector.max_cycles == 200000
    assert bisector.parent_generation == generation.id


def test_bisect_final_replay_keeps_first_bad_source(tmp_path, race_injector):
    from rvw.bisect.core import Bisector, Options
    repo, git = make_core(tmp_path)
    run = fake_run(tmp_path / 'run', '--seed', '9', env={'FAKE_CORE': str(repo)})
    hook = race_injector.at(Bisector, '_found', lambda: (repo / 'bug').unlink(), when='after')
    report = Bisector(str(run), Options(good='HEAD~7', core_repo=str(repo), workdir=tmp_path / 'bisect')).bisect()
    assert hook.fired and report['result']['replay_tested']
    replay = adapter.parse_replay(report['command'])
    assert (Path(replay.env['FAKE_CORE']) / 'f').read_text() == '5'
    assert adapter.execute(replay, tmp_path / 'replay').run.get('status') == 'assert'


def test_bisect_capture_failure_skips_even_with_other_good(tmp_path, race_injector):
    from rvw.bisect.core import Bisector, Options
    repo, git = make_core(tmp_path)
    run = fake_run(tmp_path / 'run', '--seed', '9', env={'FAKE_CORE': str(repo)})
    work = tmp_path / 'bisect'
    def remove_artifact():
        for directory in (work / 'runs').iterdir():
            (directory / 'run.log').unlink()
    hook = race_injector.at(adapter, '_collect', remove_artifact, when='before')
    report = Bisector(str(run), Options(good='HEAD~7', core_repo=str(repo), workdir=work, other='good')).bisect()
    assert hook.fired and not report['result'].get('first_bad')
    assert report['steps'][0]['verdict'] == 'skip'
    assert 'input_not_captured:' in report['steps'][0]['hang']


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_symbol_trials_capture_each_generated_elf(tmp_path, monkeypatch, race_injector, replace, revert):
    from rvw.runs.elf import Elf
    monkeypatch.setenv('FAKE_SYMBOL', 'limit>=7')
    run = fake_run(tmp_path / 'run', '--seed', '9')
    out = tmp_path / 'reduce'
    state = {}
    def change():
        path = next(out.glob('*.limit=*'))
        state.update(path=path, data=path.read_bytes())
        elf = Elf(str(path))
        elf.write_int('limit', 0)
        target = out / 'replacement.elf' if replace else path
        elf.save(str(target))
        if replace:
            target.replace(path)
    hook = race_injector.at(adapter, 'execute_many', change, when='before',
                           restore=(lambda: state['path'].write_bytes(state['data'])) if revert else None)
    report = Reducer(str(run), ROpts(out=out, modes=['symbols'], symbols=['limit'], monotone=True)).reduce()
    assert hook.fired and report['symbols']['limit']['smallest_failing'] == 7
    for trial in report['trials']:
        assert Elf(trial['elf']).read_int('limit') == trial['symbols']['limit']


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_run_many_captures_its_generated_manifest(tmp_path, monkeypatch, race_injector, replace, revert):
    import sys
    from test_debug_tools import FAKE, SYMS_ELF
    monkeypatch.delenv('RVW_NO_RUN_MANY')
    command = adapter.Command(exe=[sys.executable, FAKE], opts={'--elf': SYMS_ELF, '--seed': '9'})
    state = {}
    def change():
        path = next(tmp_path.glob('manifest-*.jsonl'))
        state.update(path=path, data=path.read_bytes())
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]['seed'] = 1
        data = ''.join(json.dumps(row) + '\n' for row in rows)
        target = tmp_path / 'replacement.jsonl' if replace else path
        target.write_text(data)
        if replace:
            target.replace(path)
    hook = race_injector.at(adapter, 'run_group', change, when='before',
                           restore=(lambda: state['path'].write_bytes(state['data'])) if revert else None)
    attempts = adapter.execute_many([command, command.set(seed=1)], [tmp_path / 'a', tmp_path / 'b'])
    assert hook.fired and attempts[0].run.get('status') == 'assert'
    assert attempts[1].run.get('status') == 'pass'


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_bundle_core_is_captured_for_rerun_and_replay(tmp_path, monkeypatch, race_injector, replace, revert):
    repo, git = make_core(tmp_path)
    monkeypatch.setenv('FAKE_CORE', str(repo))
    run = fake_run(tmp_path / 'run', '--seed', '9', '--mem-latency', '1')
    source_adapter(run, tmp_path)
    hook = race_injector.file(adapter, 'execute', repo / 'f', b'changed', replace=replace, revert=revert)
    report = make(str(run), BOpts(out=tmp_path / 'bundle', spinaltrace=False))
    assert hook.fired and report['rerun']['reproduced']
    replay = adapter.parse_replay(report['replay'])
    assert Path(replay.env['FAKE_CORE']) != repo
    assert adapter.execute(replay, tmp_path / 'replay').run.get('status') == 'assert'
