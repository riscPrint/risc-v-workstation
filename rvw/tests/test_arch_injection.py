import copy

import pytest

from rvw.sim.injection import bootstrap_rv32, inject, plan


def documents(flen=0):
    state = dict(schema='rvw.arch-injection/1', profile='test/1', pc=0x80000100,
        gpr=[0] + list(range(1, 32)), fpr=[0xffffffff7fc00000] * 32 if flen else [],
        csr={'0x300': 0}, privilege='M', translation='bare', devices=[], pending_interrupts=[],
        execution=dict(harts=1, pending_trap=False, reservation=False, debug=False,
                       wfi=False, external_effects=[]), memory=[dict(address=0x80000000, hex='aabbccdd')])
    mapping = dict(schema='rvw.arch-map/1', profile='test/1', xlen=32, flen=flen,
        pc='pc', gpr=[f'x{i}' for i in range(32)], fpr=[f'f{i}' for i in range(32)] if flen else [],
        csr={'0x300': 'mstatus'})
    return state, mapping


class Port:
    def __init__(self, corrupt=False): self.signals = {}; self.memory = {}; self.released = False; self.corrupt = corrupt
    def hold_fetch(self): pass
    def clear_microarchitecture(self): pass
    def write_signal(self, name, value): self.signals[name] = value
    def read_signal(self, name): return self.signals[name] ^ int(self.corrupt)
    def write_memory(self, address, data): self.memory[address] = data
    def read_memory(self, address, size): return self.memory[address]
    def release_fetch(self): self.released = True


def test_inject_raw_fp_and_memory_before_release():
    state, mapping = documents(64)
    port = Port()
    assert inject(port, state, mapping)['registers'] == 65
    assert port.signals['f0'] == 0xffffffff7fc00000
    assert port.signals['pc'] == 0x80000100 and port.released
    bad = Port(True)
    with pytest.raises(ValueError, match='readback'): inject(bad, state, mapping)
    assert not bad.released


@pytest.mark.parametrize('field,value', [('translation', 'sv39'), ('devices', ['uart']),
    ('pending_interrupts', [7]), ('gpr', [0]), ('csr', {})])
def test_incomplete_or_unsupported_state(field, value):
    state, mapping = documents()
    state[field] = value
    with pytest.raises(ValueError): plan(state, mapping)


def test_bootstrap_preserves_gprs_and_uses_direct_jump():
    state, mapping = documents()
    asm = bootstrap_rv32(state, mapping)
    assert 'csrw 0x300, x5' in asm and 'li x31, 0x1f' in asm
    assert asm.index('csrw') < asm.index('li x1,')
    assert 'jal x0, __rvw_resume_pc' in asm and '.set __rvw_resume_pc, 0x80000100' in asm
    state['csr']['0x300'] = 8
    with pytest.raises(ValueError, match='MIE'): bootstrap_rv32(state, mapping)


def test_bootstrap_links_to_saved_nonreset_pc(tmp_path):
    import shutil
    from rvw.common.proc import run_group
    gcc = shutil.which('riscv64-unknown-elf-gcc') or '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
    from pathlib import Path
    if not Path(gcc).exists(): pytest.skip('RISC-V GCC not installed')
    state, mapping = documents()
    source = tmp_path / 'restore.S'
    source.write_text(bootstrap_rv32(state, mapping))
    elf = tmp_path / 'restore.elf'
    result = run_group(['nice', '-n', '10', gcc, '-march=rv32im_zicsr', '-mabi=ilp32',
        '-nostdlib', '-Wl,-Ttext=0x80001000', '-Wl,-e,_rvw_restore', str(source), '-o', str(elf)],
        timeout=10, capture=True, text=True)
    assert result.returncode == 0, result.stderr
    objdump = str(Path(gcc).with_name('riscv64-unknown-elf-objdump'))
    dump = run_group([objdump, '-d', str(elf)], timeout=10, capture=True, text=True)
    assert dump.returncode == 0 and '80000100' in dump.stdout
