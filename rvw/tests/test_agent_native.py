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
    assert pack['environment']['RVW_VEX_LOCK'] == 'vex-agentbench'
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
    return {'status': status, 'identity': {'rtl_sha256': rtl, 'elf_sha256': 'e' * 64, 'seed': 1, 'config': 'default', 'source': {'tools_rev': 'c' * 40}}}


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
    wrong = copy.deepcopy(repaired)
    wrong['broken']['identity']['source']['tools_rev'] = 'd' * 40
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
        assert argv[:3] == ['nice', '-n', '15']
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


def test_incomplete_seeded_batch_does_not_start_a_repair_batch(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    (source / 'src').mkdir(parents=True)
    (source / 'src/a').write_text('correct')
    native.git(source, 'init', '-q')
    native.git(source, 'add', '-A')
    native.git(source, 'commit', '-qm', 'input')
    task = {'id': 'a', 'private': {'mutation': {'file': 'src/a', 'find': 'correct', 'replace': 'wrong'},
                                  'fail_to_pass': ['broken'], 'pass_to_pass': ['control']}}
    pack = {'schema': native.SCHEMA, 'source': {'revision': native.git(source, 'rev-parse', 'HEAD'), 'copy': ['src']},
            'tasks': [task]}
    pack_path = tmp_path / 'pack.json'
    pack_path.write_text(json.dumps(pack))
    calls = []
    def run(*args):
        calls.append(args)
        return {name: {'status': 'inconclusive'} for name in ('broken', 'control')}
    monkeypatch.setattr(native, 'run_tests', run)
    report = native.qualify(pack_path, source, tmp_path / 'qualification')
    assert len(calls) == 1
    assert report['tasks'][0]['status'] == 'inconclusive'
    assert report['tasks'][0]['repaired'] == {}
    assert report['tasks'][0]['reason'] == 'baseline did not pass and match'


def test_native_verdict_requires_baseline_and_first_spike_mismatch():
    task = {'private': {'fail_to_pass': ['broken'], 'pass_to_pass': ['control']}}
    baseline = {n: {**evidence('pass', 'b' * 64), 'cosim': {'status': 'match'}} for n in ('broken', 'control')}
    seeded = {'broken': {**evidence('fail'), 'cosim': {'status': 'mismatch', 'mismatch': {'pc': '0x80000000'}}},
              'control': {**evidence('pass'), 'cosim': {'status': 'match'}}}
    repaired = copy.deepcopy(baseline)
    assert native.native_verdict(task, baseline, seeded, repaired) == 'qualified'
    assert native.native_verdict(task, {}, seeded, repaired) == 'inconclusive'
    for phase, name in ((baseline, 'broken'), (seeded, 'control'), (repaired, 'broken')):
        previous = phase[name]['cosim']
        phase[name]['cosim'] = {'status': 'inconclusive'}
        assert native.native_verdict(task, baseline, seeded, repaired) == 'inconclusive'
        phase[name]['cosim'] = previous
    seeded['broken']['cosim']['mismatch'] = None
    assert native.native_verdict(task, baseline, seeded, repaired) == 'inconclusive'


def test_reference_failure_cannot_earn_match(tmp_path, monkeypatch):
    from types import SimpleNamespace
    result_path = tmp_path / 'batch' / 'broken' / 'result.json'
    result_path.parent.mkdir(parents=True)
    runs = {'broken': {'result': str(result_path), 'trace': str(result_path.with_name('rvfi.jsonl'))}}
    def invoke(argv, **kwargs):
        assert '--strict' in argv and '--platform' in argv and '--core' in argv
        return SimpleNamespace(stdout='{"status":"match"}', stderr='reference failed', returncode=2, timed_out=False)
    monkeypatch.setattr(native, 'run_group', invoke)
    native.reference_checks({'source': {'env': 'TEST_CORE'}, 'programs': 'programs', 'platform': 'platform.json'},
                            tmp_path, tmp_path, runs, 1)
    assert runs['broken']['cosim']['status'] == 'inconclusive'
    assert runs['broken']['cosim']['exit_code'] == 2
    assert runs['broken']['cosim']['wall_s'] >= 0


def test_cycle_limit_needs_complete_trace_and_spike_divergence():
    task = {'private': {'fail_to_pass': ['broken'], 'pass_to_pass': ['control']}}
    baseline = {n: {**evidence('pass', 'b' * 64), 'cosim': {'status': 'match'}} for n in ('broken', 'control')}
    seeded = {'broken': {**evidence('timeout'), 'trace_complete': True, 'timed_out': False,
                         'cosim': {'status': 'mismatch', 'mismatch': {'instruction_index': 5}}},
              'control': {**evidence('pass'), 'cosim': {'status': 'match'}}}
    repaired = copy.deepcopy(baseline)
    assert native.qualification(task, seeded, repaired) == 'inconclusive'
    assert native.native_verdict(task, baseline, seeded, repaired) == 'qualified'
    assert seeded['broken']['status'] == 'timeout'
    for field, value in (('trace_complete', False), ('timed_out', True)):
        changed = copy.deepcopy(seeded)
        changed['broken'][field] = value
        assert native.native_verdict(task, baseline, changed, repaired) == 'inconclusive'
    seeded['broken']['cosim']['status'] = 'match'
    assert native.native_verdict(task, baseline, seeded, repaired) == 'inconclusive'


def test_reuse_keeps_source_path_rechecks_inputs_and_preserves_attempt(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    (source / 'src').mkdir(parents=True)
    (source / 'src/core.scala').write_text('correct')
    (source / 'src/.gitignore').write_text('ignored.bin\n')
    (source / 'src/ignored.bin').write_bytes(b'pinned resource')
    native.git(source, 'init', '-q')
    native.git(source, 'add', '-A')
    native.git(source, 'add', '-f', 'src/ignored.bin')
    native.git(source, 'commit', '-qm', 'input')
    task = {'id': 'a', 'private': {'mutation': {'file': 'src/core.scala', 'find': 'correct', 'replace': 'wrong'},
                                  'fail_to_pass': ['broken'], 'pass_to_pass': ['control']}}
    pack = {'schema': native.SCHEMA, 'source': {'revision': native.git(source, 'rev-parse', 'HEAD'), 'copy': ['src']},
            'tasks': [task]}
    path = tmp_path / 'pack.json'
    path.write_text(json.dumps(pack))
    calls = []
    def run(*arguments):
        calls.append(arguments)
        return {n: {'status': 'inconclusive'} for n in ('broken', 'control')}
    monkeypatch.setattr(native, 'run_tests', run)
    out = tmp_path / 'run'
    first = native.qualify(path, source, out)
    pack['seed'] = 2
    path.write_text(json.dumps(pack))
    second = native.qualify(path, source, out, reuse_workspace=True)
    assert first['attempt'] == 1 and second['attempt'] == 2
    assert second['previous_pack_sha256'] == first['pack_sha256'] != second['pack_sha256']
    assert calls[0][2] == calls[1][2] == out / 'workspace'
    assert calls[1][3] == out / 'attempt-2/baseline'
    assert json.loads((out / 'qualification-attempt-1.json').read_text()) == first
    assert (source / 'src/core.scala').read_text() == 'correct'
    assert second['tasks'][0]['status'] == 'inconclusive'
    with pytest.raises(ValueError, match='original source checkout'):
        native.verify_workspace(pack, source, source)
    (out / 'workspace/src/ignored.bin').write_bytes(b'changed ignored resource')
    with pytest.raises(ValueError, match='differs'):
        native.verify_workspace(pack, source, out / 'workspace')
    (out / 'workspace/src/ignored.bin').write_bytes(b'pinned resource')
    (out / 'workspace/src/core.scala').write_text('unreviewed candidate')
    native.git(out / 'workspace', 'add', '-A')
    native.git(out / 'workspace', 'commit', '-qm', 'change')
    before = (out / 'qualification.json').read_bytes()
    with pytest.raises(ValueError, match='differs'):
        native.qualify(path, source, out, reuse_workspace=True)
    assert (out / 'qualification.json').read_bytes() == before
