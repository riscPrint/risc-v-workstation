"""Coverage reductions need conclusive C1 and C3 evidence, for every status."""
import json
from pathlib import Path
import subprocess

import pytest

from rvw.cli import main
from rvw.cov.code import merge, rank, report, select
from rvw.mcp.registry import Registry

from .test_code import dat


INCONCLUSIVE = [
    {"inconclusive": "input identity changed before result publication: adapter identity; rerun"},
    {"inconclusive": True},
    {"synthesized": True},
    {"wall_clock_timeout": True},
    {"status": "error"},
    {"status": "assert", "details": {"concurrent": True}},
    {"status": "rvfi_error", "details": {"serial_rerun": {"attributed": False}}},
]


def run_result(**extra):
    return {"schema": "rvw.run/1", "status": "pass", "elf": "A",
            "artifacts": {"coverage": "coverage.dat"}, **extra}


@pytest.mark.parametrize('status', ['pass', 'fail', 'assert', 'rvfi_error', 'timeout'])
@pytest.mark.parametrize('extra', INCONCLUSIVE)
def test_merge_rejects_inconclusive_c1(tmp_path, status, extra):
    dat(tmp_path / 'coverage.dat', [1, 0])
    (tmp_path / 'result.json').write_text(json.dumps(run_result(**{"status": status, **extra})))
    with pytest.raises(ValueError, match='inconclusive'):
        merge([str(tmp_path)])


@pytest.mark.parametrize('entry', [
    {"inconclusive": "suite inputs changed"}, {"inconclusive": True},
    {"synthesized": True}, {"wall_clock_timeout": True},
    {"status": "error", "signature": "error:adapter"},
    {"status": "timeout", "signature": "timeout:wall-clock"},
])
def test_merge_rejects_inconclusive_c3_even_with_conclusive_c1(tmp_path, entry):
    dat(tmp_path / 'coverage.dat', [1])
    (tmp_path / 'result.json').write_text(json.dumps(run_result()))
    suite = {"schema": "rvw.results/1", "run_id": "test", "suite": "isa", "core": "test",
             "config": "small", "created": "now",
             "tests": [{"id": "A", "status": "pass", "run": "result.json", **entry}]}
    (tmp_path / 'results.json').write_text(json.dumps(suite))
    with pytest.raises(ValueError, match='inconclusive'):
        merge([str(tmp_path)])


def test_merge_checks_c1_when_c3_entry_is_conclusive(tmp_path):
    dat(tmp_path / 'coverage.dat', [1])
    (tmp_path / 'result.json').write_text(json.dumps(run_result(**INCONCLUSIVE[0])))
    suite = {"schema": "rvw.results/1", "run_id": "test", "suite": "isa", "core": "test",
             "config": "small", "created": "now",
             "tests": [{"id": "A", "status": "pass", "run": "result.json"}]}
    (tmp_path / 'results.json').write_text(json.dumps(suite))
    with pytest.raises(ValueError, match='input identity changed'):
        merge([str(tmp_path)])


@pytest.fixture
def coverage_change(tmp_path):
    def git(*args):
        return subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test',
                               '-c', 'user.email=t@x', *args], check=True,
                              capture_output=True, text=True).stdout.strip()
    git('init', '-q')
    source = tmp_path / 'Unit.scala'
    source.write_text('val a = io.x + 1\nval b = io.y + 1\n')
    git('add', 'Unit.scala')
    git('commit', '-qm', 'base')
    base = git('rev-parse', 'HEAD')
    (tmp_path / 'logic.v').write_text('assign a=x+1; // @ Unit.scala l1\n'
                                     'assign b=y+1; // @ Unit.scala l2\n')
    paths = []
    for name, counts in [('A', [1, 0]), ('B', [0, 1])]:
        folder = tmp_path / name
        folder.mkdir()
        dat(folder / 'coverage.dat', counts)
        (folder / 'result.json').write_text(json.dumps(run_result(
            elf=name, source={"core_rev": base, "core_dirty": False})))
        paths.append(str(folder))
    data = merge(paths, tmp_path)
    source.write_text('val a = io.x + 2\nval b = io.y + 1\n')
    git('commit', '-qam', 'change')
    return data, paths


@pytest.mark.parametrize('name', ['A', 'B'])
@pytest.mark.parametrize('extra', INCONCLUSIVE)
def test_saved_inconclusive_evidence_forces_all_tests(coverage_change, tmp_path, name, extra):
    data, _ = coverage_change
    assert select(data, 'HEAD~1..HEAD', tmp_path)['tests'] == ['A']
    # Model a database written before this fix; merge must now refuse to create it.
    data['tests'][name]['run'].update(extra)
    result = select(data, 'HEAD~1..HEAD', tmp_path)
    assert result['fallback_all'] and result['tests'] == ['A', 'B']
    assert 'inconclusive_runs' in result['fallback_reasons']
    assert result['inconclusive_runs'][name]
    assert name not in result['direct_tests']
    # BASE..BASE needs no evidence and still selects nothing.
    unchanged = select(data, 'HEAD~1..HEAD~1', tmp_path)
    assert not unchanged['fallback_all'] and unchanged['tests'] == []
    for read in (report, rank):
        with pytest.raises(ValueError, match='inconclusive'):
            read(data)


@pytest.mark.parametrize('status', ['fail', 'assert', 'rvfi_error', 'timeout'])
def test_conclusive_failures_still_contribute(coverage_change, tmp_path, status):
    _, paths = coverage_change
    for path in paths:
        file = Path(path) / 'result.json'
        obj = json.loads(file.read_text())
        obj['status'] = status
        file.write_text(json.dumps(obj))
    data = merge(paths, tmp_path)
    assert report(data)['summary']['hit'] == 2
    assert rank(data)['selected'] == ['A', 'B']
    result = select(data, 'HEAD~1..HEAD', tmp_path)
    assert result['tests'] == ['A'] and not result['fallback_all']


def test_cli_and_mcp_share_merge_refusal_and_selection_fallback(coverage_change, tmp_path, capsys):
    data, paths = coverage_change
    reason = INCONCLUSIVE[0]['inconclusive']
    data['tests']['A']['run']['inconclusive'] = reason
    database = tmp_path / 'coverage.json'
    database.write_text(json.dumps(data))
    c1 = tmp_path / 'A/result.json'
    c1.write_text(json.dumps(data['tests']['A']['run']))
    assert main(['cov', 'merge', *paths, '--json']) == 2
    error = json.loads(capsys.readouterr().out)['error']
    assert reason in error
    assert main(['cov', 'select', str(database), '--repo', str(tmp_path),
                 '--diff', 'HEAD~1..HEAD', '--json']) == 0
    expected = json.loads(capsys.readouterr().out)
    assert expected['fallback_all'] and expected['tests'] == ['A', 'B']
    registry, problems = Registry.discover({'cov'})
    assert not problems
    try:
        for tool, arguments, state in [
            ('cov_merge', {'inputs': paths}, 'failed'),
            ('cov_select', {'database': str(database), 'repo': str(tmp_path),
                            'diff': 'HEAD~1..HEAD'}, 'done'),
        ]:
            _, started, failed = registry.call_json(tool, arguments)
            assert not failed, started
            _, job, failed = registry.call_json('job_status', {'job_id': started['job_id'], 'wait_s': 60})
            assert not failed and job['status'] == state, job
            if state == 'done':
                assert job['result'] == expected
            else:
                assert error in job['error']
    finally:
        registry.jobs.shutdown()
