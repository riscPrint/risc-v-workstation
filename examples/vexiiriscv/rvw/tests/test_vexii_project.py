"""Project selection and the database launch interface, without a Scala build."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from rvw.common.project import find_project, load_project
from rvw.regress.config import load_config

EXAMPLE = Path(__file__).resolve().parents[2]


def test_copied_project_uses_core_owned_paths(tmp_path, monkeypatch):
    core = tmp_path / 'separate core'
    core.mkdir()
    shutil.copy2(EXAMPLE / 'rvw.toml', core / 'rvw.toml')
    shutil.copytree(EXAMPLE / 'rvw', core / 'rvw',
                    ignore=shutil.ignore_patterns('target', 'out', '__pycache__'))
    monkeypatch.setenv('RVW_HOME', str(tmp_path / 'installed workstation'))
    monkeypatch.delenv('RVW_PROJECT', raising=False)
    monkeypatch.chdir(core / 'rvw' / 'programs')
    assert find_project() == core / 'rvw.toml'
    project = load_project()
    config = load_config(str(project.path))
    assert config.source_repo == core
    assert config.adapter == [str(core / 'rvw/run.sh')]
    assert project.get('query', 'build') == [str(core / 'rvw/build-db.sh')]
    assert project.get('query', 'db') == core / 'rvw/out/vexii.db'
    assert project.get('cosim', 'platform') == core / 'rvw/platform.json'


@pytest.mark.parametrize("options", [[], ["--no-pdg", "--rtl", "space /rtl"]])
def test_database_launcher_preserves_output_and_rejects_bad_config(tmp_path, options):
    tools = tmp_path / 'installed workstation'
    (tools / 'scripts').mkdir(parents=True)
    lock = tools / 'scripts/with-lock.sh'
    lock.write_text('#!/bin/sh\nshift\nexec "$@"\n')
    lock.chmod(0o755)
    binary = tmp_path / 'bin'
    binary.mkdir()
    sbt = binary / 'sbt'
    sbt.write_text('''#!/usr/bin/env python3
import json, os, pathlib, sys
args_file = sys.argv[-1].split('--args-file ', 1)[1]
args = pathlib.Path(args_file).read_bytes().decode().split('\\0')[:-1]
pathlib.Path(os.environ['CAPTURE']).write_text(json.dumps(dict(
    args=args, runner=os.environ.get('SPINALDB_PROCESS_RUNNER'),
    python=os.environ.get('SPINALDB_PYTHON'))))
pathlib.Path(args[1]).write_text('database fixture')
''')
    sbt.chmod(0o755)
    captured = tmp_path / 'arguments.json'
    env = dict(os.environ, RVW_HOME=str(tools), VEXIIRISCV=str(tmp_path),
               CAPTURE=str(captured), PATH=str(binary) + os.pathsep + os.environ['PATH'])
    launcher = EXAMPLE / 'rvw/build-db.sh'
    out = Path('space ; quote "/design.db')
    run = subprocess.run([str(launcher), 'rv32im', str(out), *options], cwd=tmp_path,
                         env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    capture = json.loads(captured.read_text())
    assert capture['args'] == ['rv32im', str(tmp_path / out), *options]
    assert capture['runner'] == str(tools / 'SpinalDB/scripts/hdl-deps.py')
    assert capture['python'] == env.get('RVW_PYTHON', str(tools / 'rvw/.venv/bin/python'))
    assert (tmp_path / out).read_text() == 'database fixture'
    captured.unlink()
    run = subprocess.run([str(launcher), 'wrong-config', str(out)], cwd=tmp_path,
                         env=env, capture_output=True, text=True)
    assert run.returncode == 2
    assert not captured.exists()


def test_rich_paging_selection_excludes_other_modes_and_hardware_ad():
    import runpy
    module = runpy.run_path(str(EXAMPLE / 'rvw/prepare-suites.py'))
    selected, excluded = module['mmu_selection'](EXAMPLE.parents[1])
    assert len(selected) == 145
    assert len(selected) + len(excluded) == 589
    assert all(row['mode'] == 'sv39' and row.get('ad_mode') != 'hardware' for row in selected)
    assert any('hardware A/D' in row['reason'] for row in excluded)
