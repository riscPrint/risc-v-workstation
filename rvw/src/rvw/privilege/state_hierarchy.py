"""Smstateen 1.0 hierarchy probes with explicit writable-gate contracts."""
from itertools import product
from .extensions import access, row


VERSION='Smstateen-1.0'

PROBES={
    'stateen':(63,None,False,None), 'envcfg':(62,0x10a,False,None),
    'zfinx':(1,0x003,True,'zfinx'), 'zfinx-op':(1,None,True,'zfinx'), 'jvt':(2,0x017,True,'zcmt'),
    'aia':(59,0xdb0,False,'ssaia'), 'csrind':(60,0x150,False,'sscsrind'),
    'imsic':(58,0x15c,False,'ssaia'), 'context':(57,0x5a8,False,None),
}


def programs(config):
    isa=config['isa']; options=config['stateen']
    if config.get('spec_version',VERSION)!=VERSION:raise ValueError('unsupported Smstateen version')
    if not isa.startswith('rv64') or 'smstateen' not in isa:
        raise ValueError('state hierarchy requires RV64 Smstateen')
    hyper='h' in isa.split('_')[0][4:]
    probes=options.get('probes',['stateen','envcfg'])
    if not probes or len(set(probes))!=len(probes) or set(probes)-set(PROBES):
        raise ValueError('stateen probes must select distinct known extension state')
    for name in probes:
        extension=PROBES[name][3]
        if extension and extension not in isa.split('_'):
            raise ValueError(f'{name} probes require '+('Zfinx' if name=='zfinx' else extension))
    if 'context' in probes and options.get('context_supported') is not True:
        raise ValueError('context probes require declared trigger-context support')
    guest=options.get('guest_index',0)
    if type(guest) is not int or not 0<=guest<64:raise ValueError('invalid guest_index')
    gates=options['writable_bits'];required={PROBES[p][0] for p in probes}
    if not required.issubset(gates):
        raise ValueError('selected stateen gates must be declared writable')
    rows=[]
    for probe in probes:
        for index in (range(4) if probe=='stateen' else [0]):
            bit,csr,user_state,_=PROBES[probe]
            for mg,hg,sg in product((0,1),repeat=3):
                if not hyper and hg:continue
                if not user_state and sg:continue
                for mode in (('M','S','U','VS','VU') if hyper else ('M','S','U')):
                    # VU access to an HS-qualified supervisor CSR raises cause 22.
                    user=mode in ('U','VU')
                    denied=(mode!='M' and not mg) or (mode in ('VS','VU') and not hg) or (user_state and user and not sg)
                    if not user_state and user:denied=True
                    if probe=='imsic' and mode=='VS' and not guest:denied=True
                    cause=22 if mode in ('VS','VU') and mg and denied else 2
                    setup=' li t0, -1\n'
                    for i in range(4):setup+=f' csrw {0x30c+i:#x}, t0\n'
                    if hyper:
                        setup+=' li t1, 1\n slli t1, t1, 39\n csrc mstatus, t1\n'
                        for i in range(4):setup+=f' csrw {0x60c+i:#x}, t0\n'
                    # Initialize sstateen while the controlling SE bits allow access.
                    for i in range(4):setup+=f' csrw {0x10c+i:#x}, t0\n'
                    if user_state:
                        setup+=f' li t0, {(1<<bit) if sg else 0}\n csrw 0x10c, t0\n'
                    if hyper:
                        setup+=f' li t0, {-1 if hg else ((1<<64)-1)^(1<<bit)}\n csrw {0x60c+index:#x}, t0\n'
                    setup+=f' li t0, {-1 if mg else ((1<<64)-1)^(1<<bit)}\n csrw {0x30c+index:#x}, t0\n'
                    if probe=='zfinx-op':
                        setup+=' li a1, 0x3f800000\n li a2, 0x40000000\n'
                        operation='.word 0x00c58553\n li t0, 0x40400000\n bne a0, t0, fail'
                    else:operation=f'csrr a0, {0x10c+index if probe=="stateen" else csr:#x}'
                    if probe=='imsic' and hyper:
                        setup+=f' li t0, {guest<<12}\n csrw hstatus, t0\n'
                    if probe=='stateen' and not user:
                        operation=f'csrr a1, {0x10c+(index+1)%4:#x}\ntarget_site:\n '+operation
                    actual_mode='VS' if mode=='VS' else 'U' if mode=='VU' else mode
                    if mode=='VU':setup+=' li t0, 1\n slli t0, t0, 39\n csrs mstatus, t0\n'
                    code=access(actual_mode,setup,operation,denied,cause=cause)
                    if probe=='stateen' and not user and denied:
                        code=code.replace('la t1, access_site','la t1, target_site')
                    # A successful VU ECALL has cause 8, as in ordinary U-mode.
                    name=f'stateen-hierarchy-{probe}-{index}-{mode.lower()}-{mg}{hg}{sg}'
                    item=row(name,code,'priv/smstateen.html')
                    if probe=='imsic' and mode=='VS' and mg and hg and guest:
                        item['reference_unavailable']='Spike CLI profile does not configure this guest IMSIC file'
                    item['spec_version']=VERSION
                    item['reference_model']=dict(kind='stateen-access',probe=probe,index=index,mode=mode,machine=mg,hypervisor=hg,
                        supervisor=sg,guest_index=guest,denied=denied,cause=cause)
                    if config.get('reference_backend')=='python':
                        item['assembly']=code.replace('handler:\n csrr t0, mcause','handler:\nstateen_cause_read:\n csrr t0, mcause',1).replace(' csrr t0, mepc','stateen_epc_read:\n csrr t0, mepc',1)
                        item.update(reference_mode='model-observations',model_bindings=observation_bindings(item['reference_model']),
                                    model_forbidden_pcs=observation_forbidden_pcs(item['reference_model']))
                    rows.append(item)
    return rows


