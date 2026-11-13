"""Lossless RVVI round trips of real native retirement and CSR captures."""
import json
import sys

import pytest
from rvw.common.proc import run_group
from rvw.cosim.exchange import convert
from rvw.cosim.doctor import execute_json as inspect
from test_adapter import compile_elf, invoke, EXAMPLE


def check(elf, trace):
    result = run_group([sys.executable, '-m', 'rvw', 'cosim', 'check',
                       '--core', 'vexriscv', '--platform', str(EXAMPLE/'platform.json'),
                       '--elf', str(elf), '--trace', str(trace), '--json'],
                       capture=True, text=True, timeout=120)
    return json.loads(result.stdout)


@pytest.mark.parametrize('full', [False, True])
def test_native_rvvi_roundtrip(tmp_path, monkeypatch, full):
    monkeypatch.setenv('RVW_VEX_CSR_CAPTURE', '1')
    monkeypatch.setenv('RVW_VEX_CSR_FULL', '1' if full else '0')
    monkeypatch.delenv('RVW_COSIM_DPI', raising=False)
    elf = compile_elf(tmp_path, 'rvvi', '''
  la t0, handler
  csrw mtvec, t0
  csrwi mscratch, 7
  ecall
handler:
  csrr a0, mcause
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
''')
    out = tmp_path/'run'
    result = invoke(['run', '--elf', elf, '--out', out, '--mem-latency', 0,
                     '--max-cycles', 2000, '--seed', 1, '--rvfi-trace', '--json'])
    assert result.returncode == 0, result.stderr + result.stdout
    original, encoded, restored = out/'rvfi.jsonl', tmp_path/'trace.rvvi', tmp_path/'restored.jsonl'
    export = convert(original, encoded, 'c2', 'rvvi')
    imported = convert(encoded, restored, 'rvvi', 'c2')
    assert not export['independent_check'] and not imported['independent_check']
    before = [json.loads(l) for l in original.read_text().splitlines()]
    after = [json.loads(l) for l in restored.read_text().splitlines()]
    assert before == after
    assert len(before[0]['csr_snapshot']) == (17 if full else 1)
    assert any(r.get('event') == 'trap' for r in before)
    scope = inspect(trace=restored, core='vexriscv', platform=EXAMPLE/'platform.json')
    assert scope['status'] == 'inspected' and scope['trace_complete'] and scope['compared'] is False
    first, second = check(elf, original), check(elf, restored)
    (tmp_path/'original-cosim.json').write_text(json.dumps(first))
    (tmp_path/'restored-cosim.json').write_text(json.dumps(second))
    if full:
        # Preserve the real reference-model differences. Conversion cannot turn them into a match.
        assert first['status'] == second['status'] == 'mismatch'
        assert first['mismatch']['differences'] == second['mismatch']['differences']
    else:
        assert first['status'] == second['status'] == 'match'
        assert first['trace_complete'] and second['trace_complete']
        assert first['instructions'] == second['instructions']
