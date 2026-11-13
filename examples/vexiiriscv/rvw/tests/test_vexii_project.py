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
    monkeypatch.setenv('VEXIIRISCV', str(core))
    shutil.copy2(EXAMPLE / 'rvw.toml', core / 'rvw.toml')
    shutil.copytree(EXAMPLE / 'rvw', core / 'rvw',
                    ignore=shutil.ignore_patterns('target', 'out', '__pycache__'))
    monkeypatch.setenv('RVW_HOME', str(tmp_path / 'installed workstation'))
    monkeypatch.delenv('RVW_PROJECT', raising=False)
    monkeypatch.setenv('VEXIIRISCV', str(core))
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
    root = EXAMPLE.parents[1]
    selected, excluded = module['mmu_rows'](root, 'examples/mmu/matrix.json', 'sv39', {'ad:fault'})
    assert len(selected) == 145
    assert len(selected) + len(excluded) == 589
    assert all(row['mode'] == 'sv39' and row.get('ad_mode') != 'hardware' for row in selected)
    assert any('hardware A/D' in row['reason'] for row in excluded)
    sv32, _ = module['mmu_rows'](root, 'examples/mmu/matrix.json', 'sv32', {'ad:fault'})
    assert len(sv32) == 140 and all(row['mode'] == 'sv32' for row in sv32)


def test_plan_selects_profile_families():
    from rvw.regress.commands.applicability import plan
    for name, expected in (('features64.json', {'mmu-sv39', 'privilege-controls', 'pmp', 'scheduled-wfi', 'fence-i-rv64'}),
                           ('features32.json', {'mmu-sv32', 'amo-rv32', 'fence-rv32', 'scheduled-wfi-rv32', 'pmp-rv32'})):
        rows = plan(EXAMPLE / 'rvw' / name)['suites']
        applicable = {r['name'] for r in rows if r['applicable']}
        assert expected <= applicable
        assert not applicable & {'mmu-sv48', 'hypervisor', 'shootdown', 'memory-concurrent'}


@pytest.mark.parametrize('modes,expected_count', [('MSU', 394), ('MU', 242)])
def test_prepare_rv32_pmp_uses_declared_profile(tmp_path, monkeypatch, modes, expected_count):
    import runpy
    import sys
    from rvw.privilege import campaign
    from rvw.regress.commands import applicability
    module = runpy.run_path(str(EXAMPLE / 'rvw/prepare-suites.py'))
    features = json.loads((EXAMPLE / 'rvw/features32.json').read_text())
    features['privilege_modes'] = modes
    declaration = tmp_path / 'features.json'
    declaration.write_text(json.dumps(features))
    selected = applicability.plan(declaration)
    selected['suites'] = [r for r in selected['suites'] if r['name'] == 'pmp-rv32']
    monkeypatch.setattr(applicability, 'plan', lambda path: selected)
    seen = []
    def capture(description, out, gcc):
        config = campaign.load(description)
        assert config['isa'] == features['isa']
        assert config['pmp'] == dict(entries=8, granularity_bytes=4)
        assert config.get('priv', 'msu') == modes.lower()
        rows = campaign.scenarios(config)
        assert len(rows) == expected_count
        assert all('sd t1' not in row['assembly'] for row in rows)
        seen.append(out.name)
        return dict(scenarios=rows)
    monkeypatch.setattr(campaign, 'build', capture)
    monkeypatch.setenv('RVW_HOME', str(EXAMPLE.parents[1]))
    monkeypatch.setattr(sys, 'argv', ['prepare', '--features', str(declaration), '--out', str(tmp_path / 'built')])
    assert module['main']() == 0
    assert seen == ['pmp']
    selection = json.loads((tmp_path / 'built/selection.json').read_text())
    family = selection['families'][0]
    assert family['source'] == 'examples/privilege/pmp-rv32.json'
    assert family['generated'] == family['applicable'] == expected_count
    assert family['excluded'] == []

@pytest.mark.parametrize('bits', [32, 64])
def test_prepare_random_privilege_selected_family(tmp_path, monkeypatch, bits):
    import runpy
    import sys
    from rvw.privilege import campaign
    from rvw.regress.commands import applicability
    module = runpy.run_path(str(EXAMPLE / 'rvw/prepare-suites.py'))
    features = EXAMPLE / f'rvw/features{bits}.json'
    selection = applicability.plan(features)
    assert next(r for r in selection['suites'] if r['name'] == 'reset-rv64')['applicable'] == (bits == 64)
    selection['suites'] = [r for r in selection['suites'] if r['name'] == f'random-privilege-rv{bits}']
    monkeypatch.setattr(applicability, 'plan', lambda path: selection)
    seen = []
    def capture(description, out, gcc):
        config = campaign.load(description)
        assert config['isa'].startswith(f'rv{bits}')
        rows = campaign.scenarios(config)
        assert len(rows) == 4
        seen.append(out.name)
        return dict(scenarios=rows)
    monkeypatch.setattr(campaign, 'build', capture)
    monkeypatch.setenv('RVW_HOME', str(EXAMPLE.parents[1]))
    monkeypatch.setattr(sys, 'argv', ['prepare', '--features', str(features), '--out', str(tmp_path / 'build')])
    assert module['main']() == 0
    assert seen == ['random-privilege']
    family = json.loads((tmp_path / 'build/selection.json').read_text())['families'][0]
    assert family['generated'] == family['applicable'] == 4


def test_prepare_selected_reset_family(tmp_path, monkeypatch):
    import runpy
    import sys
    from rvw.privilege import campaign
    from rvw.regress.commands import applicability
    module = runpy.run_path(str(EXAMPLE / 'rvw/prepare-suites.py'))
    features = EXAMPLE / 'rvw/features64.json'
    selection = applicability.plan(features)
    selection['suites'] = [r for r in selection['suites'] if r['name'] == 'reset-rv64']
    assert selection['suites'][0]['applicable']
    monkeypatch.setattr(applicability, 'plan', lambda path: selection)
    def capture(description, out, gcc):
        config = campaign.load(description)
        rows = campaign.scenarios(config)
        assert len(rows) == 3
        assert all(len(r['events']) == 3 for r in rows)
        assert out.name == 'reset'
        return dict(scenarios=rows)
    monkeypatch.setattr(campaign, 'build', capture)
    monkeypatch.setenv('RVW_HOME', str(EXAMPLE.parents[1]))
    monkeypatch.setattr(sys, 'argv', ['prepare', '--features', str(features), '--out', str(tmp_path / 'built')])
    assert module['main']() == 0
    report = json.loads((tmp_path / 'built/selection.json').read_text())
    assert report['families'][0]['generated'] == report['families'][0]['applicable'] == 3
