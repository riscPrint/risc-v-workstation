"""Export existing Spike oracle plans as bounded execution-unit vectors."""
import json
from pathlib import Path


def export(plans, width, out):
    suffix='s' if width==32 else 'd'
    names={f'{name}.{suffix}':op for op,name in enumerate(('fadd','fmul','fdiv','fsqrt'))}
    names.update({f'fcvt.w.{suffix}':4,f'fcvt.{suffix}.w':5,f'fmadd.{suffix}':6,
                  f'fsub.{suffix}':7,f'fcvt.wu.{suffix}':8,f'fcvt.{suffix}.wu':9})
    if width==64:names.update({f'fcvt.l.{suffix}':10,f'fcvt.{suffix}.l':11,
                              f'fcvt.lu.{suffix}':12,f'fcvt.{suffix}.lu':13,
                              'fcvt.d.s':14,'fcvt.s.d':15})
    rows=[]
    found=set()
    folders=[plans] if isinstance(plans,(str,Path)) else plans
    for path in sorted({p for folder in folders for p in Path(folder).glob('*-plan.json')}):
        data=json.loads(path.read_text())
        if len(data['cases'])!=len(data['expected']):raise ValueError('oracle plan length mismatch')
        for case,expected in zip(data['cases'],data['expected'],strict=True):
            if case['name'] not in names:continue
            op=names[case['name']];found.add(op)
            if case['xlen']!=width or case['width']!=(32 if op==15 else width):raise ValueError('unit profile width mismatch')
            a,b,c=case['operands']
            if op==14:a|=0xffffffff00000000
            rows.append(f'{op} {case["rm"]} {a:x} {b:x} {c:x} {expected["value"] & ((1<<width)-1):x} {expected["flags"]:x}')
    if found!=set(names.values()):raise ValueError('Spike plans do not cover each selected unit operation')
    Path(out).write_text('\n'.join(rows)+'\n')
    return len(rows)
