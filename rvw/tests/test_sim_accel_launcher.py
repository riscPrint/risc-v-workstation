"""Exercise the opt-in BOOM launcher without compiling RTL."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def launch(tmp_path, args=(), flags=None):
    wrapper = tmp_path / 'run-medium-fast.sh'
    shutil.copy2(ROOT / 'RiscvSim/boom/run-medium-fast.sh', wrapper)
    runner = tmp_path / 'run.sh'
    runner.write_text('#!/usr/bin/env python3\nimport json,os,sys\nprint(json.dumps([sys.argv[1:],os.environ["SPINAL_VERILATOR_FLAGS"]]))\n')
    runner.chmod(0o755)
    env = dict(os.environ)
    env.pop('SPINAL_VERILATOR_FLAGS', None)
    if flags is not None:
        env['SPINAL_VERILATOR_FLAGS'] = flags
    return subprocess.run(['bash', str(wrapper), *args], env=env, capture_output=True, text=True)


def test_medium_opt_in_preserves_options_and_sets_two_threads(tmp_path):
    result = launch(tmp_path, ['--elf', 'long.elf', '--out', 'output', '--seed', '1'],
                    '--output-split 10000')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        ['run', '--config', 'medium', '--elf', 'long.elf', '--out', 'output', '--seed', '1'],
        '--output-split 10000 --threads 2']


@pytest.mark.parametrize('args', [ ['--config', 'large'], ['--config=small'] ])
def test_opt_in_refuses_unqualified_preset(tmp_path, args):
    result = launch(tmp_path, args)
    assert result.returncode == 2
    assert 'config' in result.stderr
    assert not result.stdout


@pytest.mark.parametrize('flags', ['--threads 1', '--threads=4'])
def test_opt_in_refuses_inherited_thread_override(tmp_path, flags):
    result = launch(tmp_path, flags=flags)
    assert result.returncode == 2
    assert 'threads' in result.stderr
    assert not result.stdout