def expected_access(probe,mode,machine,hypervisor,supervisor,guest_index):
    user_state=PROBES[probe][2]
    if mode=='M':return False,2
    if not machine:return True,2
    if mode=='U' and not user_state:return True,2
    if mode in ('VS','VU'):
        if not hypervisor or mode=='VU' and not user_state:return True,22
        if probe=='imsic' and mode=='VS' and not guest_index:return True,22
    if user_state and mode in ('U','VU') and not supervisor:
        return True,22 if mode=='VU' else 2
    return False,2


def reference(scenario):
    p=scenario['reference_model']
    denied,cause=expected_access(p['probe'],p['mode'],p['machine'],p['hypervisor'],p['supervisor'],p['guest_index'])
    actual=dict(denied=denied,cause=cause if denied else {'M':11,'S':9,'U':8,'VS':10,'VU':8}[p['mode']])
    expected=dict(denied=p['denied'],cause=p['cause'] if p['denied'] else {'M':11,'S':9,'U':8,'VS':10,'VU':8}[p['mode']])
    return dict(id=scenario['id'],status='pass' if actual==expected else 'fail',evidence='model-based',actual=actual,expected=expected,
                scope='expected extension-state access/trap only; no DUT execution')


def observation_bindings(plan):
    denied,cause=expected_access(plan['probe'],plan['mode'],plan['machine'],plan['hypervisor'],plan['supervisor'],plan['guest_index'])
    target='target_site' if plan['probe']=='stateen' and plan['mode'] not in ('U','VU') else 'access_site'
    bindings=[dict(symbol='stateen_cause_read',kind='csr',csr='0x342',expected=[hex(cause if denied else {'M':11,'S':9,'U':8,'VS':10,'VU':8}[plan['mode']])]),
              dict(symbol='stateen_epc_read',kind='csr',csr='0x341',expected=[{'symbol':target if denied else 'ecall_site'}])]
    if not denied:
        read=dict(symbol=target,mode={'M':3,'S':1,'U':0,'VS':1,'VU':0}[plan['mode']],virtual=plan['mode'] in ('VS','VU'))
        if plan['probe']=='zfinx-op':read.update(kind='writeback',insn='0x00c58553',expected=['0x40400000'])
        else:read.update(kind='csr',csr=hex(0x10c+plan['index'] if plan['probe']=='stateen' else PROBES[plan['probe']][1]),mask='0x0',expected=['0x0'])
        bindings.append(read)
    return bindings


def observation_forbidden_pcs(plan):
    denied,_=expected_access(plan['probe'],plan['mode'],plan['machine'],plan['hypervisor'],plan['supervisor'],plan['guest_index'])
    target='target_site' if plan['probe']=='stateen' and plan['mode'] not in ('U','VU') else 'access_site'
    return [{'symbol':target}] if denied else []
