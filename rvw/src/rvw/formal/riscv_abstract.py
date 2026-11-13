"""Apply declared pipeline restrictions and the shared lazy RAM abstraction."""
import hashlib
import json
import math
from pathlib import Path
import re
import time
from rvw.common.proc import run_group


def restrict(source, plan):
    names=plan['in_flight']
    if not names or len(set(names))!=len(names):
        raise ValueError('declare distinct in-flight stage observations')
    for name in [plan['module'],plan['clock'],plan['reset'],*names]:
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$]*',name):
            raise ValueError('single-flight observations must be local identifiers')
    count=' + '.join("{31'b0, "+name+'}' for name in names)
    assumption=f"always @(posedge {plan['clock']}) if(!{plan['reset']}) assume(({count}) <= 1);"
    pattern=r'(\bmodule\s+'+re.escape(plan['module'])+r'\b[\s\S]*?)(\bendmodule\b)'
    result,n=re.subn(pattern,lambda m:m[1]+'\n'+assumption+'\n'+m[2],source)
    if n!=1: raise ValueError('single-flight module must occur once')
    return result,assumption


def cover(target, top, depth, solver, out, timeout):
    file=out/(target.stem+'-cover.sby')
    file.write_text(f'[options]\nmode cover\ndepth {depth}\n[engines]\nsmtbmc {solver}\n[script]\nread -formal -sv {target.name}\nprep -top {top}\n[files]\n{target.name}\n')
    with (out/(target.stem+'-cover.log')).open('w') as log:
        result=run_group(['sby','-f',file.name],cwd=out,stdout=log,stderr=log,timeout=timeout)
    directory=out/file.stem;status=directory/'status'
    token=status.read_text().split()[0] if status.is_file() else ''
    reached=(not result.timed_out and result.returncode==0 and token=='PASS' and bool(list(directory.glob('engine_*/trace*.vcd'))))
    return dict(status='reached' if reached else 'timeout' if result.timed_out else 'inconclusive',evidence=directory.name)




def restore_words(mapped, collected, ram, kept):
    from rvw.formal.lazy_ram import abstract_words
    params=collected['modules'][ram['top']]['cells'][ram['memory']]['parameters']
    size,offset=(int(params[k],2) for k in ('SIZE','OFFSET'))
    name=params['MEMID'].lstrip('\\')
    words={i:f'{name}[{i}]' for i in range(offset,offset+size)}
    if any(type(i) is not int or i not in words for i in kept):
        raise ValueError('keep_words must name valid memory word indices')
    return abstract_words(mapped,ram['top'],words,set(kept))



def native_closed(result):
    statuses=[row.get('status') for row in result.get('rows',[])]
    return result.get('status') in ('pass','inconclusive') and 'pass' in statuses and 'fail' not in statuses


def retry_rtlil(result, ram, directory, timeout):
    """Retain formal cells across the shared abstraction's netlist export."""
    from rvw.formal.portfolio import race
    if timeout <= 0:
        result['rtlil_retry']={'status':'timeout','reason':'RAM phase budget exhausted'}
        return result
    rounds=result.get('rounds',[])
    if not rounds: return result
    report=directory/rounds[-1]['result']
    previous=json.loads(report.read_text())
    if previous.get('reason')!='preparation_failed': return result
    number=len(rounds)-1
    mapped=directory/f'round-{number}.json'
    if not mapped.is_file(): return result
    if ram.get('keep_words'):
        original=json.loads((directory/'mapped.json').read_text())
        collected=json.loads((directory/'collected.json').read_text())
        restored=restore_words(original,collected,ram,ram['keep_words'])
        mapped=directory/f'round-{number}-restored.json'
        mapped.write_text(json.dumps(restored))
        result['watched']=sorted(set(ram['keep_words']))
        result['memory_state_bits']=len(result['watched'])*result['word_width']
    source=directory/f'round-{number}.il'
    with (directory/'rtlil-export.log').open('w') as log:
        process=run_group(['yosys','-Q','-T','-p',f'read_json {mapped.name}; write_rtlil {source.name}'],
                          cwd=directory,stdout=log,stderr=log,timeout=min(timeout,60))
    if process.returncode or process.timed_out:
        result['rtlil_retry']={'status':'error','reason':'RTLIL export failed'}
        return result
    case=dict(top=ram['top'],mode='prove',depth=ram['depth'],engines=ram['engines'],
              sources=[dict(path=source.name,format='rtlil',sha256=hashlib.sha256(source.read_bytes()).hexdigest())])
    native=race(case,directory,directory/'rtlil-retry',timeout=timeout)
    result['rtlil_retry']=native
    result['conditional_native_proof']=native_closed(native)
    result['stop_reason']='abstract_counterexample' if native['status']=='fail' else 'conditional_engine_result'
    # A failure of the cut model is a refinement request, not a core failure.
    result['status']='fail' if native['status']=='fail' and len(result.get('watched',[]))==result.get('words') else 'inconclusive'
    result['limits'] += ' RTLIL retry retains internal formal cells. A cut-model failure requires refinement.'
    return result


def run(cfg, plan, out, *, timeout=120, budget=240):
    from rvw.formal.riscv_proof import capture
    from rvw.formal.lazy_ram import run as lazy_ram
    if plan.get('schema')!='rvw.riscv-abstraction/1':
        raise ValueError('expected rvw.riscv-abstraction/1')
    if any(not math.isfinite(x) or x<=0 for x in (timeout,budget)):
        raise ValueError('timeout and budget must be finite and positive')
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    captured=capture(cfg,out/'capture');rows=[]
    for job in captured['jobs']:
        path=out/'capture'/job['sources'][0]['path']
        source,assumption=restrict(path.read_text(),plan)
        target=out/(job['id']+'-single-flight.sv');target.write_text(source)
        ram=dict(top=job['top'],memory=plan['memory'],engines=plan.get('engines',['abc:pdr']),
                 depth=cfg['depth'],max_words=plan.get('max_words',64),keep_words=plan.get('keep_words',[]),
                 sources=[dict(path=target.name,sha256=hashlib.sha256(target.read_bytes()).hexdigest())])
        try:
            deadline=time.monotonic()+budget
            result=lazy_ram(ram,out,out/job['id'],timeout=timeout,budget=budget)
            result=retry_rtlil(result,ram,out/job['id'],min(timeout,deadline-time.monotonic()))
        except (ValueError,OSError) as exc:
            result=dict(schema='rvw.formal-lazy-ram/1',status='unsupported',error=str(exc))
        (out/job['id']).mkdir(exist_ok=True)
        (out/job['id']/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        try:
            reach=cover(target,job['top'],cfg['depth'],cfg['solver'],out,min(timeout,60))
        except (ValueError,OSError) as exc:
            reach=dict(status='error',error=str(exc))
        rows.append(dict(check=job['id'],concrete_conditional_cover=reach,**result))
    result=dict(schema='rvw.riscv-abstract/1',status='fail' if any(r['status']=='fail' for r in rows) else 'inconclusive',rows=rows,
                restriction=assumption,source_identity=captured['formal_inputs'],
                limits=['Tracked pipeline signals are restricted to one active instruction. This is not a proven invariant.',
                        'Project data must include every relevant one-bit stage observation.',
                        'RAM word abstraction is an overapproximation. Abstract failures need refinement.',
                        'Source reset and bus assumptions remain. Conditional cover does not discharge every assumption.',
                        'Engine success does not establish full-pipeline ISA conformance.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
