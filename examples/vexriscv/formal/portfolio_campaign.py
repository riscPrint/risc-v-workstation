"""Attempt every selected instruction with the declared pipeline and RAM cuts."""
import argparse
import json
from pathlib import Path
from rvw.common.project import load_project
from rvw.formal.riscv_abstract import run
from rvw.formal.instruction_attempts import summarize


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',default='examples/vexriscv/formal')
    p.add_argument('--manifest',default='examples/vexriscv/formal/abstract.json')
    p.add_argument('--out',required=True)
    p.add_argument('--timeout',type=float,default=20)
    p.add_argument('--budget',type=float,default=50)
    p.add_argument('--checks')
    a=p.parse_args();cfg=dict(load_project(a.project).sections['riscv_formal'])
    plan=json.loads(Path(a.manifest).read_text());plan['engines']=['abc:pdr','smtbmc:bitwuzla']
    names=[k for k in cfg['checks'] if k.startswith('insn_')]
    if a.checks:
        selected=a.checks.split(',')
        if set(selected)-set(names): raise ValueError('unknown selected instruction')
        names=selected
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False);rows=[]
    for name in names:
        selected={**cfg,'checks':[name,'cover']}
        selected['check_options']={k:v for k,v in cfg.get('check_options',{}).items() if k in selected['checks']}
        try:
            result=run(selected,plan,out/name,timeout=a.timeout,budget=a.budget)
            row=result['rows'][0]
            entry=dict(check=name,**summarize(row),evidence=name+'/result.json')
        except (OSError,ValueError) as exc:
            entry=dict(check=name,status='inconclusive',reason=str(exc),conditional_native_proof=False)
        rows.append(entry)
        report=dict(schema='rvw.vex-instruction-portfolio/1',rows=rows,engines=plan['engines'],
                    timeout_s=a.timeout,budget_s=a.budget,abstraction=plan,
                    limits=['Single-flight is a restriction, not a proven invariant.',
                            'Regfile word zero is retained. Other words are overapproximated.',
                            'Conditional native proof does not certify full pipeline or observer.'])
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(entry),flush=True)


if __name__=='__main__':main()
