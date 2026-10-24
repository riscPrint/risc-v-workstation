"""Keep tracked text free of paths from a developer's home directory."""
import os
from pathlib import Path
import re
import subprocess

import pytest


REPO = Path(__file__).resolve().parents[2]
PERSONAL_PATH = re.compile(r"/(?:Users/|home/[^/\s\"'<>]+)")


def personal_path_lines(text):
    return [number for number, line in enumerate(text.splitlines(), 1)
            if PERSONAL_PATH.search(line)]


def test_tracked_text_has_no_personal_paths():
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=REPO,
                            capture_output=True, check=True)
    found = []
    for name in result.stdout.split(b'\0'):
        if not name:
            continue
        path = REPO / os.fsdecode(name)
        # Deleted tracked files and symlinks have no text content to inspect.
        if path.is_symlink() or not path.is_file():
            continue
        raw = path.read_bytes()
        if b'\0' in raw:
            continue
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        found.extend(f'{os.fsdecode(name)}:{line}' for line in personal_path_lines(text))
    assert not found, 'Personal paths in tracked text:\n' + '\n'.join(found)


@pytest.mark.parametrize('parent', ['Users', 'home'])
def test_path_check_finds_personal_directories(parent):
    text = 'neutral\n' + '/' + parent + '/developer/project\n'
    assert personal_path_lines(text) == [2]


def test_path_check_allows_neutral_examples():
    assert personal_path_lines('/work/core\n/path/to/core\n$RVW_HOME/rvw\n') == []


@pytest.mark.parametrize('script,args,variable', [
    ('SpinalChecks/boom/from-sim.sh', [], 'ENV_SH'),
    ('SpinalChecks/boom/run-suite.sh', [], 'ENV_SH'),
    ('SpinalChecks/boom/xprop.sh', [], 'ENV_SH'),
    ('rvw/examples/coverage/collect-boom.sh', ['out'], 'SPINAL_BOOM'),
])
def test_boom_helpers_name_missing_configuration(script, args, variable):
    env = dict(os.environ)
    env.pop(variable, None)
    result = subprocess.run(['bash', str(REPO / script), *args], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert variable in result.stderr


def test_suite_names_missing_test_directory(tmp_path):
    setup = tmp_path / 'env.sh'
    setup.write_text('')
    env = dict(os.environ, ENV_SH=str(setup))
    env.pop('RISCV_TESTS', None)
    result = subprocess.run(['bash', str(REPO / 'SpinalChecks/boom/run-suite.sh')],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'RISCV_TESTS' in result.stderr


def test_wave_tools_use_path(tmp_path, monkeypatch):
    from rvw.wave.vcd import tool

    hidden = tmp_path / 'opt/oss-cad-suite/bin/fst2vcd'
    hidden.parent.mkdir(parents=True)
    hidden.write_text('#!/bin/sh\nexit 0\n')
    hidden.chmod(0o755)
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('PATH', '')
    assert tool('fst2vcd') is None
    monkeypatch.setenv('PATH', str(hidden.parent))
    assert tool('fst2vcd') == str(hidden)
