#!/usr/bin/env python3
"""Expose project PMP observations without cuts, then run bounded isolation."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from rvw.common.proc import run_group


def expose(design,binding):
    module=copy.deepcopy(design['modules'][binding['source_top']])
    for alias,name in binding['signals'].items():
        if alias in module['ports'] or name not in module['netnames']:
            raise ValueError('observation binding is missing or collides: '+name)
        module['ports'][alias]=dict(direction='output',bits=list(module['netnames'][name]['bits']))
    for alias,(width,value) in binding['constants'].items():
        if alias in module['ports'] or not 0<=value<1<<width:raise ValueError('constant observation collision or range')
        module['ports'][alias]=dict(direction='output',bits=[str((value>>i)&1) for i in range(width)])
    return {'modules':{binding['observation_top']:module}}


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--timeout',type=float,default=60)
    p.add_argument('--depth',type=int,default=8)
    a=p.parse_args()
    if not 0<a.timeout<=120 or not 1<=a.depth<=32:p.error('timeout must be 0..120 seconds; depth must be 1..32')
    root=Path(__file__).resolve().parents[3];here=Path(__file__).resolve().parent
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    binding=json.loads((here/'pmp-isolation-binding.json').read_text())
    def execute(cmd,log,timeout):
        r=run_group([str(root/'scripts/with-lock.sh'),'vex-equiv','nice','-n','10',*cmd],cwd=out,timeout=timeout,capture=True)
        (out/log).write_text((r.stdout or '')+(r.stderr or ''));return r
    raw=a.rtl.read_bytes();(out/'core.v').write_bytes(raw)
    (out/'map.ys').write_text('read_verilog core.v\nhierarchy -check -top VexTop\nproc\nflatten\ncheck -assert\nwrite_json original.json\n')
    r=execute(['yosys','-Q','-s','map.ys'],'map.log',min(a.timeout,120))
    if r.returncode:return 3
    design=json.loads((out/'original.json').read_text());observed=expose(design,binding)
    # Keep every original cell. Only new output aliases and constant outputs are added.
    (out/'observed.json').write_text(json.dumps(observed))
    (out/'export.ys').write_text('read_json observed.json\ncheck -assert\nwrite_verilog -noattr observed.v\n')
    r=execute(['yosys','-Q','-s','export.ys'],'export.log',min(a.timeout,120))
    if r.returncode:return 3
    policy=json.loads((here/'pmp-isolation-policy.json').read_text());policy['depth']=a.depth;(out/'policy.json').write_text(json.dumps(policy))
    r=execute([str(root/'rvw/.venv/bin/rvw'),'formal','security','prove','--rtl',str(out/'observed.v'),
               '--top',binding['observation_top'],'--policy',str(out/'policy.json'),'--out',str(out/'proof'),
               '--timeout',str(a.timeout)],'proof.log',a.timeout+5)
    result=json.loads((out/'proof/result.json').read_text()) if (out/'proof/result.json').exists() else {'status':'inconclusive'}
    summary=dict(schema='rvw.vex-pmp-observation/1',rtl_sha256=hashlib.sha256(raw).hexdigest(),
                 status=result['status'],depth=policy['depth'],reason=result.get('reason'),
                 scope=f'actual emitted data-command starting-byte isolation at depth {a.depth}; no cuts; not CSR-configured PMP qualification')
    secure=out/'proof/secure.v'
    if secure.exists():
        # A separate negated reach predicate checks attempted access before
        # PMP permission filtering. It does not reuse emitted grant as a cover.
        text=secure.read_text();at=text.rfind('always @(posedge')
        if at<0:raise ValueError('isolation monitor boundary changed')
        text=text[:at]+"always @(posedge clk) if(!reset) assert(!(obs_attempt && obs_privilege==0 && obs_virtual_address>=32'h80008000 && obs_virtual_address<32'h80008100));\nendmodule\n"
        (out/'reach.v').write_text(text)
        r=execute([str(root/'rvw/.venv/bin/rvw'),'formal','bmc','--verilog',str(out/'reach.v'),'--top','rvw_secure_path',
                   '--clock','clk','--reset','reset','--depth',str(a.depth),'--engine','smtbmc:yices','--timeout',str(a.timeout),
                   '--out',str(out/'reach'),'--json'],'reach.log',a.timeout+5)
        coverage=json.loads((out/'reach/result.json').read_text()) if (out/'reach/result.json').exists() else {}
        status={'fail':'reached','pass':'not_reached_within_bound'}.get(coverage.get('status'),'inconclusive')
        summary['user_keystore_reach']=dict(status=status,depth=a.depth,
            cycles=[f.get('cycle') for f in coverage.get('failures',[])],backend_status=coverage.get('status'),
            wall_s=coverage.get('wall_s'),reason=coverage.get('reason') or ('reachability time limit' if coverage.get('status')=='timeout' else None))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
    return 0 if result['status']=='pass' else 3


if __name__=='__main__':raise SystemExit(main())
