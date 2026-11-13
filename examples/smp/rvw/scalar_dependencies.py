#!/usr/bin/env python3
"""Bind RVWMO dependencies from a complete, cacheless M-mode scalar capture.

Source: RISC-V RVWMO v2.0, syntactic dependencies and source/destination tables.
https://docs.riscv.org/reference/isa/v20260120/unpriv/rvwmo.html
Unknown instructions, traps, resets and devices refuse a complete binding.
"""
import argparse
import hashlib
import json
from pathlib import Path
from rvw.cosim.trace import Trace


class Dependencies:
    def __init__(self):
        self.regs = [set() for _ in range(32)]
        self.control = set()
        self.lr = None

    def observe(self, r):
        if r['trap'] or r['mem_fault'] or r['mode'] != 3:
            raise ValueError('only nonfaulting M-mode scalar execution is supported')
        insn = r['insn']
        op, f3, f7 = insn & 127, (insn >> 12) & 7, insn >> 25
        rd, a, b = (insn >> 7) & 31, (insn >> 15) & 31, (insn >> 20) & 31
        identifier = f'h{r["hart"]}e{r["epoch"]}o{r["order"]}'
        reg = self.regs
        result = None
        if op in (0x03, 0x23, 0x2f):
            kind = {0x03: 'R', 0x23: 'W'}.get(op)
            atomic_op = insn >> 27
            if op == 0x2f:
                if f3 not in (2, 3) or atomic_op not in (0,1,2,3,4,8,12,16,20,24,28) or atomic_op == 2 and b != 0:
                    raise ValueError('unsupported atomic encoding')
                kind = {2: 'LR', 3: 'SC'}.get(atomic_op, 'AMO')
            if op == 0x03 and f3 > 6 or op == 0x23 and f3 > 3:
                raise ValueError('unsupported load/store encoding')
            size = 1 << (f3 & 3)
            address = r['mem_addr']
            # Failed SC generates no memory operation and consumes the pairing.
            if kind == 'SC' and not r['mem_wmask']:
                self.lr = None
                # RVWMO's source/destination table gives failed SC no
                # destination register. It does not kill earlier provenance.
                return None
            if address % size or not 0x80000000 <= address < 0x82000000 or address+size > 0x82000000:
                raise ValueError('aligned main RAM access required')
            result = dict(id=identifier, hart=r['hart'], order=str(r['order']), kind=kind,
                          size=size, address=str(address), addr=sorted(reg[a]),
                          data=sorted(reg[b]) if kind in ('W', 'SC', 'AMO') else [],
                          ctrl=sorted(self.control))
            if r['mem_rmask']:
                result['read'] = str(r['mem_rdata'] & ((1 << (8*size))-1))
            if r['mem_wmask']:
                result['write'] = str(r['mem_wdata'] & ((1 << (8*size))-1))
            if kind == 'LR':
                self.lr = identifier, address, size
            if kind == 'SC':
                if self.lr is None or self.lr[1:] != (address,size):
                    raise ValueError('successful SC has no observed matching LR')
                result['rmw'] = self.lr[0]
                self.lr = None
            if op != 0x23 and rd:
                # Loads and atomics do not carry source dependencies to rd.
                reg[rd] = {identifier}
        elif op == 0x0f and f3 == 0:
            result = dict(id=identifier, hart=r['hart'], order=str(r['order']), kind='FENCE',
                          addr=[], data=[], ctrl=[])
        elif op == 0x63 and f3 in (0,1,4,5,6,7):
            self.control |= reg[a] | reg[b]
        elif op in (0x37,0x17,0x6f):
            if rd:
                reg[rd] = set()
        elif op == 0x67 and f3 == 0:
            self.control |= reg[a]
            if rd:
                reg[rd] = set()
        elif (op == 0x13 and (f3 not in (1,5) or f3 == 1 and insn >> 26 == 0 or
                               f3 == 5 and insn >> 26 in (0,0x10))) or (
              op == 0x1b and (f3 == 0 or f3 == 1 and f7 == 0 or f3 == 5 and f7 in (0,0x20))):
            if rd:
                reg[rd] = set(reg[a])
        elif (op == 0x33 and (f7 in (0,1) or f7 == 0x20 and f3 in (0,5))) or (
              op == 0x3b and (f7 == 0 and f3 in (0,1,5) or f7 == 1 and f3 in (0,4,5,6,7) or
                              f7 == 0x20 and f3 in (0,5))):
            if rd:
                reg[rd] = reg[a] | reg[b]
        elif op == 0x73 and f3 == 2 and a == 0 and insn >> 20 == 0xf14:
            if rd:
                reg[rd] = set()  # read-only mhartid
        else:
            raise ValueError(f'unsupported dependency instruction 0x{insn:08x}')
        return result


def bind(source, output):
    source, output = Path(source), Path(output)
    data = source.read_bytes()
    raw = [json.loads(line) for line in data.splitlines()]
    reader = Trace(source)
    try:
        if not reader.multihart or reader.header.get('memory_addresses') != 'physical':
            raise ValueError('physical multi-hart capture required')
        decoded = list(reader)
    finally:
        reader.close()
    states = {h: Dependencies() for h in raw[0]['harts']}
    done = {}
    for original, record in zip(raw[1:], decoded, strict=True):
        event = record.get('event')
        if event == 'reset' and record['epoch'] == 0:
            continue
        if event == 'hart_end':
            done[record['hart']] = record['status']
            continue
        if event:
            raise ValueError('trap, IRQ, external or later-reset capture is unsupported')
        annotation = states[record['hart']].observe(record)
        if annotation is not None:
            original['memory_model'] = annotation
    if set(done) != set(states) or any(s != 'pass' for s in done.values()):
        raise ValueError('all harts must complete with pass')
    raw[0]['memory_dependencies'] = 'complete'
    raw[0]['dependency_binding'] = dict(profile='smp-scalar/1',
        source_sha256=hashlib.sha256(data).hexdigest(),
        binding_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with output.open('x') as stream:
        stream.write(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in raw))
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--trace', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    print(bind(a.trace,a.out))
