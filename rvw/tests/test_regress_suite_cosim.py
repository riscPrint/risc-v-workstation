"""`rvw regress cosim` gives one honest status per C1 result of a run."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from rvw.regress.commands import suite_cosim

pytestmark = pytest.mark.fast


def runs(tmp_path, monkeypatch, comparisons, **changes):
    paths, table = [], {}
    for i, name in enumerate(comparisons):
        path = tmp_path / 'generations' / 'g' / 'mmu' / 'rv64' / 'tests' / f't{i}' / 'result.json'
        path.parent.mkdir(parents=True)
        path.write_text('{}')
        run = SimpleNamespace(core='fixture', elf=f'/e/t{i}.elf', status='pass', message=None, why_inconclusive=None,
                              cycles=10, instret=2, artifact=lambda _: '/t/rvfi.jsonl')
        for k, v in changes.items():
            setattr(run, k, v)
        paths.append(path)
        table[path] = run
    monkeypatch.setattr(suite_cosim, 'owned_run_paths', lambda _: paths)
    monkeypatch.setattr(suite_cosim, 'load_run', lambda p: table[p])
    it = iter(comparisons)
    monkeypatch.setattr(suite_cosim, 'cosim', lambda *a, **k: next(it))


GOOD = dict(status='match', trace_complete=True, end_status='pass', instructions=2, synchronized=0)


@pytest.mark.parametrize('comparison,status', [
    (GOOD, 'match'),
    (dict(GOOD, status='mismatch', mismatch={'pc': '0x0'}), 'mismatch'),
    (dict(GOOD, synchronized=1), 'inconclusive'),
    (dict(GOOD, applied_masks=['x']), 'inconclusive'),
    (dict(GOOD, instructions=1), 'inconclusive'),
    (dict(GOOD, trace_complete=False), 'inconclusive')])
def test_only_complete_strict_matches_count(tmp_path, monkeypatch, comparison, status):
    runs(tmp_path, monkeypatch, [comparison])
    result = suite_cosim.check_run(tmp_path, tmp_path / 'platform.json')
    assert result['counts'] == {status: 1}
    assert result['suites'] == {'mmu': {status: 1}}


def test_failed_and_inconclusive_c1_are_not_compared(tmp_path, monkeypatch):
    runs(tmp_path, monkeypatch, [], status='fail', message='tohost = 0x3')
    monkeypatch.setattr(suite_cosim, 'cosim', lambda *a, **k: pytest.fail('must not compare'))
    assert suite_cosim.check_run(tmp_path, 'p.json')['rows'] == []
    runs(tmp_path / 'b', monkeypatch, [GOOD], status='fail', message='tohost = 0x3')
    monkeypatch.setattr(suite_cosim, 'cosim', lambda *a, **k: pytest.fail('must not compare'))
    assert suite_cosim.check_run(tmp_path, 'p.json')['counts'] == {'fail': 1}
    runs(tmp_path / 'c', monkeypatch, [GOOD], why_inconclusive='input_not_captured')
    monkeypatch.setattr(suite_cosim, 'cosim', lambda *a, **k: pytest.fail('must not compare'))
    assert suite_cosim.check_run(tmp_path, 'p.json')['counts'] == {'inconclusive': 1}


def test_harness_assert_is_an_error_not_a_program_failure(tmp_path, monkeypatch):
    runs(tmp_path, monkeypatch, [GOOD], status='assert', message='IllegalStateException')
    monkeypatch.setattr(suite_cosim, 'cosim', lambda *a, **k: pytest.fail('must not compare'))
    assert suite_cosim.check_run(tmp_path, 'p.json')['counts'] == {'error': 1}


RESET = dict(GOOD, synchronized=1, applied_masks=[dict(reason='csr_reset_unknown', csr='0x340')],
             recent_synchronizations=[dict(reason='csr_reset_unknown', csr='0x340')])
IRQ = dict(GOOD, synchronized=1, applied_masks=[dict(reason='irq', csr='0x344')],
           recent_synchronizations=[dict(reason='irq', csr='0x344')])


@pytest.mark.parametrize('comparison,allow,status,strict_sync', [
    (RESET, (), 'inconclusive', None),
    (RESET, ('reset',), 'match', ('counter', 'mmio', 'irq')),
    (IRQ, ('reset',), 'inconclusive', ('counter', 'mmio', 'irq')),
    (IRQ, ('irq', 'reset'), 'match', ('counter', 'mmio')),
    (dict(IRQ, applied_masks=[dict(reason='mmio')], recent_synchronizations=[dict(reason='mmio')]), ('irq',), 'inconclusive', ('counter', 'mmio', 'csr')),
    (dict(IRQ, applied_masks=[dict(reason='mmio')], recent_synchronizations=[dict(reason='mmio')]), ('mmio',), 'match', ('counter', 'csr', 'irq')),
    (dict(RESET, recent_synchronizations=[dict(reason='counter')]), ('reset',), 'inconclusive', ('counter', 'mmio', 'irq')),
    (dict(RESET, applied_masks=[dict(reason='csr', csr='0x300')]), ('reset',), 'inconclusive', ('counter', 'mmio', 'irq')),
    (dict(GOOD, synchronized=1), ('reset',), 'inconclusive', ('counter', 'mmio', 'irq')),
    (dict(GOOD, synchronized=1, recent_synchronizations=[dict(reason='mmio')]), ('mmio',), 'match', ('counter', 'csr', 'irq')),
    (dict(GOOD, synchronized=11, recent_synchronizations=[dict(reason='mmio')] * 10), ('mmio',), 'inconclusive', ('counter', 'csr', 'irq'))])
def test_allowed_sync_kinds_only(tmp_path, monkeypatch, comparison, allow, status, strict_sync):
    runs(tmp_path, monkeypatch, [comparison])
    calls = []
    original = suite_cosim.cosim
    monkeypatch.setattr(suite_cosim, 'cosim', lambda *a, **k: calls.append(k) or original(*a, **k))
    result = suite_cosim.check_run(tmp_path, 'p.json', allow=allow)
    assert result['counts'] == {status: 1}
    assert calls[0]['strict'] is (not allow)
    assert calls[0].get('strict_sync') == strict_sync


def test_unknown_sync_kind_is_refused(tmp_path):
    with pytest.raises(ValueError):
        suite_cosim.check_run(tmp_path, 'p.json', allow=('counter',))
