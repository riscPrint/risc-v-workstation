"""Debug capture staging does not depend on writable runs or external output paths."""
import json
from pathlib import Path

import pytest

from race_injection import race_injector
from rvw import runs
from rvw.bisect.core import Bisector, Options
from rvw.bundle.make import Options as BundleOptions, make
from rvw.common.capture import Capture, CaptureError
from rvw.runs.inputs import DebugInputs
from test_debug_tools import CFG, fake_run, make_core


@pytest.mark.parametrize('entry', ['api', 'cli', 'mcp'])
def test_bundle_saved_artifacts_without_replay_source(tmp_path, monkeypatch, rvw, entry):
    import shutil
    from rvw.mcp.registry import Registry
    from rvw.results.generation import open_current
    from test_mcp_tools import call

    source = tmp_path / 'temporary-core'
    source.mkdir()
    (source / 'bug').touch()
    config = tmp_path / 'debug.toml'
    config.write_text(CFG + '\n[spinaltrace]\npdg = "/missing/model/pdg.json"\n'
                      'adapter = "/missing/model/adapter"\n')
    monkeypatch.setenv('RVW_CORE_CONFIG', str(config))
    run = fake_run(tmp_path / 'archive', '--seed', '9', '--wave', '--rvfi-trace',
                   env={'FAKE_CORE': str(source)})
    shutil.rmtree(source)
    out = tmp_path / 'bundle'
    if entry == 'api':
        report = make(str(run), BundleOptions(out=out, rerun=False, spinaltrace=False))
    elif entry == 'cli':
        rc, text, report = rvw('bundle', run, '--out', out, '--no-rerun', '--no-spinaltrace', '--json')
        assert rc == 0, text
    else:
        registry, problems = Registry.discover({'bundle'})
        assert not problems
        try:
            report = call(registry, 'bundle_make', run_dir=str(run), out=str(out),
                          no_rerun=True, no_spinaltrace=True)
        finally:
            registry.jobs.shutdown()
    assert report['signature'] == 'assert:lsu.scala:1241'
    assert report['progress']['last_cycle'] > 0
    assert report['wave']['covers_failure']
    assert report['replay'] is None and 'replay' not in report['files']
    assert any('replay unavailable' in note for note in report['notes'])
    assert not any('replay.sh' in command for command in report['next'])
    saved = open_current(out)
    assert json.loads(saved.read_bytes('summary.json'))['replay'] is None
    assert not (saved.path / 'replay.sh').exists()
    assert report['source'] == {} and not report['capture']['trees']
    with pytest.raises(CaptureError, match='input_not_captured'):
        make(str(run), BundleOptions(out=out, rerun=True, spinaltrace=False))
    assert open_current(out).id == saved.id


@pytest.mark.parametrize('ignored', [False, True])
def test_tools_capture_with_output_inside_checkout(tmp_path, monkeypatch, race_injector, ignored):
    repo, git = make_core(tmp_path)
    script = repo / 'RiscvSim/fake/run.sh'
    script.parent.mkdir(parents=True)
    script.write_text('#!/bin/bash\nexit 0\n')
    script.chmod(0o755)
    if ignored:
        (repo / '.gitignore').write_text('output/\n')
    run = fake_run(tmp_path / 'run', '--seed', '9')
    data = json.loads((run / 'result.json').read_text())
    data['replay'] = 'RiscvSim/fake/run.sh run'
    (run / 'result.json').write_text(json.dumps(data))
    monkeypatch.setattr('rvw.runs.inputs.tools_root', lambda: repo)
    inputs = DebugInputs()
    command = inputs.command(runs.open_run(run, capture=inputs.capture), {})
    hook = race_injector.file(inputs, 'publish', script, b'changed', replace=True)
    output = repo / 'output'
    output.mkdir(exist_ok=True)
    (output / 'summary.json').write_text('{}')
    inputs.publish(output, ['summary.json'])
    assert hook.fired
    assert not inputs.capture.root.is_relative_to(repo)
    saved = next(Path(arg) for arg in command.exe if arg.endswith('run.sh'))
    assert saved.read_text() == '#!/bin/bash\nexit 0\n'
    assert saved.exists() and (output / 'current').exists()


def test_bisect_read_only_archived_run(tmp_path, monkeypatch, race_injector):
    repo, git = make_core(tmp_path)
    config = tmp_path / 'debug.toml'
    config.write_text(CFG)
    monkeypatch.setenv('RVW_CORE_CONFIG', str(config))
    monkeypatch.setenv('RVW_NO_LOCK', '1')
    run = fake_run(tmp_path / 'archive', '--seed', '9', env={'FAKE_CORE': str(repo)})
    before = sorted(path.name for path in run.iterdir())
    hook = race_injector.at(DebugInputs, '__init__', lambda: run.chmod(0o555),
                           when='before', restore=lambda: run.chmod(0o755))
    bisector = Bisector(str(run), Options(good='HEAD~7', core_repo=str(repo), workdir=tmp_path / 'bisect'))
    report = bisector.bisect()
    assert hook.fired and report['result']['first_bad'] == git('rev-parse', 'HEAD~3')
    assert sorted(path.name for path in run.iterdir()) == before


def test_shared_overlap_guard_still_refuses(tmp_path):
    capture = Capture(tmp_path / 'inputs')
    with pytest.raises(CaptureError, match='overlap'):
        capture.tree(tmp_path, git=False)
