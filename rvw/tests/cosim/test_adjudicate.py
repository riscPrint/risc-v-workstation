import copy
from rvw.cosim.adjudicate import adjudicate


def result(status='match', index=0, value='0x1'):
    row = dict(status=status, instructions=3 if status == 'match' else index, trace_complete=True,
               reproduction=dict(elf_sha256='e', trace_sha256='t', platform_sha256='p'))
    if status == 'mismatch':
        row['mismatch'] = dict(instruction_index=index, differences=dict(rd_wdata=dict(expected=value, actual='0x0')))
    return row


def test_both_match_and_common_input():
    reports = dict(spike=result(), sail=result())
    assert adjudicate(reports)['status'] == 'match'
    reports['sail']['reproduction']['trace_sha256'] = 'other'
    assert adjudicate(reports)['status'] == 'inconclusive'


def test_dut_matches_one_reference():
    reports = dict(spike=result('mismatch'), sail=result())
    report = adjudicate(reports)
    assert report['status'] == 'disagreement'
    assert report['dut_matches_at_boundary'] == ['sail']
    assert report['references'] == reports


def test_both_reject_same_or_different_result():
    reports = dict(spike=result('mismatch'), sail=result('mismatch'))
    assert adjudicate(reports)['status'] == 'mismatch'
    reports['sail'] = result('mismatch', value='0x2')
    assert adjudicate(reports)['status'] == 'disagreement'
    assert adjudicate(reports)['dut_matches_at_boundary'] == []


def test_coverage_or_missing_reference_never_passes():
    reports = dict(spike=result(), sail=result())
    reports['sail']['uncompared_instructions'] = 1
    assert adjudicate(reports)['status'] == 'inconclusive'
    reports['sail']['status'] = 'error'
    assert adjudicate(reports)['status'] == 'inconclusive'


def test_native_spike_and_sail_flow(tmp_path, tmp_path_factory, monkeypatch):
    from pathlib import Path
    import pytest
    from cosim_build import _build
    from model_fixtures import generate
    from rvw.cosim.platform import Platform
    from rvw.cosim.adjudicate import execute_json
    sail = Path('/Users/mahir/fun/saviour/ref/sail/sail-riscv-Mac-arm64/bin/sail_riscv_sim')
    if not sail.exists():
        pytest.skip('native Sail executable not installed')
    monkeypatch.setenv('RVW_SAIL', str(sail))
    source = tmp_path/'both.S'
    source.write_text('''.section .text
.globl _start
_start:
 li a0, 7
 la t0, tohost
 li t1, 1
 sd t1, 0(t0)
1: j 1b
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
''')
    elf = _build(tmp_path_factory, source)
    trace = tmp_path/'trace.jsonl'
    assert generate(elf, trace, Platform.load('boom'), 100)['termination'] == 'pass'
    result = execute_json(elf=str(elf), trace=str(trace), core='boom', strict=True)
    assert result['status'] == 'match', result
    assert set(result['matched_references']) == {'spike', 'sail'}
