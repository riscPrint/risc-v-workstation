"""Partial compiler scheduling exports from the shared project description."""
from hashlib import sha256
import json
from pathlib import Path
import re
from rvw.ooo.project import configuration
from .sched import render

MAP = {'alu':('arith',['ADD','ADDI','SUB','AND','OR','XOR']),
       'multiply':('imul',['MUL','MULH','MULHSU','MULHU']),
       'divide':('idiv',['DIV','DIVU','REM','REMU']),
       'load':('load',['LB','LBU','LH','LHU','LW','LWU','LD']),
       'store':('store',['SB','SH','SW','SD'])}


def parse(td, md):
    width=re.search(r'let IssueWidth = (\d+);',td)
    window=re.search(r'let MicroOpBufferSize = (\d+);',td)
    if not width or not window:
        raise ValueError('missing compiler widths')
    resources={k:int(v) for k,v in re.findall(r'\w+Res(\w+) : ProcResource<(\d+)>;',td)}
    writes={k:(res,int(lat),int(occ)) for k,res,lat,occ in re.findall(
        r'\w+Write(\w+) : SchedWriteRes<\[\w+Res(\w+)\]> \{\s*let Latency = (\d+);\s*let ReleaseAtCycles = \[(\d+)\];',td)}
    reservations={name:(int(lat),units) for name,lat,units in re.findall(
        r'\(define_insn_reservation "([^"]+)" (\d+)\s*\(eq_attr "type" "[^"]+"\) "([^"]+)"\)',md)}
    return dict(issue_width=int(width[1]),window=int(window[1]),resources=resources,writes=writes,reservations=reservations)


def check(directory):
    p=Path(directory)
    d=json.loads((p/'scheduling.json').read_text())
    parsed=parse((p/'model.td').read_text(),(p/'model.md').read_text())
    if parsed['issue_width'] != d['issue_width'] or parsed['window'] != d['buffer_size'] or parsed['resources'] != d['resources']:
        raise ValueError('compiler width, window or resource mismatch')
    if set(parsed['writes']) != {c['name'] for c in d['classes']}:
        raise ValueError('compiler class mismatch')
    for c in d['classes']:
        if parsed['writes'][c['name']] != (c['resource'],c['latency'],c['occupancy']):
            raise ValueError('compiler latency or occupancy mismatch')
    # After parsing numeric fields, check the full restricted syntax too. This
    # covers opcode mappings, GCC resource expressions and issue reservations.
    td,md=render(d)
    if (p/'model.td').read_text()!=td or (p/'model.md').read_text()!=md:
        raise ValueError('compiler mapping or reservation mismatch')
    if f'#define RVW_ISSUE_RATE {d["issue_width"]}\n' not in (p/'tune.h').read_text():
        raise ValueError('GCC issue-rate include mismatch')
    return dict(schema='rvw.compiler-roundtrip/1',status='reported',parsed=parsed,
                limits=['restricted generated syntax only; no TableGen or GCC build'])


def export(description, out):
    raw=Path(description).read_bytes(); shared=json.loads(raw)
    if shared.get('schema')!='rvw.arch-core/1':
        raise ValueError('shared project description required')
    c=configuration(shared)
    name='Core_'+re.sub('[^A-Za-z0-9_]','_',shared['config'])
    classes=[];resources={}
    for kind,(gcc,ops) in MAP.items():
        if kind not in c.latencies:
            continue
        resources[kind]=c.ports.get(kind,1)
        classes.append(dict(name=kind,resource=kind,latency=c.latencies[kind],occupancy=1,
                            llvm_opcodes=ops,gcc_type=gcc))
    d=dict(name=name,issue_width=c.issue_width,buffer_size=c.rob_entries,
           resources=resources,classes=classes)
    p=Path(out);p.mkdir(parents=True,exist_ok=False)
    td,md=render(d)
    (p/'model.td').write_text(td);(p/'model.md').write_text(md)
    (p/'scheduling.json').write_text(json.dumps(d,indent=2)+'\n')
    (p/'tune.h').write_text(f'/* Partial target include. Select this CPU explicitly. */\n#define RVW_ISSUE_RATE {c.issue_width}\n')
    result=check(p)
    result.update(description_sha256=sha256(raw).hexdigest(),
                  unsupported_classes=sorted(set(c.latencies)-set(MAP)),
                  assumptions=['independent class resources; unspecified class count is one',
                               'occupancy is one; execution port sharing is not projected',
                               'integer base opcodes only; compressed, FP and vector mappings absent',
                               'CPU registration and GCC target hooks require compiler integration'])
    (p/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
