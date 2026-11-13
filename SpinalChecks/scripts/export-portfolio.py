#!/usr/bin/env python3
"""Normalize selected generated checks for the existing formal engine race."""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib

from rvw.common.proc import run_group


def export(prepared, timeout=30):
    prepared=Path(prepared)
    plan=tomllib.loads((prepared/'regress.toml').read_text())
    rows=[]
    for prop in plan['property']:
        job=prepared/prop['sby']
        text=job.read_text()
        script=text.split('[script]\n',1)[1].split('\n[files]',1)[0]
        script+='\nwrite_rtlil proof.il\n'
        (job.parent/'portfolio.ys').write_text(script)
        result=run_group(['yosys','-Q','-T','-s','portfolio.ys'],cwd=job.parent,
                         capture=True,timeout=timeout)
        (job.parent/'portfolio.log').write_text(result.stdout+result.stderr)
        row=dict(id=prop['id'],requirements=prop.get('requirements',[]),status='inconclusive')
        rows.append(row)
        source=job.parent/'proof.il'
        if result.returncode or result.timed_out or not source.exists():
            row['reason']='normalization failed or timed out'
            continue
        manifest=dict(top=prop['top'],mode='prove',depth=8,
            engines=['smtbmc:yices','smtbmc:z3','abc:pdr'],
            sources=[dict(path='proof.il',format='rtlil',sha256=hashlib.sha256(source.read_bytes()).hexdigest())])
        target=job.parent/'portfolio.json'
        target.write_text(json.dumps(manifest,indent=2)+'\n')
        row.update(status='prepared',manifest=str(target.relative_to(prepared)))
    report=dict(schema='rvw.check-proof-plan/1',checks=rows,
        limitations=['Preparation is not proof. At most three engines are selected per race.',
                     'Keep activation cover observations separate from unbounded safety results.'])
    (prepared/'portfolio-index.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('prepared',type=Path)
    p.add_argument('--timeout',type=float,default=30)
    a=p.parse_args()
    print(json.dumps(export(a.prepared,a.timeout),indent=2))
