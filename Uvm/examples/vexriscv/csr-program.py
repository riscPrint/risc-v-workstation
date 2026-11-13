#!/usr/bin/env python3
"""Emit the project-safe catalog CSR sequence for the native collector."""
import argparse
import asyncio
import json
from pathlib import Path
from rvw.uvm.csr_sequence import CsrQualification
from rvw.formal.csr import step


def generate(selection, out, *, seed=1):
    qualification=CsrQualification(selection,seed=seed)
    models={r['address']:r for r in qualification.model['csrs']}
    if any(not r.get('present',True) for r in models.values()):
        raise ValueError('native collector requires present CSRs; trap-only accesses need a trap collector')
    states={a:r['reset'] for a,r in models.items()}
    lines=['.section .text','.globl _start','_start:']
    async def plan(address, transaction):
        state=states[address]
        trap,next_state=step(models[address],state,transaction,32)
        if trap: raise ValueError('native collector does not plan denied accesses')
        if transaction['write']:
            lines.extend([f"li t0, {transaction['data']}",f'csrrw zero, {address}, t0'])
        else:
            lines.append(f'csrrs t1, {address}, zero')
        states[address]=next_state
        return dict(trap=False,read_data=state)
    asyncio.run(qualification.run(plan))
    lines.extend(['li t0, 1','la t1, tohost','sw t0, 0(t1)','j .',
                  '.section .tohost,"aw",@progbits','.balign 64','.globl tohost','tohost: .dword 0'])
    Path(out).write_text('\n'.join(lines)+'\n')
    return qualification.checks

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('selection',type=Path);p.add_argument('out',type=Path)
    p.add_argument('--seed',type=int,default=1);a=p.parse_args()
    print(json.dumps(dict(planned=generate(a.selection,a.out,seed=a.seed))))
