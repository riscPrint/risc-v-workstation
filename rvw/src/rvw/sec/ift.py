"""Yosys Boolean shadow design and native Verilator policy sampling."""
from collections import deque
import json
from pathlib import Path
import re
import sqlite3
from rvw.formal.security.ift import instrument
from .common import native, publish


def shadow(design, top, policy, mode='precise'):
    if mode not in ('precise', 'conservative'):
        raise ValueError('mode must be precise or conservative')
    mod = design['modules'][top]
    ports = mod['ports']
    clock, reset = policy['clock'], policy['reset']
    for name in (clock, reset, *([policy['declassifier']] if policy.get('declassifier') else [])):
        if name not in ports or ports[name]['direction'] != 'input' or len(ports[name]['bits']) != 1:
            raise ValueError('clock, reset and declassifier must be scalar public inputs')
    if clock == reset:
        raise ValueError('clock must differ from reset')
    if not (policy['sources'] or policy.get('allow_memory_sources')) or not policy['sinks']:
        raise ValueError('nonempty sources and sinks required')
    nets = mod['netnames']
    sources = set()
    for name in policy['sources']:
        if name not in nets or name in (clock, reset, policy.get('declassifier')):
            raise ValueError('source must name a data signal: '+name)
        sources.update(nets[name]['bits'])
    if any(not isinstance(b, int) for b in sources):
        raise ValueError('constant source is not supported')
    if sources & set(ports[clock]['bits']+ports[reset]['bits']):
        raise ValueError('source aliases public controls')
    if policy.get('declassifier') and sources & set(ports[policy['declassifier']]['bits']):
        raise ValueError('declassifier must be public')
    for name in policy['sinks']:
        if name not in nets:
            raise ValueError('unknown sink: '+name)
    live = {b for d in ports.values() for b in d['bits']}
    live.update(b for c in mod['cells'].values() for values in c['connections'].values() for b in values)
    if any(b not in live for name in (*policy['sources'], *policy['sinks']) for b in nets[name]['bits']):
        raise ValueError('source or sink contains unused bits removed by synthesis')
    text = instrument(design, top)
    # The reference transform selects this prefix to avoid port collisions.
    bits = {b for b in live if isinstance(b, int)}
    prefix = ''
    names = {n for p in ports for n in (p, p+'__t')}
    while any(f'{prefix}{k}{b}' in names for k in ('n','t') for b in bits):
        prefix += '_'
    if mode == 'conservative':
        for cell in mod['cells'].values():
            if cell['type'] == '$_DFF_P_':
                continue
            c = cell['connections']
            target = f'{prefix}t{c["Y"][0]}'
            terms = [f'{prefix}t{b}' if isinstance(b,int) else "1'b1" for p in ('A','B','S') for b in c.get(p,[]) if isinstance(b,int) or b in ('x','z')]
            text = re.sub(r'assign '+re.escape(target)+r' = [^;]+;',
                          f'assign {target} = '+(' | '.join(terms) or "1'b0")+';', text)
    # Force taint at declared internal or input sources. Actual values stay intact.
    # Internal register declarations must become wires when the taint driver is replaced.
    for b in sources:
        t = f'{prefix}t{b}'
        text = re.sub(r'assign '+re.escape(t)+r' = [^;]+;', '', text)
        text = re.sub(re.escape(t)+r' <= [^;]+;', '', text)
        text = text.replace(f'reg {prefix}n{b}, {t};', f'reg {prefix}n{b}; wire {t};')
        text = text.replace('endmodule', f"assign {t} = 1'b1;\nendmodule")
    return text, prefix


def path(design, top, sources, sink):
    """Structural candidate path. Dynamic provenance can differ at reconvergence."""
    mod = design['modules'][top]
    adjacency = {}
    for name, cell in mod['cells'].items():
        c = cell['connections']
        output = c['Q' if cell['type'] == '$_DFF_P_' else 'Y']
        for p in ('D',) if cell['type'] == '$_DFF_P_' else ('A','B','S'):
            for a in c.get(p,[]):
                for b in output:
                    adjacency.setdefault(a, []).append((b,name))
    q = deque((b, [name]) for name in sources for b in mod['netnames'][name]['bits'])
    seen = set()
    targets = set(mod['netnames'][sink]['bits'])
    while q:
        b, steps = q.popleft()
        if b in targets:
            return steps+[sink]
        if b not in seen:
            seen.add(b)
            q.extend((dst, steps+[cell]) for dst,cell in adjacency.get(b,[]))
    return []


