#!/usr/bin/env python3
"""Report the fixed coverage batch and one project-declared closure iteration."""
import json
import os
from pathlib import Path
import subprocess

project = Path(__file__).resolve().parent.parent
out = project/'rvw/out'
runs = out/'coverage-runs'
dest = out/'coverage-analysis'
dest.mkdir(exist_ok=True)
rvw = str(Path(os.environ['RVW_HOME'])/'rvw/.venv/bin/rvw')
base = [runs/n for n in ('smoke', 'fence-selfmod', 'illegal')]
isa = sorted(runs.glob('rv32u*-p-*'))
generated = sorted(runs.glob('pmp-*')) + sorted(runs.glob('scheduled-wfi-*')) + sorted(runs.glob('precise-*'))
for name, paths in [('smoke',base), ('isa',base+isa), ('generated',base+isa+generated),
                    ('directed',base+isa+generated+[runs/'protection-speculative',runs/'flush-chain'])]:
    db, report = dest/f'{name}.json', dest/f'{name}-report.json'
    subprocess.run([rvw,'cov','merge',*[f'{p.name}={p/"coverage.dat"}' for p in paths],
                    '--source-root',str(project),'--out',str(db),'--json'], stdout=subprocess.DEVNULL,check=True)
    subprocess.run([rvw,'cov','report',str(db),'--out',str(report),'--json'], stdout=subprocess.DEVNULL,check=True)
    data = json.loads(report.read_text())
    print(json.dumps(dict(epoch=name,programs=len(paths),types=data['types'])),flush=True)

source = (project/'src/main/scala/ooomini/Core.scala').read_text().splitlines()
def line(text):
    return next(i for i,s in enumerate(source,1) if text in s)
areas = {'rename':(line('val allocation ='),line('// Age-ordered selection')),
         'issue queue':(line('// Age-ordered selection'),line('val a = values')),
         'LSQ':(line('val effective ='),line('val shifted =')),
         'ROB commit':(line('io.store :='),line('val recoveryMap =')),
         'recovery':(line('val recoveryMap ='),line('assert(count <='))}
def links(point, area):
    mapping = point.get('scala') or {}
    locations = mapping.get('locations',[mapping])
    low,high = areas[area]
    return any(Path(loc.get('file','')).name == 'Core.scala' and low <= loc.get('line',0) < high for loc in locations)
before = json.loads((dest/'generated.json').read_text())
after = json.loads((dest/'directed.json').read_text())
for area in areas:
    points = [p for p in after['points'] if links(p,area)]
    print(json.dumps(dict(area=area,linked_points=len(points),unhit=sum(not p['count'] for p in points),
                          scope='source navigation links only; incomplete block denominator')),flush=True)
tests = []
for name, selected, priority in [('precise-interrupt',['ROB commit','recovery'],3),
                                 ('protection-speculative',['LSQ','recovery'],2),
                                 ('flush-chain',['ROB commit','LSQ','recovery'],1)]:
    targets = sorted({p['id'] for p in before['points'] if not p['count'] and any(links(p,a) for a in selected)})
    if targets:
        tests.append(dict(id=name,targets=targets,priority=priority,
                          reason='Project candidate for linked control paths; a hit is not predicted.'))
candidates = dest/'candidates.json'
candidates.write_text(json.dumps(dict(schema='rvw.coverage-candidates/1',tests=tests)))
for name in ('generated','directed'):
    subprocess.run([rvw,'cov','closure',str(dest/f'{name}.json'),'--candidates',str(candidates),
                    '--out',str(dest/f'{name}-closure.json'),'--json'],stdout=subprocess.DEVNULL,check=True)
