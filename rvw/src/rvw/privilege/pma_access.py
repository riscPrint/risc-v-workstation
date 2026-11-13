"""Explicit project PMA boundary/atomic probes and transaction expectations.

PMA overlap and misalignment choices belong to project data. This module never
invents a universal priority or conflict policy for an implementation.
"""
import re
from .programs import HEAD,TAIL


def programs(config):
    pma=config['pma'];rows=[]
    for probe in pma['probes']:
        name=probe['name'];operation=probe['operation'];width=probe['width'];address=probe['address']
        if not re.fullmatch(r'[A-Za-z0-9_-]+',name) or width not in (1,2,4,8) or address<0:
            raise ValueError('PMA probe needs a simple name, scalar width and nonnegative address')
        if operation not in ('read','write','amoadd','amoswap','lr','sc'):
            raise ValueError('unsupported PMA probe operation')
        atomic=operation not in ('read','write')
        if atomic and width not in (4,8):raise ValueError('atomic PMA probes need width 4 or 8')
        cause=probe['cause']
        if cause not in (0,4,5,6,7):raise ValueError('PMA cause must be success, misalignment or access fault')
        writes=operation in ('write','amoadd','amoswap','sc')
        if writes and probe.get('test_writes') is not True:
            raise ValueError('PMA write probes require test_writes')
        if atomic and 'a' not in config['isa'].split('_')[0][4:]:
            raise ValueError('atomic PMA probes require A')
        value=probe.get('value',0)
        suffix={1:'b',2:'h',4:'w',8:'d'}[width]
        instruction=(f'l{suffix}{"u" if width<8 else ""} a2, 0(a0)' if operation=='read' else
                     f's{suffix} a1, 0(a0)' if operation=='write' else
                     f'lr.{suffix} a2, (a0)' if operation=='lr' else
                     f'sc.{suffix} a2, a1, (a0)' if operation=='sc' else
                     f'{operation}.{suffix} a2, a1, (a0)')
        code=HEAD+f''' la t0, handler
 csrw mtvec, t0
 li a0, {address}
 li a1, {value}
.globl pma_probe_start, pma_probe_end
pma_probe_start:
access_site:
 {instruction}
pma_probe_end:
'''
        if not cause:
            if operation!='write':
                expected=probe['result']
                if atomic and width==4:expected=(expected&0x7fffffff)-(expected&0x80000000)
                code+=f' li t0, {expected}\n bne a2, t0, fail\n'
            if 'readback_value' in probe:
                if not writes:raise ValueError('readback_value requires a write operation')
                load=f'l{suffix}{"u" if width<8 else ""}'
                code+=f' {load} a3, 0(a0)\n li t0, {probe["readback_value"]}\n bne a3, t0, fail\n'
            code+=' j pass\n'
        else:code+=' j fail\n'
        code+=f'''handler:
 csrr t0, mcause
 li t1, {cause}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, access_site
 bne t0, t1, fail
 csrr t0, mtval
 li t1, {address}
 bne t0, t1, fail
 {'j pass' if cause else 'j fail'}
'''+TAIL
        item=dict(id='pma-access-'+name,assembly=code,family='pma',bins=['pma.access.'+name],
                  pma_expectation=dict(address=address,width=width,write=writes,
                      transfers=probe.get('transfers'),state=probe.get('device_state')))
        if item['pma_expectation']['transfers'] is None:
            item['pma_expectation'].pop('transfers')
        if pma.get('spike_compatible') is not True:
            item['reference_unavailable']='Spike CLI does not implement this project PMA map'
        rows.append(item)
    if not rows:raise ValueError('PMA campaign has no probes')
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('PMA probe names must be distinct')
    return rows
