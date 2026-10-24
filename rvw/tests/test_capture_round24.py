"""Replay publication keeps environment assignments as single shell values."""
import os
import shlex
import sys
from pathlib import Path

from rvw.common.proc import run_group
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results, load_run
from rvw.runs.adapter import parse_replay


def test_saved_replay_quotes_path_and_reads_back(fake, tmp_path, monkeypatch):
    path = str(tmp_path / "Application Support/bin") + os.pathsep + os.environ['PATH']
    monkeypatch.setenv('PATH', path)
    core = load_config(str(fake.config))
    adapter = tmp_path / 'adapter.py'
    text = Path(core.adapter[1]).read_text().replace('import argparse', 'import argparse\nimport shlex')
    text = text.replace('"replay": f"fake_adapter.py run',
                        '''"replay": "PATH=" + shlex.quote(os.environ['PATH']) + " env -u CXX " + shlex.quote(sys.executable) + " " + shlex.quote(__file__) + f" run''')
    adapter.write_text(text)
    core.adapter[1] = str(adapter)
    runner = Runner(core, describe(fake.repo), tmp_path / 'out', RunOptions(index=False, log=None))
    assert runner.run(suites_plan(core, ['isa'], ['small']))['ok']
    suite = find_results(runner.out)[0]
    saved = load_run(suite.path / suite.tests[0].run)
    parsed = parse_replay(saved.replay, tmp_path)
    assert parsed.env['PATH'] == path
    assert parsed.exe == [sys.executable, str(adapter)]
    assert parsed.unset == ['CXX']
    assert str(runner.inputs.directory) not in saved.replay
    # Run the published shell command after the private inputs have been removed.
    result = run_group(['/bin/sh', '-c', saved.replay], capture=True, timeout=10)
    assert result.returncode == 0, result.stderr
