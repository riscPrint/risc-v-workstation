"""Zicboz behavior through M/S/U and guest environment-control gates."""
from itertools import product
from .extensions import access, row


def programs(config):
    isa=config['isa']; options=config['envcfg']
    if not isa.startswith('rv64') or 'zicboz' not in isa:
        raise ValueError('CBO.ZERO campaign requires RV64 Zicboz')
    size=options['block_bytes']
    if type(size) is not int or not 16<=size<=4096 or size&(size-1):
        raise ValueError('block_bytes must be a power of two in 16..4096')
    hyper='h' in isa.split('_')[0][4:]
    rows=[]
    for mg,hg,sg in product((0,1),repeat=3):
        if not hyper and hg:continue
        for mode in (('M','S','U','VS','VU') if hyper else ('M','S','U')):
            denied=(mode!='M' and not mg) or (mode in ('VS','VU') and not hg) or (mode in ('U','VU') and not sg)
            cause=22 if mode in ('VS','VU') and mg and (not hg or not sg and mode=='VU') else 2
            setup=f''' la t0, block_start
 li t1, {size//8}
 li t2, -1
fill_block:
 sd t2, 0(t0)
 addi t0, t0, 8
 addi t1, t1, -1
 bnez t1, fill_block
 li t0, {mg<<7}
 csrw 0x30a, t0
 li t0, {sg<<7}
 csrw 0x10a, t0
'''
            if hyper:
                setup+=f' li t0, {hg<<7}\n csrw 0x60a, t0\n li t0, 1\n slli t0, t0, 39\n csrc mstatus, t0\n'
            if mode=='VU':setup+=' li t0, 1\n slli t0, t0, 39\n csrs mstatus, t0\n'
            setup+=' la a0, block_start\n addi a0, a0, 3\n'
            operation=f'''cbo.zero (a0)
 la a0, block_start
 li a1, {size//8}
zero_check:
 ld a2, 0(a0)
 bnez a2, fail
 addi a0, a0, 8
 addi a1, a1, -1
 bnez a1, zero_check
 la a0, block_before
 ld a1, 0(a0)
 li a2, 0x12345678
 bne a1, a2, fail
 la a0, block_after
 ld a1, 0(a0)
 bne a1, a2, fail'''
            actual_mode='VS' if mode=='VS' else 'U' if mode=='VU' else mode
            code=access(actual_mode,setup,operation,denied,cause=cause)
            if denied:
                # Check atomic denial independently after returning to M-mode.
                check=f''' la a0, block_start
 li a1, {size//8}
 li a3, -1
denied_check:
 ld a2, 0(a0)
 bne a2, a3, fail
 addi a0, a0, 8
 addi a1, a1, -1
 bnez a1, denied_check
'''
                code=code.replace(' j pass\nfail:',check+' j pass\nfail:')
            code+=f'''.section .data
.balign {size}
 .space {size-8}
block_before: .dword 0x12345678
block_start: .space {size}
block_after: .dword 0x12345678
'''
            name=f'envcfg-zero-{mode.lower()}-{mg}{hg}{sg}'
            item=row(name,code,'priv/machine.html')
            item['reference_options']=['--blocksz='+str(size)]
            rows.append(item)
    return rows
