"""Native replay environment prefixes survive binding, batching and shell replay."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

from rvw import runs
from rvw.runs import adapter
from rvw.runs.inputs import DebugInputs
from test_debug_tools import fake_run


@pytest.mark.parametrize('wrapper', ['env -u SPINAL_VERILATOR_FLAGS',
                                     '/usr/bin/env --unset=SPINAL_VERILATOR_FLAGS'])
@pytest.mark.parametrize('batch', [False, True])
def test_native_environment_replay(tmp_path, monkeypatch, wrapper, batch):
    monkeypatch.setenv('RVW_NO_LOCK', '1')
    monkeypatch.delenv('RVW_NO_RUN_MANY', raising=False)
    monkeypatch.setenv('SPINAL_VERILATOR_FLAGS', 'must be removed')
    script = tmp_path / 'adapter.py'
    script.write_text(
        'import json, os, sys\nfrom pathlib import Path\n'
        'def write(row):\n'
        ' out=Path(row["out"]); out.mkdir(exist_ok=True)\n'
        ' data={"schema":"rvw.run/1", "status":"pass",\n'
        '       "details":{"flags":os.getenv("SPINAL_VERILATOR_FLAGS"),\n'
        '                  "setting":os.getenv("SPINAL_SETTING")}}\n'
        ' (out/"result.json").write_text(json.dumps(data))\n'
        'if sys.argv[1]=="run-many":\n'
        ' for line in Path(sys.argv[3]).read_text().splitlines(): write(json.loads(line))\n'
        'else: write({"out":sys.argv[sys.argv.index("--out")+1]})\n')
    run = fake_run(tmp_path / 'run', '--seed', '9')
    data = json.loads((run / 'result.json').read_text())
    data['replay'] = wrapper + ' SPINAL_SETTING=' + shlex.quote('two words') + ' ' + shlex.join(
        [sys.executable, str(script), 'run'])
    (run / 'result.json').write_text(json.dumps(data))
    inputs = DebugInputs()
    cmd = inputs.command(runs.open_run(run, capture=inputs.capture), {})
    assert all(Path(arg).name != 'env' for arg in cmd.exe)
    if batch:
        attempts = adapter.execute_many([cmd, cmd.set(seed=2)], [tmp_path / 'a', tmp_path / 'b'])
    else:
        attempts = [adapter.execute(cmd, tmp_path / 'a')]
    for attempt in attempts:
        assert attempt.run.get('details') == {'flags': None, 'setting': 'two words'}
    replay = cmd.set(out=tmp_path / 'saved').shell()
    subprocess.run(['bash', '-c', replay], check=True, env=os.environ)
    assert runs.open_run(tmp_path / 'saved').get('details') == {'flags': None, 'setting': 'two words'}
    copied = adapter.parse_replay(replay)
    assert copied.unset == cmd.unset and copied.env == cmd.env
    from rvw.bundle.make import _write_replay
    saved = tmp_path / 'replay.sh'
    _write_replay(saved, cmd, runs.open_run(run))
    subprocess.run(['bash', str(saved), str(tmp_path / 'script-result')], check=True, env=os.environ)
    assert runs.open_run(tmp_path / 'script-result').get('details') == {
        'flags': None, 'setting': 'two words'}


def test_env_assignment_can_restore_an_unset_name():
    command = adapter.parse_replay('X=before env -u X X=after adapter run')
    assert command.unset == ['X'] and command.env == {'X': 'after'}


@pytest.mark.parametrize('prefix', ['env -u', 'env -u BAD-NAME', 'env -i', 'env --chdir=/tmp'])
def test_unsupported_env_prefix_refuses(prefix):
    with pytest.raises(ValueError, match='environment'):
        adapter.parse_replay(prefix + ' adapter run')


def test_shared_git_runner_strips_overrides_and_keeps_execution_policy():
    from rvw.common.capture import run_git

    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return "result"

    assert run_git('/repo', 'status', tool='/tools/git', timeout=17, text=False,
                   env={'GIT_DIR': '/wrong', 'GIT_INDEX_FILE': '/wrong-index',
                        'GIT_NO_REPLACE_OBJECTS': '0', 'PATH': '/tools'}, run=run) == 'result'
    argv, options = calls[0]
    assert argv == ['/tools/git', '--no-replace-objects', '-C', '/repo', 'status']
    assert options == {'env': {'PATH': '/tools', 'GIT_NO_REPLACE_OBJECTS': '1',
                              'GIT_OPTIONAL_LOCKS': '0'}, 'capture': True,
                       'text': False, 'timeout': 17}
