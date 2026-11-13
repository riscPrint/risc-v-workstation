"""Version-selected ACLINT rc4 and fast-interrupt v0.20 programs."""
from .controllers import FAST, ACLINT, Aclint, NestedPriority
from .programs import HEAD, TAIL


def programs(config):
    kind=config['kind'];rows=[]
    version=ACLINT if kind=='aclint' else FAST
    if config.get('spec_version') != version:
        raise ValueError('unsupported controller specification version')
    if kind=='smnip':
        csr=config.get('fast_interrupts',{}).get('config_csr',0x355)
        for threshold in (0,16,255,256):
            code=HEAD+f''' li t0, 0x1000
 csrw 0x350, t0
 li t0, 0x804
 csrw {csr}, t0
 li t0, {threshold}
 csrw 0x347, t0
 csrr t1, 0x347
 bne t0, t1, fail
 la t0, handler
 csrw mtvec, t0
ecall_site:
 ecall
 csrr t0, 0x347
 li t1, {threshold}
 bne t0, t1, fail
 j pass
handler:
 csrr t0, mcause
 li t1, 11
 bne t0, t1, fail
 csrr t0, 0x346
 srli t0, t0, 8
 andi t0, t0, 511
 li t1, {threshold}
 bne t0, t1, fail
 csrw 0x347, zero
 csrr t0, mepc
 la t1, ecall_site
 bne t0, t1, fail
 addi t0, t0, 4
 csrw mepc, t0
 mret
''' + TAIL
            rows.append(dict(id=f'smnip-threshold-{threshold}',assembly=code,family='smnip',
                bins=[f'smnip.threshold.{threshold}'],reference_model=dict(kind='smnip',threshold=threshold)))
    else:
        layout=config['aclint']
        for source, key, bit in [('mswi','mswi',3),('sswi','sswi',1)]:
            if key not in layout:continue
            address=layout[key]
            if type(address) is not int or address < 0 or address % 4:raise ValueError('invalid ACLINT map')
            code=HEAD+f''' li a0, {address}
 li t0, 1
 sw t0, 0(a0)
 li s0, 10000
1: csrr t0, mip
 andi t0, t0, {1<<bit}
 bnez t0, 2f
 addi s0, s0, -1
 bnez s0, 1b
 j fail
2: sw zero, 0(a0)
'''
            if source=='sswi':
                code+=f''' csrr t0, mip
 andi t0, t0, {1<<bit}
 beqz t0, fail
 li t0, {1<<bit}
 csrc mip, t0
'''
            code+=f''' li s0, 10000
3: csrr t0, mip
 andi t0, t0, {1<<bit}
 beqz t0, pass
 addi s0, s0, -1
 bnez s0, 3b
 j fail
''' + TAIL
            rows.append(dict(id='aclint-'+source,assembly=code,family='aclint',bins=['aclint.'+source],
                reference_model=dict(kind='aclint',source=source)))
    for row in rows:row['spec_version']=version
    if not rows:raise ValueError('no implemented controller sources')
    return rows


def reference(scenario):
    p=scenario['reference_model']
    if p['kind']=='smnip':
        m=NestedPriority();m.threshold=p['threshold'];m.trap();saved=m.previous
        m.threshold=0;m.ret();actual=[saved,m.threshold];expected=[p['threshold']]*2
    else:
        m=Aclint()
        if p['source']=='sswi':
            m.set_ssip(0,1);a=m.ssip[0];m.set_ssip(0,0);b=m.ssip[0]
            m.clear_ssip_csr(0);actual=[a,b,m.ssip[0]];expected=[True,True,False]
        else:
            m.write_msip(0,1);a=m.msip[0];m.write_msip(0,0);actual=[a,m.msip[0]];expected=[True,False]
    return dict(id=scenario['id'],status='pass' if actual==expected else 'fail',
                evidence='model-based',actual=actual,expected=expected)
