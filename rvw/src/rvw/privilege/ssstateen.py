"""Ssstateen-only profiles with no machine state-enable bank."""
from itertools import product
from .extensions import access, row
from .state_hierarchy import PROBES, observation_bindings, observation_forbidden_pcs

VERSION='Ssstateen-1.0'


def programs(config):
    isa=config['isa'];options=config['stateen'];extensions=isa.split('_')
    if config.get('spec_version') != VERSION:raise ValueError('unsupported Ssstateen version')
    if not isa.startswith('rv64') or 'ssstateen' not in extensions or 'smstateen' in extensions:
        raise ValueError('Ssstateen-only probes require RV64 Ssstateen without Smstateen')
    hyper='h' in extensions[0][4:];probes=options.get('probes',['stateen','envcfg','csrind','zfinx'])
    if not probes or len(set(probes)) != len(probes) or set(probes)-{'stateen','envcfg','csrind','zfinx','jvt','zfinx-op'}:
        raise ValueError('select distinct Ssstateen extension probes')
    required={PROBES[p][0] for p in probes if hyper or PROBES[p][2]}
    if not required.issubset(options['writable_bits']):raise ValueError('selected Ssstateen gates must be writable')
    for probe in probes:
        extension=PROBES[probe][3]
        if extension and extension not in extensions:raise ValueError(probe+' requires '+extension)
    rows=[]
    for probe in probes:
        bit,csr,user_state,_=PROBES[probe]
        for index in range(4) if probe=='stateen' else [0]:
            for hg,sg in product((0,1),repeat=2):
                if not hyper and hg or not user_state and sg:continue
                for mode in ('M','S','U','VS','VU') if hyper else ('M','S','U'):
                    user=mode in ('U','VU');virtual=mode in ('VS','VU')
                    denied=(virtual and not hg) or (user and (not user_state or not sg))
                    cause=22 if virtual else 2
                    setup=' li t0, -1\n'
                    if hyper:
                        setup+=' li t1, 1\n slli t1, t1, 39\n csrc mstatus, t1\n'
                        for i in range(4):setup+=f' csrw {0x60c+i:#x}, t0\n'
                    for i in range(4):setup+=f' csrw {0x10c+i:#x}, t0\n'
                    if user_state:setup+=f' li t0, {sg << bit}\n csrw 0x10c, t0\n'
                    if hyper:setup+=f' li t0, {-1 if hg else ((1<<64)-1)^(1<<bit)}\n csrw {0x60c+index:#x}, t0\n'
                    operation=f'csrr a0, {0x10c+index if probe=="stateen" else csr:#x}' if probe!='zfinx-op' else '.word 0x00c58553\n li t0, 0x40400000\n bne a0, t0, fail'
                    if probe=='zfinx-op':setup+=' li a1, 0x3f800000\n li a2, 0x40000000\n'
                    if probe=='stateen' and not user:operation=f'csrr a1, {0x10c+(index+1)%4:#x}\ntarget_site:\n '+operation
                    if mode=='VU':setup+=' li t0, 1\n slli t0, t0, 39\n csrs mstatus, t0\n'
                    code=access('U' if mode=='VU' else mode,setup,operation,denied,cause)
                    if probe=='stateen' and not user and denied:code=code.replace('la t1, access_site','la t1, target_site')
                    code=code.replace('handler:\n csrr t0, mcause','handler:\nstateen_cause_read:\n csrr t0, mcause',1).replace(' csrr t0, mepc','stateen_epc_read:\n csrr t0, mepc',1)
                    plan=dict(kind='ssstateen-access',probe=probe,index=index,mode=mode,machine=1,hypervisor=hg,supervisor=sg,guest_index=0,denied=denied,cause=cause)
                    item=row(f'ssstateen-{probe}-{index}-{mode.lower()}-{hg}{sg}',code,'priv/smstateen.html')
                    item.update(spec_version=VERSION,reference_model=plan,reference_mode='model-observations',
                                model_bindings=observation_bindings(plan),model_forbidden_pcs=observation_forbidden_pcs(plan))
                    rows.append(item)
    return rows


def reference(scenario):
    """Apply the Ssstateen hierarchy with no machine-level gate."""
    p=scenario['reference_model'];mode=p['mode'];user_state=PROBES[p['probe']][2]
    if p['machine']!=1:raise ValueError('Ssstateen-only model has no machine gate')
    cause={'M':11,'S':9,'U':8,'VS':10,'VU':8}[mode];denied=False
    if mode in ('VS','VU') and not p['hypervisor']:denied=True;cause=22
    elif mode in ('U','VU') and (not user_state or not p['supervisor']):denied=True;cause=22 if mode=='VU' else 2
    actual=dict(denied=denied,cause=cause)
    expected=dict(denied=p['denied'],cause=p['cause'] if p['denied'] else {'M':11,'S':9,'U':8,'VS':10,'VU':8}[mode])
    return dict(id=scenario['id'],status='pass' if actual==expected else 'fail',evidence='model-based',actual=actual,expected=expected,
                scope='Ssstateen access/trap expectation only; no DUT execution')
