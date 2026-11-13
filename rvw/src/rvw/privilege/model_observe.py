"""Model-based C2 observations. This is not a complete ISA comparison."""
from pathlib import Path
import hashlib
import importlib
from rvw.cosim.elf import Elf
from rvw.cosim.trace import Trace


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _observe(elf,scenario,trace_path,c1_identity):
    bindings=scenario.get('model_bindings',[])
    if not bindings:return dict(status='inconclusive',reason='no model observation bindings')
    image=Elf(elf);symbols=image.symbols
    def number(value):
        if isinstance(value,dict):return symbols[value['symbol']]
        return int(value,0) if isinstance(value,str) else value
    wanted={};seen={};required={number(v) for v in scenario.get('model_required_pcs',[])};visited=set()
    forbidden={number(v) for v in scenario.get('model_forbidden_pcs',[])}
    for binding in bindings:
        pc=symbols[binding['symbol']]
        if pc in wanted:raise ValueError('duplicate model observation PC')
        wanted[pc]=binding;seen[pc]=[]
    for item in scenario.get('model_forbidden_pcs',[]):
        if isinstance(item,dict) and 'insn' in item:
            pc=number(item)
            raw=next((data[pc-address:pc-address+4] for address,data,_ in image.segments if address<=pc and pc+4<=address+len(data)),None)
            if raw is None or int.from_bytes(raw,'little')!=number(item['insn']):
                return dict(status='inconclusive',reason='denied instruction differs from the model')
    end=None;instructions=0;trace=None
    try:
        trace=Trace(trace_path)
        if trace.multihart or not trace.state or trace.header.get('elf_sha256')!=scenario['elf_sha256'] or trace.header['xlen']!=image.xlen:
            return dict(status='inconclusive',reason='C2 state, hart or ELF binding differs')
        if c1_identity is not None:
            if not all(c1_identity.get(k) and trace.header.get(k)==c1_identity[k] for k in ('core','config')):
                return dict(status='inconclusive',reason='C2 core/config identity differs from C1')
            if trace.header.get('evidence')=='model-based' or trace.header['config']=='reference':
                return dict(status='inconclusive',reason='reference trace cannot earn C1 observation groups')
        for row in trace:
            if row.get('event')=='end':end=row['status'];continue
            if 'event' in row:continue
            instructions+=1
            if row['trap'] or row['mem_fault']:continue
            pc=row['pc'];visited.add(pc)
            if pc not in wanted and pc not in required and pc not in forbidden:continue
            raw=next((data[pc-address:pc-address+4] for address,data,_ in image.segments
                      if address<=pc and pc+4<=address+len(data)),None)
            if raw is None or int.from_bytes(raw,'little')!=row['insn']:
                return dict(status='inconclusive',reason='observed instruction differs from the bound ELF',symbol=wanted[pc]['symbol'] if pc in wanted else hex(pc))
            if pc in forbidden:return dict(status='fail',reason='denied model instruction retired',pc=hex(pc))
            if pc not in wanted:continue
            b=wanted[pc]
            if row['mode']!=b.get('mode',3):
                return dict(status='fail',reason='model read executed in the wrong privilege mode',symbol=b['symbol'])
            if 'virtual' in b:
                virtual=row.get('hypervisor',{}).get('virtual',False if not b['virtual'] else None)
                if virtual is None:return dict(status='inconclusive',reason='missing virtual-mode observation',symbol=b['symbol'])
                if virtual!=b['virtual']:return dict(status='fail',reason='wrong virtual mode at model instruction',symbol=b['symbol'])
            if row['rd']==0 or row['rd']!=((row['insn']>>7)&31):
                return dict(status='fail',reason='model read destination differs',symbol=b['symbol'])
            if b['kind']=='csr':
                if row['insn']&0x7f!=0x73 or (row['insn']>>12)&7!=2 or (row['insn']>>15)&31 or row['insn']>>20!=number(b['csr']):
                    return dict(status='inconclusive',reason='binding is not the expected CSR read',symbol=b['symbol'])
            elif b['kind']=='load':
                if row['insn']&0x7f!=3 or row['mem_addr']!=number(b['address']) or row['mem_rmask'].bit_count()!=b['width'] or row['mem_wmask']:
                    return dict(status='fail',reason='model MMIO read shape differs',symbol=b['symbol'])
            elif b['kind']=='writeback':
                if row['insn']!=number(b['insn']) or row['mem_rmask'] or row['mem_wmask']:
                    return dict(status='inconclusive',reason='instruction-result binding differs',symbol=b['symbol'])
            else:raise ValueError('unsupported model binding kind')
            seen[pc].append(row['rd_wdata'])
            mask=number(b.get('mask',hex((1<<image.xlen)-1)));index=len(seen[pc])-1
            if index>=len(b['expected']):
                return dict(status='fail',reason='extra model observation',symbol=b['symbol'])
            expected=number(b['expected'][index])&mask
            if row['rd_wdata']&mask!=expected or (b['kind']=='load' and row['mem_rdata']&mask!=expected):
                return dict(status='fail',reason='DUT observation differs from the Python expectation',symbol=b['symbol'],index=index)
    except (OSError,ValueError,KeyError) as exc:
        return dict(status='inconclusive',reason='invalid or incomplete model trace: '+str(exc))
    finally:
        if trace:trace.close()
    if end not in ('pass','fail') or not instructions:
        return dict(status='inconclusive',reason='need a complete C2 trace with an explicit end status')
    if end=='fail':return dict(status='fail',reason='C2 program failed')
    missing=[b['symbol'] for pc,b in wanted.items() if len(seen[pc])!=len(b['expected'])]
    if missing or required-visited:
        return dict(status='inconclusive',reason='missing model observations or required program PCs',missing=missing)
    return dict(status='pass',evidence='model-based',trace_sha256=digest(trace_path),observations=sum(map(len,seen.values())),
                scope='named instruction results, CSR/MMIO observations and program PCs only; no complete ISA comparison')


