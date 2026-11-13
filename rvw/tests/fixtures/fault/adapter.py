"""Fake C1 core adapter for fault-campaign tests. It runs a raw program image on the rvw
debug model hart, applies one `--fault` (sites core.xN), and writes C1 result.json and C2.
A parity checker guards x9 and reports detection `parity_x9`. The program checks its sum.
"""
import argparse
import json
from pathlib import Path

from rvw.debug.hart import Hart, Memory

BASE = 0x80000000

parser = argparse.ArgumentParser()
parser.add_argument('command')
parser.add_argument('--elf', required=True)
parser.add_argument('--out', required=True)
parser.add_argument('--rvfi-trace', action='store_true')
parser.add_argument('--fault')
parser.add_argument('--max-cycles', type=int, default=500)
args = parser.parse_args()
out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
image = Path(args.elf).read_bytes()
memory = Memory([{'base': BASE, 'size': 0x2000}])
memory.load(BASE, image)
writes = []
original_write = memory.write
memory.write = lambda address, size, value, source='hart': (writes.append((address, size, value)),
                                                            original_write(address, size, value, source))[1]
hart = Hart(memory, reset_pc=BASE, modes='M')
hart.dcsr |= 1 << 15     # ebreak ends the program (Debug Mode entry)
fault = json.loads(Path(args.fault).read_text())['faults'][0] if args.fault else None
applied = {'applied': False, 'reason': 'cycle not reached'} if fault else None
if fault and not (fault['site'].startswith('core.x') and 0 < int(fault['site'][6:]) < 32):
    applied = {'applied': False, 'reason': 'unknown site'}
    fault = None
records = [dict(schema='rvw.rvfi/1', xlen=64, isa='rv64i', core='fake', config='fake', elf=args.elf)]
detections = []
status = 'timeout'
for cycle in range(args.max_cycles):
    if fault:
        reg, bit = int(fault['site'][6:]), fault['bit']
        start, duration = fault['cycle'], fault.get('duration')
        if fault['kind'] == 'flip':
            active = cycle == start          # a transient upset toggles the bit once
        else:
            active = cycle >= start and (duration is None or cycle < start + duration)
        if active:
            if fault['kind'] == 'flip':
                hart.x[reg] ^= 1 << bit
            elif fault['kind'] == 'stuck1':
                hart.x[reg] |= 1 << bit
            else:
                hart.x[reg] &= ~(1 << bit)
            applied = {'applied': True, 'site': fault['site'], 'bit': bit, 'cycle': start}
            if reg == 9 and 'parity_x9' not in detections:
                detections.append('parity_x9')
    pc = hart.pc
    insn = int.from_bytes(image[pc - BASE:pc - BASE + 4], 'little')
    writes.clear()
    entry = hart.step()
    rd = (insn >> 7) & 31 if insn & 0x7f in (0x13, 0x33, 0x37, 0x17, 0x03, 0x6f, 0x67) else 0
    record = {k: '0x0' for k in 'rs1_rdata rs2_rdata mem_rdata'.split()}
    mem = writes[-1] if writes else (0, 0, 0)
    record.update(order=cycle, cycle=cycle, pc=hex(pc), pc_next=hex(hart.pc if not hart.debug_mode else pc + 4),
                  insn=hex(insn), mode=3, trap=False, intr=False, halt=False, rs1=0, rs2=0, rd=rd,
                  rd_wdata=hex(hart.x[rd]), mem_addr=hex(mem[0]), mem_wmask=(1 << mem[1]) - 1 if writes else 0,
                  mem_wdata=hex(mem[2]), mem_rmask=0, mem_fault=False)
    if entry is not None:
        status = 'pass' if hart.x[5] == 15 else 'fail'
        break
    records.append(record)
records.append(dict(event='end', cycle=len(records), status=status))
(out / 'rvfi.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
details = {}
if applied is not None:
    details['fault'] = applied
if detections and applied and applied['applied']:
    details['detections'] = detections
result = {'schema': 'rvw.run/1', 'status': status, 'core': 'fake', 'config': 'fake', 'elf': args.elf,
          'cycles': len(records), 'artifacts': {'rvfi_trace': 'rvfi.jsonl'}, 'details': details}
if status == 'fail':
    result['fail_code'] = 1
(out / 'result.json').write_text(json.dumps(result) + '\n')
