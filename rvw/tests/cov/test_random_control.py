"""The random control arm does not inspect measured coverage holes."""
import json
import pytest
from rvw.common.riscv import decode
from rvw.cov import random_candidate
from .test_stimulus import source
from .test_campaign import setup
from rvw.cov import campaign as c

pytestmark = pytest.mark.fast


def test_uniform_candidates_decode_and_replay(tmp_path):
    manifest = source(tmp_path)
    words = []
    for index in range(32):
        candidate = random_candidate.generate(manifest, tmp_path, tmp_path/str(index), [5, 6, 7], index)
        word = candidate['model']['instruction']
        assert decode(word, 32).mnemonic in random_candidate.R_TYPE + random_candidate.I_TYPE
        assert word >> 7 & 31 == 5 and word >> 15 & 31 == 6
        assert candidate['measured_hits'] == []
        words.append(word)
    replay = random_candidate.generate(manifest, tmp_path, tmp_path/'replay', [5, 6, 7], 0)
    assert replay['model']['instruction'] == words[0]
    assert len(set(words)) > 20


def test_control_keeps_fixed_budget_after_all_hits(tmp_path, monkeypatch):
    settings = setup(tmp_path, monkeypatch)
    data = json.loads(settings.read_text()); data['strategy'] = 'random'
    settings.write_text(json.dumps(data))
    seen = []
    def generate(manifest, root, directory, registers, seed):
        seen.append(seed)
        directory.mkdir(); path = directory/'payload.S'; path.write_text('.word 0x33')
        return {'status':'generated', 'source':str(path)}
    monkeypatch.setattr(random_candidate, 'generate', generate)
    monkeypatch.setattr(c, 'qualify', lambda *a: {'status':'qualified', 'execution_identity':'fixture-native',
        'coverage':{'groups':{'g':{'hits':[{'bin':[1],'count':1},{'bin':[2],'count':1}]}}}})
    result = c.campaign(settings, tmp_path/'out')
    assert seen == [1,2]
    assert [a['new_hits'] for a in result['attempts']] == [['g:[1]','g:[2]'],[]]


@pytest.mark.parametrize('status,complete', [('mismatch', True), ('match', False)])
def test_initial_suite_rejects_unqualified_reference(tmp_path, monkeypatch, status, complete):
    from types import SimpleNamespace
    from rvw.cov import initial_coverage as initial
    elf = tmp_path/'program'; elf.write_bytes(b'ELF')
    result = tmp_path/'result.json'; result.write_text('{}')
    trace = tmp_path/'rvfi.jsonl'; trace.write_text('{}\n')
    run = SimpleNamespace(elf=str(elf), elf_sha256=initial.digest(elf), path=tmp_path,
                          why_inconclusive=None, status='pass', instret=3, core='fixture',
                          artifact=lambda name:trace if name == 'rvfi_trace' else None)
    monkeypatch.setattr(initial, 'load_run', lambda _:run)
    monkeypatch.setattr(initial, 'cosim', lambda *a, **kw: dict(status=status, trace_complete=complete,
                        instructions=3, end_status='pass'))
    monkeypatch.setattr(initial, 'functional', lambda *a, **kw: pytest.fail('unqualified coverage'))
    with pytest.raises(ValueError, match='complete strict Spike'):
        initial.measure([result], tmp_path/'platform', tmp_path/'manifest', tmp_path)


def test_initial_coverage_populates_holes_before_selection(tmp_path, monkeypatch):
    from rvw.cov import initial_coverage
    from types import SimpleNamespace
    settings = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(c, 'load_config', lambda **kw: SimpleNamespace(configs=['test'], name='fixture'))
    data = json.loads(settings.read_text()); data['initial_results'] = ['initial/result.json']
    settings.write_text(json.dumps(data))
    monkeypatch.setattr(initial_coverage, 'measure', lambda *a: {'execution_identity':'fixture-native',
        'records':[], 'coverage':{'groups':{'g':{'hits':[{'bin':[1],'count':1}]}}}})
    seen = []
    def generate(manifest, root, goal, *args):
        seen.append(goal); return {'status':'unsat'}
    monkeypatch.setattr(c, 'generate', generate)
    report = c.campaign(settings, tmp_path/'out')
    assert seen == ['g:[2]']
    assert report['hits'] == ['g:[1]']
    assert report['execution_identity'] == 'fixture-native'
    resumed = c.campaign(settings, tmp_path/'out', resume=True)
    assert resumed['hits'] == report['hits']


def test_initial_suite_uses_captured_replay_elf(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from rvw.cov import initial_coverage as initial
    result = tmp_path/'result.json'; result.write_text('{}')
    elf = tmp_path/'replay.elf'; elf.write_bytes(b'captured ELF')
    trace = tmp_path/'rvfi.jsonl'; trace.write_text('{}\n')
    artifacts = {'rvfi_trace':trace, 'replay_elf':elf}
    run = SimpleNamespace(elf=str(tmp_path/'removed-input'), elf_sha256=initial.digest(elf),
                          path=tmp_path, why_inconclusive=None, status='pass', instret=3,
                          core='fixture', config='test', artifact=artifacts.get)
    monkeypatch.setattr(initial, 'load_run', lambda _:run)
    def compare(*args, **kw):
        assert kw['elf'] == str(elf) and kw['strict'] is True
        return dict(status='match', trace_complete=True, end_status='pass', instructions=3)
    monkeypatch.setattr(initial, 'cosim', compare)
    monkeypatch.setattr(initial, 'execution_identity', lambda *a:'fixture-native')
    monkeypatch.setattr(initial, 'functional', lambda *a, **kw:{'groups':{}})
    measured = initial.measure([result], tmp_path/'platform', tmp_path/'manifest', tmp_path, 'fixture', 'test')
    assert measured['records'][0]['elf_sha256'] == initial.digest(elf)
    assert measured['records'][0]['comparison']['status'] == 'match'
