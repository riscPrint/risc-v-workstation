"""RV64 secret operands must retain all bits with a fixed public setup length."""
from pathlib import Path
import pytest
from rvw.sec.core_adapter import render, compile_elf
from rvw.sec.c1_adapter import timing

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('value', [0, 1, -1, 0x80000000, 0x8000000000000000, 0x123456789abcdef0])
def test_full_width_secret_setup(tmp_path, value):
    template = tmp_path/'case.S'
    template.write_text('# RVW_SETUP\n# RVW_PROGRAM\n# RVW_DATA\n')
    text = render(template, dict(secret={'x6': value}, program=[]), 64)
    instructions = [line.strip().split() for line in text.splitlines() if line.strip()]
    assert len(instructions) == 15
    result = 0
    for tokens in instructions:
        imm = int(tokens[-1])
        if tokens[0] == 'slli': result <<= imm
        elif tokens[0] == 'addi': result += imm
        else: pytest.fail('unexpected setup instruction')
        result &= (1 << 64)-1
    assert result == value & ((1 << 64)-1)


@pytest.mark.parametrize('march,abi', [('rv64ima_zicsr', 'lp64'), ('rv32im_zicsr', 'ilp32')])
def test_compiler_abi_follows_target(tmp_path, monkeypatch, march, abi):
    from rvw.sec import core_adapter
    commands = []
    monkeypatch.setattr(core_adapter.shutil, 'which', lambda *a, **k: '/tool/gcc')
    monkeypatch.setattr(core_adapter, 'native', lambda argv, out: commands.append(argv))
    compile_elf(tmp_path/'case.S', tmp_path, dict(_dir=tmp_path, march=march))
    assert f'-mabi={abi}' in commands[0]


def test_timing_uses_observed_retirement_window():
    rows = [dict(order=n, cycle=c, pc=hex(0x80000000+4*n)) for n,c in enumerate([5,7,40,44])]
    assert timing(rows, 0x80000004, 0x8000000c) == {'cycles':37, 'retire_cycles':[33,4]}
    with pytest.raises(ValueError, match='fewer than two'):
        timing(rows, 0x8000000c, 0x80000010)


def test_completion_scope_keeps_actual_store_and_omits_drain():
    from rvw.sec.c1_adapter import completion_trace
    header = dict(schema='rvw.rvfi/1', xlen=64)
    store = dict(order=1, cycle=20, mem_addr='0x80001000', mem_wmask=15, mem_wdata='0x1')
    drain = dict(order=2, cycle=24, pc='0x80000098')
    rows = [header, store, drain, dict(event='end', status='pass', cycle=24)]
    result = completion_trace(rows, 0x80001000)
    assert result[:-1] == [header, store]
    assert result[-1] == dict(event='end', status='pass', cycle=20)
    with pytest.raises(ValueError, match='not observed'):
        completion_trace(rows, 0x80002000)
    with pytest.raises(ValueError, match='did not report pass'):
        completion_trace([dict(store, mem_wdata='0x3')], 0x80001000)


def test_capture_requires_complete_strict_unmasked_match():
    from types import SimpleNamespace
    from rvw.sec.c1_adapter import qualified
    run = SimpleNamespace(status='pass', why_inconclusive=None, instret=39)
    comparison = dict(status='match', trace_complete=True, end_status='pass', instructions=39,
                      synchronized=0, applied_masks=[])
    assert qualified(run, comparison)
    for patch in [dict(trace_complete=False), dict(instructions=38), dict(synchronized=1),
                  dict(applied_masks=[{'reason':'anything'}]), dict(status='mismatch')]:
        assert not qualified(run, dict(comparison, **patch))
