"""Retain Sail M instruction checkers under global multiplication UFs."""
import argparse
import hashlib
import json
from pathlib import Path
from rvw.common.project import load_project
from rvw.formal.riscv_proof import capture
from rvw.formal.uf_prove import prove


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',required=True);p.add_argument('--out',required=True)
    p.add_argument('--timeout',type=float,default=60)
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    cfg=dict(load_project(a.project).sections['riscv_formal'])
    cfg['checks']=['insn_mul_ch0','insn_mulhu_ch0','cover']
    cfg['check_options']={k:v for k,v in cfg.get('check_options',{}).items() if k in cfg['checks']}
    if not {'mul','mulhu'} <= set(cfg.get('instruction_models',{})):
        raise ValueError('select the pinned generated Sail M models')
    captured=capture(cfg,out/'capture');rows=[]
    for job in captured['jobs']:
        plan={**job,'engines':['smtbmc:bitwuzla'],'operators':['bvmul']}
        result=prove(plan,out/'capture',out/job['id'],timeout=a.timeout)
        (out/job['id']/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        rows.append(dict(check=job['id'],**result))
    report=dict(schema='rvw.vex-m-uf/1',rows=rows,source_identity=captured['formal_inputs'],
                limits=['Global typed multiplication UFs overapproximate arithmetic.',
                        'Different operand widths use different UFs. Failure needs arithmetic refinement.',
                        'These checks do not prove multiplier arithmetic or observer conformance.'])
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
