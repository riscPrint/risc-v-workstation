"""Reduction behavior with fixture oracles, not RTL evidence."""
import pytest
import subprocess
import shutil

from test_debug_tools import env, fake_run, SYMS_ELF
from rvw.runs.elf import Elf
from rvw.reduce.core import Reducer, Options
from rvw.reduce.streams import minimize, instruction_slots, irq_entries


def test_ddmin_and_budget():
    calls = []
    def probe(xs):
        calls.append(xs)
        return 3 in xs and 7 in xs
    kept, why = minimize(range(10), probe)
    assert kept == [3, 7] and why == 'one_minimal'
    assert all(probe([v for v in kept if v != i]) is False for i in kept)
    assert minimize([1], lambda _: None)[1] == 'inconclusive_or_budget'
    assert minimize([1], lambda _: False)[1] == 'initial_not_reproduced'


def test_instruction_reduce(tmp_path, monkeypatch):
    gcc = shutil.which('riscv64-unknown-elf-gcc') or '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
    asm = tmp_path / 'code.S'
    asm.write_text('.text\n.global stream\n.type stream,@function\nstream:\n'
                   '.option norvc\naddi a0,a0,1\naddi a1,a1,2\n'
                   '.option rvc\nc.nop\nc.nop\n'
                   '.option norvc\naddi a2,a2,3\n.size stream,.-stream\n')
    binary = tmp_path / 'code.elf'
    subprocess.run([gcc, '-nostdlib', '-Wl,-e,stream', str(asm), '-o', str(binary)], check=True)
    e = Elf(str(binary))
    name = 'stream'
    slots = instruction_slots(e, name)
    off = next(o for o, size in slots if size == 4 and e.data[o:o+4] != bytes.fromhex('13000000'))
    monkeypatch.setenv('FAKE_INSN_OFFSET', str(off))
    run = fake_run(tmp_path / 'r', '--seed', '9', '--elf', str(binary))
    rep = Reducer(str(run), Options(out=tmp_path / 'red', modes=['instructions'],
                                   instructions=[name], budget=100)).reduce()
    stream = rep['streams']['instructions:' + name]
    assert rep['reproduced'] and stream['remaining'] == 1 and stream['one_minimal']
    result = Elf(rep['best']['elf'])
    assert len(result.data) == len(e.data)
    for i, (o, size) in enumerate(slots):
        assert result.data[o:o+size] == (e.data[o:o+size] if i in stream['kept'] else
                                        bytes.fromhex('0100' if size == 2 else '13000000'))


@pytest.mark.parametrize('budget,complete', [(100, True), (1, False)])
def test_irq_reduce(tmp_path, monkeypatch, budget, complete):
    monkeypatch.setenv('FAKE_IRQ', '1')
    schedule = '1:0x0,50:0x8,100:0x80,200:0x0,300:0x8'
    run = fake_run(tmp_path / 'r', '--irq-schedule', schedule)
    rep = Reducer(str(run), Options(out=tmp_path / 'red', modes=['irq'], budget=budget)).reduce()
    stream = rep['streams']['irq']
    assert rep['reproduced'] and stream['one_minimal'] is complete
    if complete:
        assert stream['kept'] == [2]
        assert "1:0x0,100:0x80" in rep['best']['replay']
    else:
        assert stream['completion'] == 'budget_exhausted'
    assert not stream['global_minimum']


@pytest.mark.parametrize('cause', ['FAKE_ERROR', 'FAKE_WALL_CLOCK', 'FAKE_SYNTH', 'FAKE_INCONCLUSIVE'])
def test_inconclusive_candidate(tmp_path, monkeypatch, cause):
    monkeypatch.setenv('FAKE_IRQ', '1')
    run = fake_run(tmp_path / 'r', '--irq-schedule', '1:0x0,100:0x80')
    monkeypatch.setenv(cause, '1')
    rep = Reducer(str(run), Options(out=tmp_path / 'red', modes=['irq'])).reduce()
    assert not rep['reproduced']
    assert not rep['streams']['irq']['one_minimal']


@pytest.mark.parametrize('text', ['', '2:0x0', '1:0x0,1:0x8', '1:0x10000000000000000'])
def test_invalid_irq(text):
    with pytest.raises(ValueError):
        irq_entries(text)


def test_data_is_not_instructions():
    with pytest.raises(ValueError):
        instruction_slots(Elf(SYMS_ELF), 'count')
