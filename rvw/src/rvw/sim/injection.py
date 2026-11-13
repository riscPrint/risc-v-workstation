"""Architectural state injection through a project-declared signal map.

This rebuilds microarchitecture. It is not a live native model restore.
The producer must export a complete, profile-qualified architectural inventory.
"""
from __future__ import annotations


def plan(state, mapping):
    """Validate every binding and value before stopping or modifying the DUT.

    Both documents use named profiles owned by the project. This API does not
    infer CSR completeness from whatever CSRs a producer happened to observe.
    """
    if state.get('schema') != 'rvw.arch-injection/1' or mapping.get('schema') != 'rvw.arch-map/1':
        raise ValueError('unsupported architectural injection schema')
    if state.get('profile') != mapping.get('profile') or not state.get('profile'):
        raise ValueError('architectural profile mismatch')
    xlen, flen = mapping['xlen'], mapping['flen']
    if xlen not in (32, 64) or flen not in (0, 32, 64):
        raise ValueError('unsupported architectural register widths')
    # Hidden state cannot be silently discarded when rebuilding a pipeline.
    if state.get('execution') != {'harts': 1, 'pending_trap': False,
            'reservation': False, 'debug': False, 'wfi': False, 'external_effects': []}:
        raise ValueError('unsupported execution state')
    if state.get('privilege') != 'M':
        raise ValueError('only M-mode injection is supported')
    if state.get('devices') != [] or state.get('pending_interrupts') != []:
        raise ValueError('device and interrupt injection is not implemented')
    if state.get('translation') != 'bare':
        raise ValueError('virtual memory injection needs a qualified TLB invalidation port')
    gpr, fpr = state['gpr'], state['fpr']
    if len(gpr) != 32 or gpr[0] != 0 or len(mapping['gpr']) != 32:
        raise ValueError('all GPRs and x0=0 are required')
    if len(fpr) != (32 if flen else 0) or len(mapping['fpr']) != len(fpr):
        raise ValueError('complete raw FPR inventory required')
    if set(state['csr']) != set(mapping['csr']):
        raise ValueError('CSR inventory differs from project profile')
    writes = [(mapping['pc'], state['pc'], xlen)]
    writes += [(name, value, xlen) for name, value in zip(mapping['gpr'][1:], gpr[1:])]
    writes += [(name, value, flen) for name, value in zip(mapping['fpr'], fpr)]
    writes += [(mapping['csr'][name], value, xlen) for name, value in state['csr'].items()]
    names = [name for name, _, _ in writes]
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        raise ValueError('injection bindings must be unique signal names')
    for _, value, width in writes:
        if type(value) is not int or not 0 <= value < (1 << width):
            raise ValueError('architectural value is outside its raw register width')
    regions = []
    for row in state['memory']:
        address, data = row['address'], bytes.fromhex(row['hex'])
        if type(address) is not int or address < 0 or address + len(data) > 1 << xlen or not data:
            raise ValueError('invalid physical memory image')
        if any(address < base + len(raw) and base < address + len(data) for base, raw in regions):
            raise ValueError('overlapping physical memory images')
        regions.append((address, data))
    return writes, regions


def inject(port, state, mapping):
    """Read back all injected state before fetch release. Discard DUT on error."""
    writes, regions = plan(state, mapping)
    port.hold_fetch()
    # The project port must reset/flush hidden pipeline state and invalidate caches.
    port.clear_microarchitecture()
    for address, data in regions:
        port.write_memory(address, data)
    for name, value, _ in writes:
        port.write_signal(name, value)
    for name, value, _ in writes:
        if port.read_signal(name) != value:
            raise ValueError(f'architectural readback mismatch: {name}')
    for address, data in regions:
        if port.read_memory(address, len(data)) != data:
            raise ValueError(f'architectural memory readback mismatch: {address:#x}')
    port.release_fetch()
    return {'status': 'injected', 'profile': state['profile'],
            'registers': len(writes), 'memory_bytes': sum(len(data) for _, data in regions)}


def bootstrap_rv32(state, mapping):
    """Emit an RV32IM M-mode bootstrap for a core without injection hooks.

    Link at a project-selected RAM address within JAL range of the target PC.
    CSR writes precede GPR restore. A direct JAL preserves every restored GPR.
    This path refuses FP, translation, device state and interrupt-enabled state.
    Memory images must be loaded separately before reset release.
    """
    plan(state, mapping)
    if mapping['xlen'] != 32 or mapping['flen'] or state['fpr']:
        raise ValueError('bootstrap supports RV32IM only')
    supported = {'0x300', '0x304', '0x305', '0x340', '0x341', '0x342', '0x343', '0x344'}
    if set(state['csr']) - supported:
        raise ValueError('bootstrap CSR profile is unsupported')
    if any(name in state['csr'] and state['csr'][name] for name in ('0x304', '0x344')):
        raise ValueError('bootstrap requires disabled interrupts')
    if state['csr'].get('0x300', 0) & 8:
        raise ValueError('bootstrap requires mstatus.MIE=0')
    lines = ['.option norvc', '.option norelax', '.section .text.rvw_restore,"ax"',
             '.globl _rvw_restore', '_rvw_restore:']
    for csr, value in state['csr'].items():
        address = int(csr, 16)
        if not 0 <= address < 4096 or address >= 0xc00:
            raise ValueError('bootstrap requires writable CSR addresses')
        lines += [f'  li x5, {value:#x}', f'  csrw {address:#x}, x5']
    for reg, value in enumerate(state['gpr'][1:], 1):
        lines.append(f'  li x{reg}, {value:#x}')
    lines += ['  jal x0, __rvw_resume_pc', f'.globl __rvw_resume_pc',
              f'.set __rvw_resume_pc, {state["pc"]:#x}']
    return '\n'.join(lines) + '\n'
