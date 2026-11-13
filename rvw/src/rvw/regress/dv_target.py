"""Translate project declarations to the pinned pygen target settings."""
import json
import re
from pathlib import Path

from rvw.csr.catalog import load_model


def derive(platform, csrs):
    data = json.loads(Path(platform).read_text())
    isa = data['isa'].lower()
    match = re.fullmatch(r'rv(32|64)([imac]+)(?:_z[a-z0-9]+)*', isa)
    if not match or not {'i', 'm'} <= set(match[2]):
        raise ValueError('pygen target requires declared RV32IM or RV64IM ISA')
    xlen = int(match[1])
    if data['xlen'] != xlen:
        raise ValueError('platform XLEN differs from ISA')
    modes = list(data['privilege_modes'])
    if not modes or 'M' not in modes or set(modes) - set('MSU'):
        raise ValueError('declare privilege modes from M, S, U')
    model = load_model(csrs)
    if model['xlen'] != xlen:
        raise ValueError('CSR selection XLEN differs from platform')
    rows = [r for r in model['csrs'] if r.get('present', True)]
    if any(r.get('privilege') not in modes for r in rows):
        raise ValueError('CSR selection requires an undeclared privilege mode')
    reset = int(data['reset_pc'], 0)
    ram = next((r for r in data['ram'] if int(r['base'], 0) == reset), None)
    if ram is None:
        raise ValueError('declare RAM starting at the reset PC')
    return dict(schema='rvw.dv-target/1', xlen=xlen, isa=isa,
                privilege_modes=modes, csrs=rows, reset_pc=reset,
                ram_size=int(ram['size'], 0),
                unaligned_load_store=all(data.get('misaligned', {}).get(kind) == 'emulate'
                                         for kind in ('load', 'store')),
                pmp_regions=data.get('pmp_regions', 0))


def apply(target, module, package):
    """Replace architectural preset values before pygen imports its config.

    Keep only nonarchitectural generator constants from the pinned upstream
    module. Do not write to the installed generator checkout.
    """
    module.XLEN = target['xlen']
    module.supported_isa = [getattr(package.riscv_instr_group_t,
        f"RV{width}{extension.upper()}") for width in ((32, 64) if target['xlen'] == 64 else (32,))
        for extension in 'imac'
        if extension in target['isa'].split('_')[0][4:]]
    modes = dict(M='MACHINE_MODE', S='SUPERVISOR_MODE', U='USER_MODE')
    module.supported_privileged_mode = [getattr(package.privileged_mode_t, modes[m])
                                       for m in target['privilege_modes']]
    # Standard names absent from this pinned generator remain numeric custom CSRs.
    module.implemented_csr = []
    module.custom_csr = []
    for row in target['csrs']:
        enum = getattr(package.privileged_reg_t, row['name'].upper(), None)
        if enum is None:
            module.custom_csr.append(row['address'])
        else:
            module.implemented_csr.append(enum)
    module.support_unaligned_load_store = int(target['unaligned_load_store'])
    module.support_pmp = int(target['pmp_regions'] > 0)
    module.support_sfence = int('S' in target['privilege_modes'])
    module.SATP_MODE = package.satp_mode_t.BARE
    module.supported_interrupt_mode = [package.mtvec_mode_t.DIRECT]
