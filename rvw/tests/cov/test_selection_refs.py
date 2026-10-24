"""Git refs can move while selection reads the two diffs."""
import subprocess
from pathlib import Path
from rvw.common.capture import CaptureError

import pytest

from rvw.cov.code import select



def _at(argv, path):
    """A git call run in `path`, wherever the shared runner puts `-C`."""
    return '-C' in argv and argv[argv.index('-C') + 1] == str(path)

@pytest.fixture
def history(tmp_path):
    def git(*args):
        return subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test',
                               '-c', 'user.email=t@x', *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    git('init', '-q')
    unit = tmp_path / 'Unit.scala'
    unit.write_text('val a=1\nval b=2\n')
    git('add', 'Unit.scala')
    git('commit', '-qm', 'base')
    base = git('rev-parse', 'HEAD')
    unit.write_text('val a=3\nval b=2\n')
    git('commit', '-qam', 'first candidate')
    head = git('rev-parse', 'HEAD')
    unit.write_text('val a=1\nval b=4\n')
    (tmp_path / 'blackbox.v').write_text('module bb; endmodule\n')
    git('add', 'Unit.scala', 'blackbox.v')
    git('commit', '-qm', 'later candidate')
    later = git('rev-parse', 'HEAD')
    git('update-ref', 'refs/heads/base', base)
    git('update-ref', 'refs/heads/candidate', head)
    data = {'source_revision': base, 'tests': {'A': {}, 'B': {}},
            'points': [{'scala': {'file': 'Unit.scala', 'line': line}, 'tests': {test: 1}}
                       for line, test in ((1, 'A'), (2, 'B'))]}
    return git, data, base, head, later


@pytest.mark.parametrize('move_before', ['first_diff', 'second_diff'])
@pytest.mark.parametrize('move_base', [False, True])
def test_selection_pins_both_refs_for_all_diffs(tmp_path, monkeypatch, history, move_before, move_base):
    git, data, base, head, later = history
    expected = select(data, 'base..candidate', tmp_path)
    assert expected['tests'] == ['A'] and not expected['fallback_all']
    original_popen = subprocess.Popen
    calls, moved = [], False

    def popen(argv, *args, **kwargs):
        nonlocal moved
        if Path(argv[0]).name == 'git' and _at(argv, tmp_path):
            calls.append(argv)
            trigger = 'diff' in argv if move_before == 'first_diff' else '--unified=0' in argv
            if trigger and not moved:
                moved = True
                if move_base:
                    git('update-ref', 'refs/heads/base', head)
                git('update-ref', 'refs/heads/candidate', later)
        return original_popen(argv, *args, **kwargs)

    # Change real refs at a Git process boundary. Parsing and both diffs remain real.
    monkeypatch.setattr(subprocess, 'Popen', popen)
    result = select(data, 'base..candidate', tmp_path)
    assert moved
    assert result == expected
    assert result['base_revision'] == base and result['head_revision'] == head
    resolutions = [argv[-1] for argv in calls if 'rev-parse' in argv]
    assert resolutions == ['base^{commit}', 'candidate^{commit}']
    diffs = [argv for argv in calls if 'diff' in argv]
    assert len(diffs) == 2
    assert all(f'{base}..{head}' in argv for argv in diffs)
    # A later call sees the new commits and the blackbox, so it must run every test.
    stable_after = select(data, 'base..candidate', tmp_path)
    assert stable_after['fallback_all'] and stable_after['tests'] == ['A', 'B']
    assert stable_after['non_scala_changes'] == ['blackbox.v']
    assert stable_after['base_revision'] == (head if move_base else base)
    assert stable_after['head_revision'] == later


def test_selection_resolves_a_repeated_ref_once(tmp_path, monkeypatch, history):
    git, data, _, head, later = history
    original_popen = subprocess.Popen
    resolutions = []

    def popen(argv, *args, **kwargs):
        if Path(argv[0]).name == 'git' and _at(argv, tmp_path):
            if 'rev-parse' in argv:
                resolutions.append(argv[-1])
            elif 'diff' in argv:
                git('update-ref', 'refs/heads/candidate', later)
        return original_popen(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, 'Popen', popen)
    result = select(data, 'candidate..candidate', tmp_path)
    assert resolutions == ['candidate^{commit}']
    assert result['base_revision'] == head and result['head_revision'] == head
    assert result['tests'] == [] and result['changed_files'] == []
    assert not result['fallback_all']


def test_selection_ref_resolution_errors_are_not_empty_selections(tmp_path, history):
    _, data, _, _, _ = history
    with pytest.raises(CaptureError):
        select(data, 'base..missing-ref', tmp_path)
