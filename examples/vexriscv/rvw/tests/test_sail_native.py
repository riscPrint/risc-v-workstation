"""Independent Sail checks with explicit capture and ECALL policy bounds."""
import json
import sys

import pytest
from rvw.common.proc import run_group
from test_adapter import compile_elf, invoke, EXAMPLE


def adjudicate(elf, trace):
    result = run_group([sys.executable, '-m', 'rvw', 'cosim', 'adjudicate',
                       '--core', 'vexriscv', '--platform', str(EXAMPLE/'platform.json'),
                       '--elf', str(elf), '--trace', str(trace)],
                       capture=True, text=True, timeout=120)
    return json.loads(result.stdout)


def capture(tmp_path, monkeypatch, instructions):
    monkeypatch.setenv('RVW_VEX_CSR_CAPTURE', '0')
    monkeypatch.delenv('RVW_COSIM_DPI', raising=False)
    elf = compile_elf(tmp_path, 'sail', instructions)
    out = tmp_path/'run'
    result = invoke(['run', '--elf', elf, '--out', out, '--mem-latency', 0,
                     '--max-cycles', 2000, '--seed', 1, '--rvfi-trace', '--json'])
    assert result.returncode == 0, result.stderr + result.stdout
    trace = out/'rvfi.jsonl'
    assert json.loads(trace.read_text().splitlines()[0])['schema'] == 'rvw.rvfi/1'
    return elf, trace


def test_native_absent_pmp_values_and_negative_control(tmp_path, monkeypatch):
    elf, trace = capture(tmp_path, monkeypatch, '''
  csrr a0, pmpaddr0
  li t0, 123
  csrw pmpaddr0, t0
  csrr a1, pmpaddr0
  csrr a2, pmpcfg0
  or a0, a0, a1
  or a0, a0, a2
  bnez a0, fail
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
fail:
  la t0, tohost
  li t1, 3
  sw t1, 0(t0)
''')
    report = adjudicate(elf, trace)
    (tmp_path/'match.json').write_text(json.dumps(report))
    assert report['status'] == 'match', report
    rows = [json.loads(l) for l in trace.read_text().splitlines()]
    row = next(r for r in rows if r.get('rd') == 10)
    row['rd_wdata'] = hex(int(row['rd_wdata'], 16) ^ 1)
    changed = tmp_path/'changed.jsonl'
    changed.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    report = adjudicate(elf, changed)
    assert report['status'] == 'mismatch', report
    assert all(r['status'] == 'mismatch' for r in report['references'].values())


@pytest.mark.parametrize('overwrite', [False, True])
def test_native_ecall_policy_does_not_invent_sail_csr_state(tmp_path, monkeypatch, overwrite):
    elf, trace = capture(tmp_path, monkeypatch, '''
  la t0, handler
  csrw mtvec, t0
  ecall
handler:
''' + ('  csrwi mtval, 5\n' if overwrite else '') + '''
  csrr a0, mtval
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
''')
    report = adjudicate(elf, trace)
    (tmp_path/'adjudication.json').write_text(json.dumps(report))
    assert report['references']['spike']['status'] == 'match', report
    if overwrite:
        assert report['status'] == 'match', report
    else:
        assert report['status'] == 'inconclusive', report
        sail = report['references']['sail']
        assert sail['status'] == 'error' and 'cannot propagate' in sail['message']
