"""Independent native repair-loop checks with a controlled runner fixture."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rvw.agent_bench import native, repair

pytestmark = pytest.mark.fast


@pytest.fixture
def challenge_inputs(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    (source / 'src').mkdir(parents=True)
    (source / 'src/core.scala').write_text('correct')
    native.git(source, 'init', '-q')
    native.git(source, 'add', '-A')
    native.git(source, 'commit', '-qm', 'input')
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'rvw.toml').write_text('project data')
    pack = {'schema': native.SCHEMA, 'source': {'revision': native.git(source, 'rev-parse', 'HEAD'),
                'env': 'TEST_CORE', 'copy': ['src']}, 'adapter': 'adapter', 'programs': 'programs', 'config': 'default',
            'project_copy': [{'source': 'project/rvw.toml', 'dest': 'rvw.toml'}],
            'tasks': [{'id': 'broken', 'public': {'summary': 'Repair the failing program.', 'failing': ['broken']},
                       'private': {'mutation': {'file': 'src/core.scala', 'find': 'correct', 'replace': 'wrong'},
                                   'fail_to_pass': ['broken'], 'pass_to_pass': ['control']}}]}
    path = tmp_path / 'pack.json'
    path.write_text(json.dumps(pack))
    calls = []
    def run_tests(pack, base, workspace, out, tests, timeout):
        wrong = (Path(workspace) / 'src/core.scala').read_text() != 'correct'
        calls.append(Path(workspace))
        return {n: {'status': 'fail' if n == 'broken' and wrong else 'pass',
                    'identity': {'rtl_sha256': ('a' if wrong else 'b') * 64,
                                 'elf_sha256': 'e' * 64, 'seed': 1, 'config': 'default',
                                 'source': {'tools_rev': 'c' * 40}},
                    'result': str(Path(out) / n / 'result.json'), 'trace': str(Path(out) / n / 'rvfi.jsonl')}
                for n in tests}
    monkeypatch.setattr(native, 'run_tests', run_tests)
    monkeypatch.setattr(repair, 'run_group', lambda *a, **k: SimpleNamespace(stdout='{}', stderr='', returncode=0, timed_out=False))
    return source, path, calls


def test_reproduces_failure_checks_only_source_and_rejects_wrong_fix(tmp_path, challenge_inputs):
    source, pack, calls = challenge_inputs
    state = repair.prepare_challenge(pack, 'broken', source, tmp_path / 'challenge')
    assert state['status'] == 'ready' and state['reproduced']
    workspace = Path(state['workspace'])
    assert (workspace / 'rvw.toml').read_text() == 'project data'
    assert (workspace / 'TASK.md').exists()
    assert not native.git(workspace, 'status', '--porcelain')
    assert set(state['diagnostics']['broken']) == {'bundle', 'cosim'}
    (workspace / 'src/core.scala').write_text('another wrong fix')
    wrong = repair.check_challenge(tmp_path / 'challenge/challenge.json', tmp_path / 'wrong')
    assert wrong['status'] == 'repair_rejected'
    (workspace / 'src/core.scala').write_text('correct')
    (workspace / 'rvw.toml').write_text('agent tries to change the tests')
    result = repair.check_challenge(tmp_path / 'challenge/challenge.json', tmp_path / 'checked')
    assert result['status'] == 'repair_verified'
    assert result['ignored_files'] == ['rvw.toml']
    assert result['source_files'] == ['src/core.scala']
    assert result['root_cause'].startswith('unknown')
    assert result['c4_acceptance'] == 'NOT CLAIMED' and result['human_review'] == 'required'
    assert (source / 'src/core.scala').read_text() == 'correct'
    assert len(result['candidate_patch_sha256']) == 64
    assert 'wrong' in (tmp_path / 'checked/candidate.patch').read_text()


def test_missing_reproduction_cannot_earn_repair_even_if_candidate_passes(tmp_path, challenge_inputs):
    source, pack, _ = challenge_inputs
    state = repair.prepare_challenge(pack, 'broken', source, tmp_path / 'challenge')
    state['reproduced'] = False
    path = tmp_path / 'challenge/challenge.json'
    path.write_text(json.dumps(state))
    (Path(state['workspace']) / 'src/core.scala').write_text('correct')
    assert repair.check_challenge(path, tmp_path / 'checked')['status'] == 'inconclusive'


def test_changed_pack_refuses_evaluation(tmp_path, challenge_inputs):
    source, pack, _ = challenge_inputs
    repair.prepare_challenge(pack, 'broken', source, tmp_path / 'challenge')
    pack.write_text(pack.read_text() + '\n')
    with pytest.raises(ValueError, match='changed'):
        repair.check_challenge(tmp_path / 'challenge/challenge.json', tmp_path / 'checked')


def test_named_pass_cannot_hide_independent_failure(tmp_path, challenge_inputs, monkeypatch):
    source, pack_path, _ = challenge_inputs
    pack = json.loads(pack_path.read_text())
    pack['tasks'][0]['private']['pass_to_pass'].append('hidden')
    pack_path.write_text(json.dumps(pack))
    original = native.run_tests
    def run_tests(pack, base, workspace, out, tests, timeout):
        result = original(pack, base, workspace, out, tests, timeout)
        if (Path(workspace) / 'src/core.scala').read_text() == 'named-test-only':
            result['broken']['status'] = 'pass'
            result['hidden']['status'] = 'fail'
        return result
    monkeypatch.setattr(native, 'run_tests', run_tests)
    state = repair.prepare_challenge(pack_path, 'broken', source, tmp_path / 'challenge')
    assert state['reproduced']
    (Path(state['workspace']) / 'src/core.scala').write_text('named-test-only')
    result = repair.check_challenge(tmp_path / 'challenge/challenge.json', tmp_path / 'checked')
    assert result['repaired']['broken']['status'] == 'pass'
    assert result['repaired']['hidden']['status'] == 'fail'
    assert result['status'] == 'repair_rejected'