def observe(elf,scenario,trace_path,c1_identity=None):
    sources=[]
    try:
        kind=scenario['reference_model']['kind']
        module={'ssstateen-access':'ssstateen','stateen-access':'state_hierarchy','reri-transactions':'reri_transactions','fast-preemption':'fast_preemption','fast-vector':'fast_vector'}.get(kind)
        if module is None:raise ValueError('no bound observation model for this scenario')
        model=importlib.import_module('rvw.privilege.'+module);plan=scenario['reference_model']
        if scenario.get('spec_version')!=getattr(model,'VERSION',getattr(model,'FAST',None)):
            raise ValueError('unsupported model specification version')
        oracle=model.reference(scenario)
        if oracle['status']!='pass':raise ValueError('model plan does not match the current reference')
        if scenario.get('model_bindings')!=model.observation_bindings(plan):
            raise ValueError('observation bindings differ from the pinned Python model')
        if scenario.get('model_required_pcs',[])!=(model.observation_pcs(plan) if hasattr(model,'observation_pcs') else []):
            raise ValueError('required program PCs differ from the pinned Python model')
        if scenario.get('model_forbidden_pcs',[])!=(model.observation_forbidden_pcs(plan) if hasattr(model,'observation_forbidden_pcs') else []):
            raise ValueError('forbidden program PCs differ from the pinned Python model')
        sources=[Path(model.__file__),Path(__file__),Path(importlib.import_module('rvw.cosim.trace').__file__),
                 Path(importlib.import_module('rvw.cosim.elf').__file__),
                 Path(importlib.import_module('rvw.privilege.'+('reri' if kind=='reri-transactions' else 'controllers')).__file__)]
        if kind=='ssstateen-access':sources.append(Path(importlib.import_module('rvw.privilege.state_hierarchy').__file__))
        result=_observe(elf,scenario,trace_path,c1_identity)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result=dict(status='inconclusive',reason=str(exc))
    result.update(evidence='model-based',scope='named instruction results, CSR/MMIO observations and program PCs only; no complete ISA comparison',
                  model_sha256={p.name:digest(p) for p in sources})
    if Path(trace_path).is_file():result['trace_sha256']=digest(trace_path)
    return result
