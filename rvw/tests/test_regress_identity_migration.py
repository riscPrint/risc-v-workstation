import os
import sys
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe


def test_adapter_identity_does_not_replace_declared_command_bytes(fake, tmp_path, monkeypatch):
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    dependency = bindir / 'migration-dependency'
    dependency.write_text('#!' + sys.executable + '\nprint("first")\n')
    dependency.chmod(0o755)
    monkeypatch.setenv('PATH', str(bindir) + os.pathsep + os.environ['PATH'])
    core = load_config(str(fake.config))
    core.input_commands = ['migration-dependency']
    core.identity = True
    options = RunOptions(results_root=tmp_path / 'store', index=False, log=None)
    plan = suites_plan(core, ['isa'], None)
    first = Runner(core, describe(fake.repo), tmp_path / 'first', options)
    assert first.run(plan)['ok']
    count = len(fake.calls('run'))
    dependency.write_text('#!' + sys.executable + '\nprint("changed")\n')
    second = Runner(core, describe(fake.repo), tmp_path / 'second', options)
    assert second.run(plan)['ok']
    assert len(fake.calls('run')) > count
    # The adapter identity alone did not detect this changed dependency.
    assert second.identities == first.identities
