"""Guard the MMU defaults used by the qualified Spike reference."""
import copy
from pathlib import Path

import pytest
from cosim_build import _build
from model_fixtures import Spike


def execute(tmp_path_factory, platform, body, data=''):
    source = tmp_path_factory.mktemp('reference-mmu') / 'mmu.S'
    source.write_text('''.option norvc
.section .text
.globl _start
_start:
 la t0, handler
 csrw mtvec,t0
''' + body + '''
1: j 1b
.balign 4
handler: j handler
.section .data
''' + data)
    elf = _build(tmp_path_factory, source)
    p = copy.deepcopy(platform)
    p.pmp_regions = 0
    model = Spike(p, elf)
    try:
        effects = []
        for _ in range(100):
            e = model.step()
            effects.append(e)
            if e['trap'] or e['rd'] == 10:
                return effects
        pytest.fail('reference did not reach the observed instruction')
    finally:
        model.close()


def test_mstatus_sum_mxr_are_writable(tmp_path_factory, platform):
    effects = execute(tmp_path_factory, platform,
                      'li t0,0xc0000\ncsrs mstatus,t0\ncsrr a0,mstatus')
    assert not effects[-1]['trap']
    assert effects[-1]['rd_wdata'] & 0xc0000 == 0xc0000


SET_SATP = '''la t0,root
 srli t0,t0,12
 li t1,0x8000000000000000
 or t0,t0,t1
 csrw satp,t0
 sfence.vma
'''


def test_sv39_dirty_page_fault(tmp_path_factory, platform):
    # A valid RWX superpage with A=D=0 must fault under the reference's Svade policy.
    effects = execute(tmp_path_factory, platform, SET_SATP + '''
 li t0,0x1800
 csrc mstatus,t0
 li t0,0x20800
 csrs mstatus,t0
 li t0,0x2010
 lw a0,0(t0)
''', '.balign 4096\nroot: .dword 0x2000000f\n.zero 4088\n')
    assert effects[-1]['trap'] == 1
    assert effects[-1]['cause'] == 13
    assert effects[-1]['tval'] == 0x2010


def test_sv39_instruction_alias(tmp_path_factory, platform):
    # VA 0..1 GiB maps to PA 0x80000000..0xbfffffff, including this code.
    effects = execute(tmp_path_factory, platform, SET_SATP + '''
 la t0,alias
 li t1,0x80000000
 sub t0,t0,t1
 csrw mepc,t0
 li t0,0x1800
 csrc mstatus,t0
 li t0,0x800
 csrs mstatus,t0
 mret
alias:
 li a0,42
''', '.balign 4096\nroot: .dword 0x200000cf\n.zero 4088\n')
    assert not any(e['trap'] for e in effects)
    assert effects[-1]['pc'] < 0x40000000
    assert effects[-1]['rd_wdata'] == 42
