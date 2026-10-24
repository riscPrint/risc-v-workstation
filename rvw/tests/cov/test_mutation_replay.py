"""Mutation replay must use the same detection and equivalence test selections."""
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from rvw.cov import mutation
from rvw.common.capture import sha256_file


@pytest.fixture
def project(tmp_path, monkeypatch):
    (tmp_path / 'database').mkdir()
    (tmp_path / 'config.mcy').write_text('[options]\nsize 4\n')
    (tmp_path / 'baseline.sh').write_text('exit 0\n')
    (tmp_path / 'design.sv').write_text('module dut; endmodule\n')
    (tmp_path / 'rvw-mcy-config.sha256').write_text(sha256_file(tmp_path / 'config.mcy') + '\n')
    with sqlite3.connect(tmp_path / 'database/db.sqlite3') as db:
        db.executescript('CREATE TABLE mutations(mutation_id INTEGER, mutation TEXT);'
                         'CREATE TABLE tags(mutation_id INTEGER, tag TEXT);'
                         'CREATE TABLE results(mutation_id INTEGER, test TEXT, result TEXT);'
                         'CREATE TABLE queue(mutation_id INTEGER, test TEXT, running INTEGER);'
                         'CREATE TABLE files(filename TEXT, data BLOB);')
        db.execute('INSERT INTO files VALUES(?,?)', ('design.sv', (tmp_path / 'design.sv').read_bytes()))
        db.executemany('INSERT INTO mutations VALUES(?,?)',
                       [(i, 'mutate -mode inv') for i in range(1, 5)])
        db.executemany('INSERT INTO results VALUES(?,?,?)', [
            (1, 'sim', 'PASS'), (1, 'eq', 'FAIL'),       # survivor, not a kill
            (2, 'sim', 'PASS'), (2, 'eq', 'PASS'),       # equivalent
            (3, 'sim', 'FAIL'), (3, 'eq', 'FAIL'),       # killed
            (4, 'sim', 'PASS'), (4, 'eq', 'FAIL'),       # pending second detection test
            *[(i, 'sim2', 'PASS') for i in range(1, 4)],
            *[(i, 'eq2', 'FAIL') for i in range(1, 5)],
            *[(i, 'unselected', 'FAIL') for i in range(1, 5)],
        ])
    # Only execution is stubbed. Reports and replay use the real SQLite reader and CLI parser.
    monkeypatch.setattr(mutation, 'run_job', lambda *args: 0)
    return tmp_path


@pytest.fixture
def fresh_project(project, monkeypatch):
    database = (project / 'database/db.sqlite3').read_bytes()
    shutil.rmtree(project / 'database')
    (project / 'rvw-mcy-config.sha256').unlink()

    def run_job(argv, cwd, log, timeout):
        argv = [Path(argv[0]).name, *argv[1:]]
        if argv == ['mcy', 'init']:
            (cwd / 'database').mkdir()
            (cwd / 'database/db.sqlite3').write_bytes(database)
        return 0

    monkeypatch.setattr(mutation, 'run_job', run_job)
    return project


@pytest.mark.parametrize('tests,equivalence', [
    (['sim', 'sim2'], ['eq', 'eq2']),
    (None, ['eq', 'eq2']),
    (['sim', 'sim2'], []),
    (None, []),
])
def test_replay_preserves_selected_tests_and_classifications(fresh_project, rvw, tests, equivalence):
    project = fresh_project
    original = mutation.mutate(project, run=True, baseline=project / 'baseline.sh',
                               detection_tests=tests, equivalence_tests=equivalence)
    if tests and equivalence:
        assert [m['observed_state'] for m in original['mutants']] == ['survived', 'equivalent', 'killed', 'pending']
        assert original['counts']['killed'] == 0 and original['status'] == 'inconclusive'
    # Execution replay needs fresh MCY state. Preserve the exact selection flags.
    fresh = project / 'replay'
    fresh.mkdir()
    for name in ('config.mcy', 'baseline.sh', 'design.sv'):
        shutil.copyfile(project / name, fresh / name)
    args = original['replay'][1:]
    args[2] = str(fresh)
    args[args.index('--baseline') + 1] = str(fresh / 'baseline.sh')
    rc, _, replay = rvw(*args)
    assert rc == 3, replay
    assert replay['counts'] == original['counts']
    assert replay['mutants'] == original['mutants']
    assert replay['detection_tests'] == original['detection_tests'] == tests
    assert replay['equivalence_tests'] == original['equivalence_tests'] == equivalence


