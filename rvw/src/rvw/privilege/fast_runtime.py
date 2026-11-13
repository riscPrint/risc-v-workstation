"""Pinned v0.20 Smidctrl/Smnip setup for two hart-local edge sources."""
from .controllers import FAST


def validate(config):
    options=config['fast_interrupts']
    if config.get('spec_version')!=FAST:raise ValueError('unsupported fast-interrupt specification')
    if not config['isa'].startswith('rv64'):raise ValueError('this ACLIC profile requires RV64')
    if not {'smaia','smcsrind','smidctrl','smnip'}.issubset(config['isa'].split('_')):
        raise ValueError('declare the v0.20 Smidctrl/Smnip ISA dependencies')
    if options.get('sources',0)<2 or options.get('priority_bits')!=8:
        raise ValueError('this ACLIC profile needs two sources and eight priority bits')
    if options.get('config_csr',0x355)!=0x355:raise ValueError('v0.20 uses mireg4 at CSR 0x355')
    return options


def setup(group_bits,outer=0x48,inner=0x20):
    return f''' li t0, 0x1000
 csrw 0x350, t0
 li t0, {(outer<<8)|(inner<<16)}
 csrw 0x351, t0
 li t0, {(6<<16)|(6<<32)}
 csrw 0x352, t0
 csrw 0x353, zero
 li t0, {(group_bits<<8)|4}
 csrw 0x355, t0
 csrr t1, 0x355
 bne t0, t1, fail
 li t0, 0x80
 csrw 0x350, t0
 csrw 0x351, zero
 li t0, 0xc0
 csrw 0x350, t0
 li t0, 6
 csrw 0x351, t0
 li t0, 256
 csrw 0x347, t0
 li t0, 2048
 csrw mie, t0
'''


def baseline():
    return dict(step=1,kind='aclic-baseline',sources=[1,2],major_causes=[3,7],level=False)
