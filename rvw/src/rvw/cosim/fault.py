"""Independent scalar fault-attempt evidence, separate from completed effects."""
def reference_fault(effect, xlen):
    insn = effect['insn']
    op, width_code = insn & 127, insn >> 12 & 7
    if (not effect['trap'] or effect['intr'] or effect['cause'] not in (4, 5, 6, 7, 13, 15)
            or op not in (3, 7, 0x23, 0x27) or width_code > 3):
        raise ValueError('reference cannot check this fault-access encoding or cause')
    store = op in (0x23, 0x27)
    if store != (effect['cause'] in (6, 7, 15)):
        raise ValueError('reference fault cause and access disagree')
    immediate = ((insn >> 25) << 5 | (insn >> 7 & 31)) if store else insn >> 20
    if immediate & 0x800:
        immediate -= 0x1000
    addr = (effect['before'][insn >> 15 & 31] + immediate) % (1 << xlen)
    mask = (1 << (1 << width_code)) - 1
    return dict(addr=addr, rmask=0 if store else mask, wmask=mask if store else 0,
                completed_rmask=0, completed_wmask=0, rdata=None, wdata=None)
