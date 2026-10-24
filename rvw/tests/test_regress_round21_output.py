"""Capture storage must stay outside the selected input trees."""
from regress_fixtures import git
from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.regress.plan import gate
from rvw.regress.captured import private_directory


def test_ignored_output_inside_core_does_not_overlap_capture(fake):
    (fake.repo / '.gitignore').write_text('build/\n')
    git(fake.repo, 'add', '.gitignore')
    git(fake.repo, 'commit', '-qm', 'Ignore build output')
    core = load_config(str(fake.config))
    output = fake.repo / 'build' / 'test-run'
    runner = Runner(core, describe(fake.repo), output, RunOptions(index=False, log=None))
    assert not runner.inputs.directory.is_relative_to(fake.repo)
    summary = runner.run(suites_plan(core, ['isa'], None))
    assert summary['ok'], summary
    assert runner.out == output.resolve()


def test_gate_results_root_inside_ignored_core_output(fake, monkeypatch):
    (fake.repo / '.gitignore').write_text('build/\n')
    git(fake.repo, 'add', '.gitignore')
    git(fake.repo, 'commit', '-qm', 'Ignore build output')
    core = load_config(str(fake.config))
    revision = describe(fake.repo).rev
    root = fake.repo / 'build' / 'results'
    result = gate(core, 'quick', revision, revision, None, None, None,
                  RunOptions(results_root=root, index=False, log=None), None, None)
    assert result['verdict'].verdict == 'accept'
    assert result['file'].is_relative_to(root)


def test_storage_falls_back_when_temp_directory_is_an_input(fake, tmp_path, monkeypatch):
    from rvw.regress import captured
    core = load_config(str(fake.config))
    core.cache_paths = [tmp_path]
    monkeypatch.setattr(captured.tempfile, 'gettempdir', lambda: str(tmp_path))
    directory = private_directory(core, describe(fake.repo))
    assert not directory.is_relative_to(tmp_path)
    assert directory == directory.resolve()
