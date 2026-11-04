import json
from pathlib import Path

import pytest
from rvw.cli import main
from rvw.common.project import load_project
from rvw.common.proc import run_group
from rvw.doctor import check
from rvw.init.scaffold import scaffold
from rvw.regress.config import load_config
from types import SimpleNamespace


@pytest.fixture
def core(tmp_path):
    root = tmp_path / 'mycore'
    root.mkdir()
    (root / 'build.sbt').write_text('val spinalVersion = "1.15.0"\n// spinalhdl-core\n')
    source = root / 'src/main/scala'
    source.mkdir(parents=True)
    (source / 'Top.scala').write_text('import spinal.core._\nclass Top extends Component {}\n// rv32im\n')
    return root


def test_dry_run_writes_nothing(core):
    before = sorted(core.rglob('*'))
    result = scaffold(core, dry_run=True)
    assert result['status'] == 'planned'
    assert 'rvw.toml' in result['files'] and 'rvw/run.sh' in result['files']
    assert result['spinal_versions'] == ['1.15.0']
    assert result['candidate_tops'] == ['Top']
    assert result['xlen'] == 32
    assert sorted(core.rglob('*')) == before


def test_created_project_and_fail_closed_launcher(core):
    result = scaffold(core)
    assert result['status'] == 'created'
    project = load_project(core)
    config = load_config(project=core)
    assert project.name == 'mycore' and config.default_config == 'default'
    assert not config.input_complete and not config.identity_capture
    info = run_group([str(core / 'rvw/run.sh'), 'info', '--json'], capture=True)
    assert info.returncode == 0 and json.loads(info.stdout)['xlen'] == 32
    build = run_group([str(core / 'rvw/run.sh'), 'build', '--config', 'default', '--json'], capture=True)
    assert build.returncode == 2 and 'not implemented' in build.stderr
    run = run_group([str(core / 'rvw/run.sh'), 'run'], capture=True)
    assert run.returncode == 2
    assert '/out/' in (core / 'rvw/.gitignore').read_text()


def test_overwrite_preflight_and_force(core):
    (core / 'rvw').mkdir()
    (core / 'rvw/README.md').write_text('existing')
    with pytest.raises(ValueError, match='Refusing to overwrite'):
        scaffold(core)
    assert not (core / 'rvw.toml').exists()
    assert (core / 'rvw/README.md').read_text() == 'existing'
    report = scaffold(core, force=True, dry_run=True)
    assert report['overwritten'] == ['rvw/README.md']
    assert (core / 'rvw/README.md').read_text() == 'existing'
    scaffold(core, force=True)
    assert (core / 'rvw.toml').is_file()


def test_blocked_parent_preflight(core):
    (core / 'rvw').write_text('file')
    with pytest.raises(ValueError, match='Parent is not a directory'):
        scaffold(core)
    assert not (core / 'rvw.toml').exists()


@pytest.mark.parametrize('kwargs', [{'isa': 'bad'}, {'isa': 'rv64im', 'xlen': 32}, {'name': '../bad'}])
def test_invalid_inputs(core, kwargs):
    with pytest.raises(ValueError):
        scaffold(core, **kwargs)
    assert not (core / 'rvw.toml').exists()


def test_no_guessed_isa_or_non_spinal(tmp_path, core):
    with pytest.raises(ValueError, match='Minimal supported path'):
        scaffold(tmp_path)
    (core / 'src/main/scala/Top.scala').write_text('class Top extends Component {}')
    with pytest.raises(ValueError, match='Supply --isa'):
        scaffold(core)
    assert scaffold(core, isa='rv64im')['xlen'] == 64


def test_doctor_reports_remaining_actions(core, monkeypatch):
    scaffold(core)
    actual = check.run_group
    def runner(cmd, **kwargs):
        if cmd[0] == 'bash':
            return SimpleNamespace(returncode=0, stdout='PRESENT Python: 3.13\n', stderr='')
        return actual(cmd, **kwargs)
    monkeypatch.setattr(check, 'run_group', runner)
    result = check.diagnose(project=core)
    checks = {c['name']: c for c in result['checks']}
    assert checks['project']['status'] == 'ready'
    assert checks['adapter.info']['status'] == 'ready'
    assert checks['adapter.build_run']['status'] == 'inconclusive'
    assert checks['suite.smoke']['status'] == 'error'
    assert checks['gate.inputs']['status'] == 'inconclusive'
    assert result['exit_code'] == 1
    result = check.diagnose(project=core, smoke_elf=core / 'missing.elf')
    assert next(c for c in result['checks'] if c['name'] == 'adapter.build_run')['status'] == 'error'


def test_cli_json(core, capsys):
    assert main(['init', str(core), '--isa', 'rv32im', '--dry-run', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'planned'
    assert main(['init', str(core), '--isa', 'bad', '--json']) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'error'
