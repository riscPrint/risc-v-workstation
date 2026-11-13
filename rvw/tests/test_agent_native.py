"""Native task evidence and mutation checks without native tools."""
import copy
import json
from pathlib import Path

import pytest

from rvw.agent_bench import native

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def test_example_pack_is_pinned_and_keeps_core_data_outside_generic_code():
    pack, digest, base = native.load_pack(ROOT / 'examples/agent-bench/native.json')
    assert len(pack['tasks']) == 10 and len(digest) == 64
    assert len(pack['source']['revision']) == 40
    assert pack['environment']['RVW_VEX_LOCK'] == 'vex-agent'
    for task in pack['tasks']:
        assert 'mutation' not in task['public']
        assert task['private']['fail_to_pass'] and task['private']['pass_to_pass']


def test_occurrence_mutation_round_trip(tmp_path):
    p = tmp_path / 'source.scala'
    p.write_text('same\nsame\nsame\n')
    mutation = {'file': p.name, 'find': 'same', 'replace': 'wrong', 'occurrence': 2}
    native.mutate(tmp_path, mutation)
    assert p.read_text() == 'same\nwrong\nsame\n'
    native.mutate(tmp_path, mutation, reverse=True)
    assert p.read_text() == 'same\nsame\nsame\n'
    with pytest.raises(ValueError):
        native.mutate(tmp_path, {**mutation, 'occurrence': 4})


def evidence(status, rtl='a' * 64):
    return {'status': status, 'identity': {'rtl_sha256': rtl, 'elf_sha256': 'e' * 64, 'seed': 1, 'config': 'default'}}


def test_qualification_requires_failure_repair_controls_and_changed_rtl():
    task = {'private': {'fail_to_pass': ['broken'], 'pass_to_pass': ['control']}}
    seeded = {'broken': evidence('fail'), 'control': evidence('pass')}
    repaired = {n: evidence('pass', 'b' * 64) for n in seeded}
    assert native.qualification(task, seeded, repaired) == 'qualified'
    assert native.qualification(task, {}, repaired) == 'inconclusive'
    assert native.qualification(task, {**seeded, 'broken': evidence('pass')}, repaired) == 'unqualified'
    assert native.qualification(task, {**seeded, 'control': evidence('fail')}, repaired) == 'unqualified'
    for status in ('timeout', 'inconclusive', 'error'):
        assert native.qualification(task, {**seeded, 'broken': evidence(status)}, repaired) == 'inconclusive'
    assert native.qualification(task, seeded, {n: evidence('pass') for n in seeded}) == 'inconclusive'
    wrong = copy.deepcopy(repaired)
    wrong['broken']['identity']['elf_sha256'] = 'f' * 64
    assert native.qualification(task, seeded, wrong) == 'inconclusive'


def test_prepare_refuses_wrong_pin_and_never_changes_source(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'src').mkdir()
    (source / 'src/a').write_text('correct')
    native.git(source, 'init', '-q')
    native.git(source, 'add', '-A')
    native.git(source, 'commit', '-qm', 'input')
    pin = native.git(source, 'rev-parse', 'HEAD')
    task = {'private': {'mutation': {'file': 'src/a', 'find': 'correct', 'replace': 'wrong'}}}
    pack = {'source': {'revision': pin, 'copy': ['src']}}
    work = native.prepare(pack, source, tmp_path / 'workspace', task)
    assert (work / 'src/a').read_text() == 'wrong'
    assert (source / 'src/a').read_text() == 'correct'
    assert not native.git(work, 'status', '--porcelain')
    with pytest.raises(ValueError, match='pin'):
        native.prepare({'source': {**pack['source'], 'revision': '0' * 40}}, source, tmp_path / 'bad', task)
    (source / 'src/a').write_text('uncommitted')
    with pytest.raises(ValueError, match='dirty'):
        native.prepare(pack, source, tmp_path / 'dirty', task)


def test_batch_requires_matching_trace_identity_and_complete_end(tmp_path, monkeypatch):
    from types import SimpleNamespace
    program = tmp_path / 'programs'
    program.mkdir()
    (program / 'broken').write_bytes(b'ELF')
    identity = {'rtl_sha256': 'a' * 64, 'elf_sha256': native.hashlib.sha256(b'ELF').hexdigest(),
                'source': {'core_rev': 'a' * 40}, 'seed': 1, 'config': 'default'}
    variant = {}

    def invoke(argv, **kwargs):
        assert argv[:3] == ['nice', '-n', '10']
        manifest = Path(argv[argv.index('--manifest') + 1])
        jobs = [json.loads(line) for line in manifest.read_text().splitlines()]
        assert len(jobs) == 1
        for job in jobs:
            out = Path(job['out'])
            out.mkdir()
            (out / 'result.json').write_text(json.dumps({**identity, 'status': 'pass'}))
            (out / 'rvfi.jsonl').write_text('unit test: Trace is replaced below')
        return SimpleNamespace(stdout='', stderr='', returncode=0, timed_out=False)

    class Capture:
        def __init__(self, path):
            self.header = {**identity, **variant}
        def __iter__(self):
            return iter([{'order': 0}, {'event': 'end', 'status': 'pass'}])

    monkeypatch.setattr(native, 'run_group', invoke)
    monkeypatch.setattr(native, 'Trace', Capture)
    pack = {'adapter': 'adapter.sh', 'programs': 'programs', 'source': {'env': 'TEST_CORE'}, 'config': 'default'}
    assert native.run_tests(pack, tmp_path, tmp_path, tmp_path / 'good', ['broken'], 1)['broken']['status'] == 'pass'
    variant['elf_sha256'] = 'f' * 64
    assert native.run_tests(pack, tmp_path, tmp_path, tmp_path / 'bad', ['broken'], 1)['broken']['status'] == 'inconclusive'
