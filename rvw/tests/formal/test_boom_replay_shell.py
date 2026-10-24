"""The BOOM replay adapter must pass caller values as arguments, not shell source."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize('option', ['cycle', 'depth', 'engine', 'timeout', 'out'])
@pytest.mark.parametrize('rvw_rc', [0, 7])
def test_replay_adapter_does_not_execute_caller_values(tmp_path, option, rvw_rc):
    root = Path(__file__).resolve().parents[3]
    adapter = tmp_path / 'SpinalChecks' / 'boom'
    adapter.mkdir(parents=True)
    shutil.copy(root / 'SpinalChecks' / 'boom' / 'from-sim.sh', adapter)
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    lock = scripts / 'with-lock.sh'
    lock.write_text('#!/bin/bash\nshift\nexec "$@"\n')
    lock.chmod(0o755)
    rvw = tmp_path / 'rvw' / '.venv' / 'bin' / 'rvw'
    rvw.parent.mkdir(parents=True)
    rvw.write_text('#!/usr/bin/env python3\nimport json,os,sys\n'
                   'open(os.environ["ARGV_FILE"], "w").write(json.dumps(sys.argv[1:]))\n'
                   'sys.exit(int(os.environ["RVW_EXIT"]))\n')
    rvw.chmod(0o755)
    env_sh = tmp_path / 'env.sh'
    env_sh.write_text('')
    sentinel = tmp_path / 'PWNED'
    out = adapter / (f'out; touch {sentinel}; #' if option == 'out' else 'out')
    (out / 'sim' / 'small_wave' / 'rtl').mkdir(parents=True)
    (out / 'sim' / 'small_wave' / 'rtl' / 'top.v').touch()
    (out / 'sim' / 'small_wave' / 'rv64ui-p-add').mkdir()
    (out / 'sim' / 'small_wave' / 'rv64ui-p-add' / 'wave.fst').touch()
    attack = f"smtbmc:yices'; touch {sentinel}; #" if option == 'engine' else f'1; touch {sentinel}; #'
    values = {'cycle': '2', 'depth': '4', 'engine': 'abc:bmc3', 'timeout': '10'}
    if option != 'out':
        values[option] = attack
    capture = tmp_path / 'argv.json'
    env = dict(os.environ, ENV_SH=str(env_sh), SKIP_SIM='1', ENGINE=values['engine'],
               TIMEOUT=values['timeout'], ARGV_FILE=str(capture), RVW_EXIT=str(rvw_rc))
    result = subprocess.run(['bash', str(adapter / 'from-sim.sh'), values['cycle'], values['depth'], str(out)],
                            env=env, capture_output=True, text=True)
    assert not sentinel.exists(), result.stderr
    assert result.returncode == rvw_rc, result.stderr
    argv = json.loads(capture.read_text())
    for key in ('cycle', 'depth', 'engine', 'timeout'):
        assert argv[argv.index('--' + key) + 1] == values[key]
