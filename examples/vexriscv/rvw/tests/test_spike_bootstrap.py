"""Native Spike -> RV32IM bootstrap -> VexRiscv continuation."""
import json
import os
from pathlib import Path

from rvw.common.proc import run_group
from rvw.cosim.elf import Elf
from rvw.cosim.platform import Platform
from rvw.cosim.spike import Spike, capture_shim
from rvw.common.capture import Capture
from rvw.sim.injection import bootstrap_rv32
from rvw.sim.spike_bootstrap import capture

EXAMPLE = Path(__file__).resolve().parents[1]
HOME = Path(os.environ.get('RVW_HOME', Path(__file__).resolve().parents[4]))
GCC = os.environ.get('RISCV_PREFIX', 'riscv64-unknown-elf-') + 'gcc'


def run(command, timeout=30):
    result = run_group(list(map(str, command)), timeout=timeout, capture=True, text=True)
    assert not result.timed_out and result.returncode == 0, result.stdout + result.stderr
    return result


def test_native_spike_bootstrap_suffix(tmp_path):
    source = tmp_path / 'source.S'
    source.write_text((EXAMPLE / 'programs/smoke.S').read_text().replace(
        '_start:\n', '_start:\n  li t0, 0x1357\n  csrw mscratch, t0\n').replace(
        '  la t0, scratch', '  csrr t4, mscratch\n  li t5, 0x1357\n  bne t4, t5, fail\n  la t0, scratch'))
    elf = tmp_path / 'smoke'
    run([GCC, '-march=rv32im_zicsr_zifencei', '-mabi=ilp32', '-nostdlib',
         '-nostartfiles', '-T', EXAMPLE / 'programs/link.ld', source, '-o', elf])
    platform = Platform.load('vexriscv', EXAMPLE / 'platform.json')
    platform.ram = [(0x80000000, 0x10000)]
    mapping = json.loads((EXAMPLE / 'bootstrap-profile.json').read_text())
    shim = capture_shim(Capture(tmp_path / 'capture'), HOME / 'Cosim/build/librvw_spike.so')
    model = Spike(platform, elf, shim=shim)
    expected = []
    try:
        state = capture(model, mapping, instructions=10)
        assert state['pc'] != platform.reset_pc
        assert state['csr']['0x340'] == 0x1357
        for _ in range(100):
            effect = model.step()
            expected.append(platform.normalize_effect(effect))
            if effect['mem_wmask'] and effect['mem_addr'] == Elf(elf).symbols['tohost']:
                break
        else:
            raise AssertionError('Spike did not reach tohost')
    finally:
        model.close()
    asm = tmp_path / 'bootstrap.S'
    asm.write_text('.section .reset,"ax"\n.globl _start\n_start:\n  jal x0, _rvw_restore\n' + bootstrap_rv32(state, mapping))
    linker = tmp_path / 'boot.ld'
    linker.write_text('ENTRY(_start)\nSECTIONS { . = 0x80000000; .reset : { *(.reset) } '
                      '. = 0x80008000; .restore : { *(.text.rvw_restore) } }')
    boot = tmp_path / 'bootstrap'
    run([GCC, '-march=rv32im_zicsr', '-mabi=ilp32', '-nostdlib', '-nostartfiles',
         '-T', linker, asm, '-o', boot])
    image = dict(schema='rvw.vex-bootstrap-image/1', pc=str(state['pc']), memory=list(state['memory']))
    image['memory'] += [dict(address=a, hex=data.hex()) for a, data, _ in Elf(boot).segments if data]
    image_path = tmp_path / 'image.json'
    image_path.write_text(json.dumps(image))
    out = tmp_path / 'rtl'
    run([EXAMPLE / 'checkpoint-probe.sh', elf, out, tmp_path / 'unused',
         'bootstrap', '10', image_path], timeout=600)
    rows = [json.loads(line) for line in (out / 'rvfi.jsonl').read_text().splitlines()]
    assert rows[-1]['event'] == 'end' and rows[-1]['status'] == 'pass'
    actual = [r for r in rows if 'order' in r]
    assert len(actual) == len(expected) > 5
    for rtl, ref in zip(actual, expected):
        for field in ('pc', 'pc_next', 'insn', 'mode', 'rd', 'mem_rmask', 'mem_wmask'):
            value = int(rtl[field], 0) if isinstance(rtl[field], str) else rtl[field]
            assert value == ref[field], (field, rtl, ref)
        for field, enabled in [('mem_addr', rtl['mem_rmask'] or rtl['mem_wmask']),
                               ('rd_wdata', rtl['rd']), ('mem_rdata', rtl['mem_rmask']),
                               ('mem_wdata', rtl['mem_wmask'])]:
            if enabled:
                assert int(rtl[field], 0) == ref[field], (field, rtl, ref)
