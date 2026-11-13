"""RV32 state-enable split banks and privilege access probes."""
from itertools import product
from .programs import HEAD
from .timer32 import TAIL32
from .disabled import enter
from .state_hierarchy import VERSION, PROBES, expected_access


def write_bank(base, index, value):
    """Write both halves without an RV64 shift or an assembler CSR alias."""
    value &= (1 << 64) - 1
    return (f' li t0, {value & 0xffffffff}\n csrw {base+index:#x}, t0\n'
            f' li t0, {value >> 32}\n csrw {base+16+index:#x}, t0\n')


def check_bit(csr, bit, value):
    return (f' csrr t1, {csr:#x}\n li t0, {1 << bit}\n and t1, t1, t0\n'
            f' li t0, {value << bit}\n bne t0, t1, fail\n')


def program(probe, index, mode, mg, hg, sg, hyper):
    bit, csr, user_state, _ = PROBES[probe]
    denied, cause = expected_access(probe, mode, mg, hg, sg, 0)
    code = HEAD + ' la t0, handler\n csrw mtvec, t0\n'
    if hyper:code += ' li t0, 128\n csrc 0x310, t0\n'
    for i in range(4):code += write_bank(0x30c, i, -1)
    if hyper:
        for i in range(4):code += write_bank(0x60c, i, -1)
    code += ' li t0, -1\n'
    for i in range(4):code += f' csrw {0x10c+i:#x}, t0\n'
    if user_state:code += f' li t0, {sg << bit}\n csrw 0x10c, t0\n'
    if hyper:code += write_bank(0x60c, index, -1 if hg else ((1 << 64)-1) ^ (1 << bit))
    code += write_bank(0x30c, index, -1 if mg else ((1 << 64)-1) ^ (1 << bit))
    # The chosen bit must be writable. Read it in M to avoid an access trap.
    half = 16 if bit >= 32 else 0
    code += check_bit(0x30c+index+half, bit % 32, mg)
    if hyper:code += check_bit(0x60c+index+half, bit % 32, mg & hg)
    # Changing a high half must retain the implemented low Zfinx gate.
    # Changing the low gate must retain the high SE gate.
    code += check_bit(0x30c if bit >= 32 else 0x31c, 1 if bit >= 32 else 31, 1)
    if probe == 'stateen':code += check_bit(0x31c+(index+1)%4, 31, 1)
    if mode in ('VS','VU'):code += ' li t0, 128\n csrs 0x310, t0\n'
    code += enter('S' if mode == 'VS' else 'U' if mode == 'VU' else mode)
    code += f'''access_site:
 csrr a0, {0x10c+index if probe == 'stateen' else csr:#x}
ecall_site:
 ecall
 j fail
handler:
 csrr t0, mcause
 li t1, {cause if denied else dict(M=11,S=9,U=8,VS=10,VU=8)[mode]}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'access_site' if denied else 'ecall_site'}
 bne t0, t1, fail
 j pass
'''
    return code + TAIL32


def programs(config):
    isa=config['isa'];options=config['stateen'];probes=options.get('probes',['stateen','envcfg','csrind','zfinx'])
    if config.get('spec_version') != VERSION:raise ValueError('unsupported Smstateen version')
    if not isa.startswith('rv32') or 'smstateen' not in isa.split('_'):
        raise ValueError('RV32 state-enable probes require RV32 Smstateen')
    if not probes or len(set(probes)) != len(probes) or set(probes)-{'stateen','envcfg','csrind','zfinx'}:
        raise ValueError('select distinct RV32 state-enable probes')
    required={PROBES[p][0] for p in probes}|{1,63}
    if not required.issubset(options['writable_bits']):raise ValueError('selected and retained state-enable gates must be writable')
    if 'zfinx' not in isa.split('_'):raise ValueError('RV32 split-bank readback requires the Zfinx low gate')
    if 'csrind' in probes and 'sscsrind' not in isa.split('_'):raise ValueError('csrind requires Sscsrind')
    hyper='h' in isa.split('_')[0][4:];rows=[]
    for probe in probes:
        for index in range(4) if probe == 'stateen' else [0]:
            for mg,hg,sg in product((0,1),repeat=3):
                if not hyper and hg or not PROBES[probe][2] and sg:continue
                for mode in ('M','S','U','VS','VU') if hyper else ('M','S','U'):
                    name=f'stateen32-{probe}-{index}-{mode.lower()}-{mg}{hg}{sg}'
                    rows.append(dict(id=name,family='stateen32',bins=[name,f'stateen32.half.{"high" if PROBES[probe][0]>=32 else "low"}'],
                        assembly=program(probe,index,mode,mg,hg,sg,hyper),spec_version=VERSION,
                        spec='https://docs.riscv.org/reference/isa/v20260120/priv/smstateen.html'))
    return rows
