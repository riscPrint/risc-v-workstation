"""Zicbom environment gates and legal field readback; no cache-effect claim."""
from itertools import product
from .extensions import access

VERSION='CMO-1.0.0'
SPEC='https://docs.riscv.org/reference/isa/v20260120/unpriv/cmo.html'
INSTRUCTIONS={'inval':0x0005200f,'clean':0x0015200f,'flush':0x0025200f}


def decision(operation,mode,machine,hypervisor,supervisor):
    gates={'M':[],'S':[machine],'U':[machine,supervisor],
           'VS':[machine,hypervisor],'VU':[machine,hypervisor,supervisor]}[mode]
    if mode!='M' and (not machine or mode=='U' and not supervisor):
        return dict(denied=True,cause=2,expected_operation=None)
    if mode in ('VS','VU') and (not hypervisor or mode=='VU' and not supervisor):
        return dict(denied=True,cause=22,expected_operation=None)
    effective='flush' if operation=='inval' and 1 in gates else operation
    return dict(denied=False,cause={'M':11,'S':9,'U':8,'VS':10,'VU':8}[mode],expected_operation=effective)


def legal_values(options,field,level):
    values=options[field][level];allowed=(0,1,3) if field=='cbie' else (0,1)
    if not values or len(set(values))!=len(values) or any(type(v) is not int or v not in allowed for v in values):
        raise ValueError('declare distinct legal '+field+' values for '+level)
    return values


def programs(config):
    isa=config['isa'];o=config['envcfg']
    if config.get('spec_version')!=VERSION:raise ValueError('unsupported CMO specification version')
    if not isa.startswith(('rv32','rv64')) or 'zicbom' not in isa.split('_'):raise ValueError('CBOM environment probes require RV32/RV64 Zicbom')
    xlen=int(isa[2:4])
    size=o['block_bytes']
    if type(size) is not int or not 16<=size<=4096 or size&(size-1):raise ValueError('block_bytes must be a power of two in 16..4096')
    operations=o.get('operations',['clean','flush','inval'])
    if not operations or len(set(operations))!=len(operations) or set(operations)-set(INSTRUCTIONS):raise ValueError('select distinct CBOM operations')
    hyper='h' in isa.split('_')[0][4:];modes=list(config.get('modes',['M','S','U']))
    if hyper and o.get('virtualization',True):modes+=['VS','VU']
    rows=[]
    for operation in operations:
        field='cbie' if operation=='inval' else 'cbcfe';shift=4 if field=='cbie' else 6;mask=(3 if field=='cbie' else 1)<<shift
        mv=legal_values(o,field,'machine');sv=legal_values(o,field,'supervisor');hv=legal_values(o,field,'hypervisor') if hyper else [None]
        for machine,guest,supervisor in product(mv,hv,sv):
            for mode in modes:
                outcome=decision(operation,mode,machine,guest,supervisor)
                setup=(' li t0, 128\n csrc 0x310, t0\n' if xlen==32 else ' li t0, 1\n slli t0, t0, 39\n csrc mstatus, t0\n') if hyper else ''
                registers=[(0x30a,machine),(0x10a,supervisor)]+([(0x60a,guest)] if hyper else [])
                for csr,value in registers:
                    setup+=f''' li t0, {value<<shift}
 csrw {csr:#x}, t0
 csrr t1, {csr:#x}
 li t2, {mask}
 and t1, t1, t2
 bne t0, t1, fail
'''
                if mode=='VU':setup+=(' li t0, 128\n csrs 0x310, t0\n' if xlen==32 else ' li t0, 1\n slli t0, t0, 39\n csrs mstatus, t0\n')
                setup+=' la a0, cbo_buffer\n'
                code=access('U' if mode=='VU' else mode,setup,f'.word {INSTRUCTIONS[operation]:#x}',outcome['denied'],cause=outcome['cause'],xlen=xlen)
                code+=f'''.section .data
.balign {size}
cbo_buffer: .space {size}
'''
                gates=f'{machine}{guest if hyper else "n"}{supervisor}'
                name=f'envcfg-cbom-{operation}-{mode.lower()}-{gates}'
                rows.append(dict(id=name,family='envcfg',assembly=code,spec_version=VERSION,spec=SPEC,
                    bins=[f'envcfg.cbom.access.{operation}.{mode}',f'envcfg.cbom.controls.{operation}.{mode}.{gates}'],
                    reference_options=['--blocksz='+str(size)],
                    expected_outcome=dict(operation=operation,mode=mode,machine=machine,hypervisor=guest,supervisor=supervisor,**outcome),
                    scope='legal field readback and instruction permission/trap only; no cache side-effect check'))
    return rows
