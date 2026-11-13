"""Smstateen 1.0 hierarchy probes with explicit writable-gate contracts."""
from itertools import product
from .extensions import access, row


def programs(config):
    isa=config['isa']; options=config['stateen']
    if not isa.startswith('rv64') or 'smstateen' not in isa:
        raise ValueError('state hierarchy requires RV64 Smstateen')
    hyper='h' in isa.split('_')[0][4:]
    probes=options.get('probes',['stateen','envcfg'])
    if set(probes)-{'stateen','envcfg','zfinx'} or not probes:
        raise ValueError('stateen probes must select stateen, envcfg or zfinx')
    if 'zfinx' in probes and 'zfinx' not in isa:
        raise ValueError('FCSR probes require Zfinx')
    gates=options['writable_bits']
    required=({63} if 'stateen' in probes else set())|({62} if 'envcfg' in probes else set())|({1} if 'zfinx' in probes else set())
    if not required.issubset(gates):
        raise ValueError('selected stateen gates must be declared writable')
    rows=[]
    for probe in probes:
        for index in (range(4) if probe=='stateen' else [0]):
            bit={'stateen':63,'envcfg':62,'zfinx':1}[probe]
            for mg,hg,sg in product((0,1),repeat=3):
                if not hyper and hg:continue
                if probe!='zfinx' and sg:continue
                for mode in (('M','S','U','VS','VU') if hyper else ('M','S','U')):
                    # VU access to an HS-qualified supervisor CSR raises cause 22.
                    user=mode in ('U','VU')
                    denied=(mode!='M' and not mg) or (mode in ('VS','VU') and not hg) or (probe=='zfinx' and user and not sg)
                    if probe!='zfinx' and user:denied=True
                    cause=22 if mode in ('VS','VU') and mg and denied else 2
                    setup=' li t0, -1\n'
                    for i in range(4):setup+=f' csrw {0x30c+i:#x}, t0\n'
                    if hyper:
                        setup+=' li t1, 1\n slli t1, t1, 39\n csrc mstatus, t1\n'
                        for i in range(4):setup+=f' csrw {0x60c+i:#x}, t0\n'
                    # Initialize sstateen while the controlling SE bits allow access.
                    for i in range(4):setup+=f' csrw {0x10c+i:#x}, t0\n'
                    if probe=='zfinx':
                        setup+=f' li t0, {2 if sg else 0}\n csrw 0x10c, t0\n'
                    if hyper:
                        setup+=f' li t0, {-1 if hg else ((1<<64)-1)^(1<<bit)}\n csrw {0x60c+index:#x}, t0\n'
                    setup+=f' li t0, {-1 if mg else ((1<<64)-1)^(1<<bit)}\n csrw {0x30c+index:#x}, t0\n'
                    operation=(f'csrr a0, {0x10c+index:#x}' if probe=='stateen' else 'csrr a0, 0x10a' if probe=='envcfg' else 'csrr a0, 0x003')
                    if probe=='stateen' and not user:
                        operation=f'csrr a1, {0x10c+(index+1)%4:#x}\ntarget_site:\n '+operation
                    actual_mode='VS' if mode=='VS' else 'U' if mode=='VU' else mode
                    if mode=='VU':setup+=' li t0, 1\n slli t0, t0, 39\n csrs mstatus, t0\n'
                    code=access(actual_mode,setup,operation,denied,cause=cause)
                    if probe=='stateen' and not user and denied:
                        code=code.replace('la t1, access_site','la t1, target_site')
                    # A successful VU ECALL has cause 8, as in ordinary U-mode.
                    name=f'stateen-hierarchy-{probe}-{index}-{mode.lower()}-{mg}{hg}{sg}'
                    rows.append(row(name,code,'priv/smstateen.html'))
    return rows