def database_path(db, source, sink):
    """Resolve a structural path through C6. This is not dynamic taint provenance."""
    from rvw.query.db import run_on, QueryError
    from rvw.query.ops import path as query_path
    try:
        return run_on(db,lambda design: query_path(design,source,sink,max_paths=1))
    except (QueryError, sqlite3.Error, OSError) as e:
        return {'found':False,'inconclusive':str(e)}


def run(rtl, top, policy, stimulus, out, mode='precise', db=None):
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=False)
    policy = json.loads(Path(policy).read_text())
    samples = json.loads(Path(stimulus).read_text())
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', top):
        raise ValueError('simple top identifier required')
    (out/'input.v').write_bytes(Path(rtl).read_bytes())
    native(['yosys','-Q','-p',f'read_verilog -sv input.v; hierarchy -check -top {top}; proc; flatten; memory_map; techmap; simplemap; opt_clean -purge; write_json mapped.json'],out)
    design = json.loads((out/'mapped.json').read_text())
    text, prefix = shadow(design,top,policy,mode)
    (out/'shadow.v').write_text(text)
    ports = design['modules'][top]['ports']
    clock, reset = policy['clock'], policy['reset']
    inputs = {n:len(p['bits']) for n,p in ports.items() if p['direction']=='input' and n != clock}
    if not samples or samples[0].get(reset) != 1 or not any(s.get(reset)==0 for s in samples):
        raise ValueError('stimulus must start with active reset and release reset')
    lines = ['module tb;', 'reg '+clock+'=0;']
    con = [f'.{clock}({clock})']
    for n,p in ports.items():
        if n == clock: continue
        w = len(p['bits'])
        lines += [f'{"reg" if p["direction"]=="input" else "wire"} [{w-1}:0] {n};', f'wire [{w-1}:0] {n}__t;']
        con += [f'.{n}({n})', f'.{n}__t('+ (f"{w}'d0" if p['direction']=='input' else n+'__t')+')']
    lines += [f'{top}__ift dut('+','.join(con)+');','initial begin']
    checked_cycles=0
    for cycle,sample in enumerate(samples):
        if set(sample) != set(inputs) or any(type(v) is not int or not 0<=v<1<<inputs[n] for n,v in sample.items()):
            raise ValueError('each sample must bind every non-clock input within its width')
        lines += [f'{clock}=0;']+[f"{n}={inputs[n]}'d{v};" for n,v in sample.items()]+[f'#1; {clock}=1; #1;']
        if sample[reset] == 0 and not sample.get(policy.get('declassifier'),0):
            checked_cycles+=1
            for index,sink in enumerate(policy['sinks']):
                ts = [f'dut.{prefix}t{b}' if isinstance(b,int) else ("1'b1" if b in ('x','z') else "1'b0") for b in design['modules'][top]['netnames'][sink]['bits']]
                lines.append(f'if ({" | ".join(ts)}) $display("SEC {cycle} {index}");')
    lines += ['$display("SEC_END"); $finish; end endmodule']
    (out/'tb.sv').write_text('\n'.join(lines))
    native(['verilator','--binary','--build-jobs','2','-CFLAGS','-O0','--timing','-Wno-fatal','--top-module','tb','shadow.v','tb.sv'],out)
    log = native([str(out/'obj_dir/Vtb')],out)
    (out/'simulation.log').write_text(log)
    findings = []
    db_paths = set()
    if db:
        with sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True) as conn:
            db_paths = {r[0] for r in conn.execute('select path from signals')}
    database_cache={}
    for cycle,index in re.findall(r'^SEC (\d+) (\d+)$',log,re.M):
        sink = policy['sinks'][int(index)]
        steps = path(design,top,policy['sources'],sink)
        if db and sink not in database_cache:
            database_cache[sink]={source:database_path(db,source,sink) for source in policy['sources']}
        findings.append(dict(database_dependency_paths=database_cache.get(sink,{}),cycle=int(cycle), sink=sink, candidate_path=steps,
                             database_paths=[p for p in db_paths if p in steps or p.split('.')[-1] in steps]))
    return publish(out,'ift',findings,'SEC_END' in log and checked_cycles>0,mode=mode,policy=policy,checked_cycles=checked_cycles,
                   unknown_constants='x/z represent either Boolean value with taint set; no electrical high-impedance model',path_kind='structural candidate, not dynamic provenance',samples=len(samples))
