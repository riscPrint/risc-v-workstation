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


def test_optional_scaffolds_are_planned_and_loadable(core):
    from rvw.cosim.platform import Platform
    (core / 'build.sbt').write_text('val spinalVersion = "1.15.0"\nlazy val cpu = (project in file("."))\n')
    linker = core / 'memory.ld'
    linker.write_text('MEMORY { ram (rwx) : ORIGIN = 0x80000000, LENGTH = 64K }')
    options = dict(wire_build=True, linker_script=linker, reset_pc='0x80000000', db_top='demo.Top')
    report = scaffold(core, dry_run=True, **options)
    assert not (core / 'rvw.toml').exists()
    assert 'ProjectRef(coreSource, "cpu")' in report['files']['rvw/build.sbt']
    assert 'SpinalDB/spinaldb' in report['files']['rvw/build.sbt']
    assert 'with-lock.sh" sbt-mycore nice -n 10' in report['files']['rvw/build-db.sh']
    scaffold(core, **options)
    project = load_project(core)
    assert project.get('cosim', 'platform') == core / 'rvw/cosim.json'
    assert project.get('query', 'db') == core / 'rvw/out/design.db'
    assert (core / 'rvw/build-db.sh').stat().st_mode & 0o111
    platform = json.loads((core / 'rvw/cosim.json').read_text())
    assert platform['ram'] == [{'base': '0x80000000', 'size': '0x10000'}]
    with pytest.raises(ValueError, match='Review the scaffold'):
        Platform.load('mycore', core / 'rvw/cosim.json')
    with pytest.raises(ValueError, match='Refusing to overwrite'):
        scaffold(core, **options)


@pytest.mark.parametrize('memory,options,pattern', [
    ('MEMORY { rom : ORIGIN = 0, LENGTH = 4K ram : ORIGIN = 4096, LENGTH = 8K }', {}, '--ram-region'),
    ('MEMORY { ram : ORIGIN = BASE, LENGTH = 4K }', {}, 'literal'),
    ('MEMORY { ram : ORIGIN = 0, LENGTH = 4K }', {'reset_pc': None}, '--reset-pc'),
    ('MEMORY { ram : ORIGIN = 0, LENGTH = 4K }', {'reset_pc': '4096'}, 'inside selected RAM'),
    ('MEMORY { ram : ORIGIN = 0, LENGTH = 0 }', {}, 'inside selected RAM'),
])
def test_linker_inputs_refuse_guessing(core, memory, options, pattern):
    linker = core / 'memory.ld'
    linker.write_text(memory)
    with pytest.raises(ValueError, match=pattern):
        scaffold(core, linker_script=linker, **({'reset_pc': '0'} | options))
    assert not (core / 'rvw.toml').exists()


def test_explicit_ram_selection(core):
    linker = core / 'memory.ld'
    linker.write_text('MEMORY { rom : ORIGIN = 0, LENGTH = 4K ram : ORIGIN = 4096, LENGTH = 2M }')
    result = scaffold(core, linker_script=linker, ram_region='ram', reset_pc='4096', dry_run=True)
    assert json.loads(result['files']['rvw/cosim.json'])['ram'][0]['size'] == '0x200000'


def test_build_selection_refuses_ambiguity(core):
    with pytest.raises(ValueError, match='--sbt-project'):
        scaffold(core, wire_build=True)
    assert not (core / 'rvw.toml').exists()
    (core / 'build.sbt').write_text('val spinalVersion = "1.15.0"\nlazy val cpu = project\nlazy val tests = project')
    with pytest.raises(ValueError, match='--sbt-project'):
        scaffold(core, wire_build=True)
    assert scaffold(core, sbt_project='cpu', dry_run=True)['build_wired']
    with pytest.raises(ValueError, match='Invalid sbt'):
        scaffold(core, sbt_project='cpu;run')


