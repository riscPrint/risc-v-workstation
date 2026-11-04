"""Independent scalar fault-attempt evidence, separate from completed effects."""
from rvw.common.riscv import decode
from .sail import memory_operand


def reference_fault(effect, xlen):
    insn = effect['insn']
    instruction = decode(insn, xlen)
    if (not effect['trap'] or effect['intr'] or effect['cause'] not in (4, 5, 6, 7, 13, 15)
            or instruction.cls not in ('load', 'store', 'atomic')):
        raise ValueError('reference cannot check this fault-access encoding or cause')
    # A decoded attempt does not establish that no byte completed. Refuse
    # reference effects which the zero-completion interface cannot represent.
    if effect['mem_rmask'] or effect['mem_wmask']:
        raise ValueError('reference reports partial fault effects')
    name = instruction.mnemonic.removeprefix('c.')
    atomic = instruction.cls == 'atomic'
    read = instruction.cls == 'load' or atomic and not name.startswith('sc.')
    write = instruction.cls == 'store' or atomic and not name.startswith('lr.')
    # AMOs take store/AMO faults even though they also attempt a read.
    if (write != (effect['cause'] in (6, 7, 15))):
        raise ValueError('reference fault cause and access disagree')
    if atomic:
        width = 4 if name.endswith('.w') else 8
    else:
        width = {'lb': 1, 'lbu': 1, 'lh': 2, 'lhu': 2, 'lw': 4, 'lwu': 4,
                 'ld': 8, 'sb': 1, 'sh': 2, 'sw': 4, 'sd': 8,
                 'flw': 4, 'fld': 8, 'fsw': 4, 'fsd': 8}.get(name.removesuffix('sp'))
        if width is None:
            raise ValueError('reference cannot check this fault-access width')
    operand = memory_operand(insn, xlen)
    if operand is None:
        raise ValueError('reference cannot locate fault-access operand')
    rs1, offset = operand
    addr = (effect['before'][rs1] + offset) % (1 << xlen)
    mask = (1 << width) - 1
    return dict(addr=addr, rmask=mask if read else 0, wmask=mask if write else 0,
                completed_rmask=0, completed_wmask=0, rdata=None, wdata=None)
