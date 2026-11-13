#!/usr/bin/env python3
"""Generate trap-free M-mode programs for this project's static CSR banks.

This harness deliberately does not install mtvec or touch mepc for trap setup.
Unexpected traps fail by timeout. Use the general CSR generators for denied
accesses and privilege changes. Their trap-control guard remains unchanged.
"""
import argparse
from pathlib import Path
from rvw.formal import csr_bank


def generate(model, out):
    obj = csr_bank.load(model)
    views = obj['views']
    banks = {b['name']: b for b in obj['banks']}
    if obj['xlen'] != 32 or obj.get('sequences') or obj.get('setup'):
        raise ValueError('require an RV32 static model without setup or sequences')
    if len(views) != len(banks) or len({v['bank'] for v in views}) != len(views):
        raise ValueError('this binding needs one unaliased view per bank')
    if any(b['width'] != 32 for b in banks.values()) or any(
        v['privilege'] != 'M' or v.get('shift', 0) or not v.get('present', True)
        for v in views
    ):
        raise ValueError('require present unshifted M-mode views of RV32 banks')
    # Reuse the existing model, monitor and coverage generator.
    csr_bank.generate(model, out)
    out = Path(out)
    for view in views:
        accesses = []
        if view.get('read_only', False):
            accesses.append(dict(view=view['name'], op='read'))
        else:
            for pattern in (0, 0x100, 0x55aa5500):
                data = pattern & view['write_mask']
                for op in ('write', 'read', 'set', 'read', 'clear', 'read'):
                    accesses.append(dict(view=view['name'], op=op,
                                         **({'data': data} if op != 'read' else {})))
        state = {b['name']: b['reset'] for b in obj['banks']}
        lines = ['.option norvc', '.section .text.init', '.globl _start', '_start:']
        address = hex(view['address'])
        for access in accesses:
            expected = csr_bank.step(obj, state, access)
            if expected['trap']:
                raise ValueError('trap-free harness cannot test a denied access')
            op = access['op']
            lines.append(f"li t0, {access.get('data', 0)}")
            lines.append({'read': f'csrr s2, {address}', 'write': f'csrw {address}, t0',
                          'set': f'csrrs s2, {address}, t0',
                          'clear': f'csrrc s2, {address}, t0'}[op])
            if op != 'write':
                lines += [f"li t0, {expected['rdata']}", 'bne s2, t0, fail']
            state = expected['state']
        lines += ['li t0, 1', 'j finish', 'fail:', 'li t0, 3', 'finish:',
                  'la t1, tohost', 'sw t0, 0(t1)', '1: j 1b',
                  '.section .tohost,"aw",@progbits', '.balign 8',
                  '.globl tohost', 'tohost: .dword 0', '.globl fromhost',
                  'fromhost: .dword 0', '']
        (out / (view['name'] + '.S')).write_text('\n'.join(lines))
    return obj


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('model', type=Path)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    generate(args.model, args.out)
