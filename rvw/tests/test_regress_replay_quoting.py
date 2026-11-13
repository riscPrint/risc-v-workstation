"""Published replays must bind the saved ELF for any valid shell quote style."""
import shlex
from pathlib import Path

import pytest

from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results, load_run, save_run

pytestmark = pytest.mark.fast


@pytest.mark.parametrize("equals", [False, True])
def test_double_quoted_elf_survives_capture_cleanup(fake, tmp_path, monkeypatch, equals):
    storage = tmp_path / 'capture space'
    storage.mkdir()
    monkeypatch.setattr('rvw.regress.captured.tempfile.gettempdir', lambda: str(storage))
    core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'out',
                    RunOptions(index=False, use_cache=False, log=None))
    run_tests = runner._run_tests

    def quoted(pending, *args):
        run_tests(pending, *args)
        for job in pending:
            run = load_run(job.dir)
            run.replay = (f'FAKE_SRC={shlex.quote(str(fake.repo))} ' + shlex.join(core.adapter)
                          + f' run --elf "{run.elf}" --seed {run.seed}'
                          + f' --config {run.config} --max-cycles {run.max_cycles} --out "{job.dir}"')
            if equals:
                run.replay = run.replay.replace('--elf ', '--elf=')
            run.replay = 'LITERAL="$HOME with space" ' + run.replay
            save_run(run, job.dir)

    monkeypatch.setattr(runner, '_run_tests', quoted)
    assert runner.run(suites_plan(core, ['isa'], None))['ok']
    assert not runner.inputs.directory.exists()
    for suite in find_results(runner.out):
        for entry in suite.tests:
            run = load_run(suite.path / entry.run)
            argv = shlex.split(run.replay)
            assert run.replay.startswith('LITERAL="$HOME with space" ')
            saved = Path(next(a.split('=', 1)[1] for a in argv if a.startswith('--elf='))
                         if equals else argv[argv.index('--elf') + 1])
            assert saved.is_file()
            assert saved.read_bytes() == Path(run.elf).read_bytes()