def test_empty_detection_selection_is_refused(project):
    with pytest.raises(ValueError, match='detection test'):
        mutation.mutate(project, run=True, baseline=project / 'baseline.sh', detection_tests=[])


@pytest.mark.parametrize('dependency', ['test-options.svh', 'nested/options.svh', 'test-helper.sh',
                                         'baseline.sh', None])
def test_resume_refuses_incomplete_dependency_identity(project, dependency):
    # MCY's files table does not include headers or scripts read transitively.
    # Even unchanged known inputs cannot prove arbitrary script inputs complete.
    if dependency:
        path = project / dependency
        path.parent.mkdir(exist_ok=True)
        path.write_text('changed input\n')
    with pytest.raises(ValueError, match='dependency.*fresh project'):
        mutation.mutate(project, run=True, baseline=project / 'baseline.sh')


def test_resume_cli_does_not_return_cached_kills(project, rvw):
    rc, _, result = rvw('cov', 'mutate', project, '--run', '--baseline', project / 'baseline.sh', '--json')
    assert rc == 2
    assert result['schema'] == 'rvw.coverage-error/1'
    assert 'fresh project' in result['error']
    assert 'counts' not in result


def test_fresh_run_records_incomplete_identity_and_cannot_resume(fresh_project, monkeypatch):
    project = fresh_project
    result = mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert result['run_exit_code'] == 0
    audit = json.loads((project / 'rvw-mcy-inputs.json').read_text())
    assert audit['complete'] is False
    assert 'complete dependency identity cannot be determined' in audit['reason']
    assert audit['config']['sha256'] == sha256_file(project / 'config.mcy')
    assert audit['baseline']['sha256'] == sha256_file(project / 'baseline.sh')
    assert any(r['source'] == str(project / 'design.sv') for r in audit['capture']['files'])
    assert audit['tools'] == result['tools']

    def unexpected(*args):
        pytest.fail('resume must refuse before running the baseline or any MCY command')
    monkeypatch.setattr(mutation, 'run_job', unexpected)
    with pytest.raises(ValueError, match='fresh project'):
        mutation.mutate(project, run=True, baseline=project / 'baseline.sh')
    assert mutation.mutate(project)['counts'] == result['counts']  # Historical inspection remains usable.


def test_failed_init_is_not_resumable(fresh_project, monkeypatch):
    def fail_init(argv, *args):
        argv = [Path(argv[0]).name, *argv[1:]]
        return 7 if argv == ['mcy', 'init'] else 0
    monkeypatch.setattr(mutation, 'run_job', fail_init)
    with pytest.raises(ValueError, match='mcy init failed'):
        mutation.mutate(fresh_project, run=True, baseline=fresh_project / 'baseline.sh')
    assert not (fresh_project / 'database').exists()
    with pytest.raises(ValueError, match='fresh project'):
        mutation.mutate(fresh_project, run=True, baseline=fresh_project / 'baseline.sh')


@pytest.mark.parametrize('stage', ['baseline', 'init', 'run'])
@pytest.mark.parametrize('filename', ['baseline.sh', 'config.mcy'])
def test_fresh_run_refuses_known_input_changed_during_execution(fresh_project, monkeypatch, stage, filename):
    execute = mutation.run_job
    baseline = fresh_project / 'baseline.sh'

    def change_input(argv, *args):
        rc = execute(argv, *args)
        argv = [Path(argv[0]).name, *argv[1:]]
        if ((stage == 'baseline' and argv[0] == 'bash') or
                (stage == 'init' and argv == ['mcy', 'init']) or
                (stage == 'run' and argv[:2] == ['mcy', 'run'])):
            (Path(args[0]) / filename).write_text('changed input\n')
        return rc
    monkeypatch.setattr(mutation, 'run_job', change_input)
    with pytest.raises(ValueError, match='execution changed input'):
        mutation.mutate(fresh_project, run=True, baseline=baseline)


def test_fresh_run_refuses_changed_mcy_listed_file(fresh_project, monkeypatch):
    execute = mutation.run_job

    def change_source(argv, *args):
        rc = execute(argv, *args)
        argv = [Path(argv[0]).name, *argv[1:]]
        if argv[:2] == ['mcy', 'run']:
            (Path(args[0]) / 'design.sv').write_text('module changed; endmodule\n')
        return rc
    monkeypatch.setattr(mutation, 'run_job', change_source)
    with pytest.raises(ValueError, match='execution changed input'):
        mutation.mutate(fresh_project, run=True, baseline=fresh_project / 'baseline.sh')
