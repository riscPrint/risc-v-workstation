"""Bounded Spike architectural capture for the RAM-only RV32IM bootstrap."""
from .injection import plan


def capture(model, mapping, *, instructions):
    """Read complete declared physical RAM and profile CSRs after K retirements.

    The project must supply the complete mutable CSR inventory. This helper
    refuses interrupts, traps, FP, multiple RAM regions and non-M-mode state.
    It does not claim C1 capture or pre-fetch readback on a bootstrap target.
    """
    platform = model.platform
    if (type(instructions) is not int or instructions <= 0 or platform.xlen != 32
            or platform.isa.lower() != 'rv32im_zicsr_zifencei'
            or platform.mmio or len(platform.ram) != 1 or mapping['flen']):
        raise ValueError('capture requires a positive RV32IM RAM-only sample')
    base, size = platform.ram[0]
    if base % 8 or size % 8 or not 0 < size <= 16 * 1024 * 1024:
        raise ValueError('capture needs aligned bounded physical RAM')
    for _ in range(instructions):
        effect = model.step()
        if effect['trap'] or effect['intr'] or effect['halted'] or model.mode() != 3:
            raise ValueError('unsupported execution state during capture')
    csr = model.csr_snapshot(list(mapping['csr']))
    if csr.get('0x300', 0) & 8 or csr.get('0x304', 0) or csr.get('0x344', 0):
        raise ValueError('capture requires disabled interrupts')
    memory = b''.join(model.read_physical(a).to_bytes(8, 'little') for a in range(base, base + size, 8))
    state = dict(schema='rvw.arch-injection/1', profile=mapping['profile'],
        pc=effect['pc_next'], gpr=list(model.regs), fpr=[], csr=csr,
        memory=[dict(address=base, hex=memory.hex())], privilege='M', translation='bare',
        devices=[], pending_interrupts=[], execution=dict(harts=1, pending_trap=False,
        reservation=False, debug=False, wfi=False, external_effects=[]))
    plan(state, mapping)
    return state