def test_db_entry_forwards_arguments_without_sbt_command_injection(core, tmp_path):
    import os
    import subprocess
    scaffold(core, sbt_project='cpu', db_top='demo.Top')
    workstation = tmp_path / 'workstation'
    (workstation / 'scripts').mkdir(parents=True)
    (workstation / 'SpinalDB').mkdir()
    lock = workstation / 'scripts/with-lock.sh'
    lock.write_text('#!/bin/bash\nshift\nexec "$@"\n')
    lock.chmod(0o755)
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    builder = binaries / 'sbt'
    builder.write_text('#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\nargsfile = sys.argv[-1].split("--args-file ")[1]\nPath(os.environ["OUTPUT_ARGS"]).write_bytes(Path(argsfile).read_bytes())\n')
    builder.chmod(0o755)
    arguments = tmp_path / 'args'
    output = tmp_path / 'spaces ; dollar $ output.db'
    env = dict(os.environ, RVW_HOME=str(workstation), OUTPUT_ARGS=str(arguments),
               PATH=str(binaries) + ':' + os.environ['PATH'])
    done = subprocess.run([str(core / 'rvw/build-db.sh'), 'default', str(output)], env=env)
    assert done.returncode == 0
    assert arguments.read_bytes().split(b'\0')[:2] == [str(output).encode(), b'--source-root']
    assert subprocess.run([str(core / 'rvw/build-db.sh'), 'other', str(output)], env=env).returncode == 2


@pytest.mark.parametrize("build_fails", [False, True])
def test_wired_launcher_uses_generic_supervision_and_identity(core, tmp_path, build_fails):
    import os
    import subprocess
    import sys
    scaffold(core, sbt_project='cpu')
    workstation = tmp_path / 'installed workstation'
    scripts = workstation / 'RiscvSim/scripts'
    scripts.mkdir(parents=True)
    (workstation / 'scripts').mkdir()
    supervisor = scripts / 'supervise.py'
    supervisor.write_text('import os, sys\nos.execv(sys.argv[1], [*sys.argv[1:3], "--riscvsim-supervised", os.environ["LAUNCH_OWNER"], *sys.argv[3:]])\n')
    import shutil
    shutil.copy(Path(__file__).resolve().parents[2] / 'RiscvSim/scripts/classpath.py', scripts / 'classpath.py')
    jar = tmp_path / 'scala-library.jar'
    jar.touch()
    (scripts / 'source-identity.py').write_text('print("{}")\n')
    (scripts / 'native-identity.py').write_text('import json, os, sys\nfrom pathlib import Path\nif len(sys.argv) == 1: print(\'{}\')\nelse: Path(os.environ["OUTPUT_ARGS"]).write_text(json.dumps(sys.argv[1:]))\n')
    lock = workstation / 'scripts/with-lock.sh'
    lock.write_text('#!/bin/bash\nshift\nexec "$@"\n')
    lock.chmod(0o755)
    binaries = tmp_path / 'bin'
    binaries.mkdir()
    sbt = binaries / 'sbt'
    sbt.write_text('#!/bin/bash\necho compiling\n' +
                   ('exit 7\n' if build_fails else f'echo "{jar}"\n'))
    sbt.chmod(0o755)
    owner = tmp_path / 'owner'
    owner.mkdir()
    output = tmp_path / 'args'
    env = dict(os.environ, RVW_HOME=str(workstation), RVW_PYTHON=sys.executable,
               LAUNCH_OWNER=str(owner), OUTPUT_ARGS=str(output), PATH=str(binaries) + ':' + os.environ['PATH'])
    env.pop('RISCVSIM_EXTRA_INPUTS', None)
    done = subprocess.run([str(core / 'rvw/run.sh'), 'run', '--elf', 'path ; with spaces', '--out', 'out'], env=env, capture_output=True, text=True)
    assert 'compiling' in done.stderr
    assert '/synthetic/scala-library.jar' not in done.stdout
    if build_fails:
        assert done.returncode == 2
        assert not output.exists()
        return
    assert done.returncode == 0
    arguments = json.loads(output.read_text())
    assert arguments[-5:] == ['run', '--elf', 'path ; with spaces', '--out', 'out']
    assert 'rvwcore.Main' in arguments
    assert (owner / 'source.json').read_text().strip() == '{}'


def test_build_wiring_refuses_incompatible_literal_versions(core):
    (core / 'build.sbt').write_text('val spinalVersion = "1.14.0"\nlazy val cpu = project')
    with pytest.raises(ValueError, match='Spinal version 1.15.0'):
        scaffold(core, wire_build=True)
    (core / 'build.sbt').write_text('val spinalVersion = "1.15.0"\nscalaVersion := "2.12.18"\nlazy val cpu = project')
    with pytest.raises(ValueError, match='Scala 2.13.14'):
        scaffold(core, wire_build=True)
    assert not (core / 'rvw.toml').exists()
