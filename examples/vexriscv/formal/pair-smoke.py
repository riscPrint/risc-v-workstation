#!/usr/bin/env python3
"""Run bounded two-copy controls on a supplied VexTop RTL export."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--depth',type=int,default=8)
    p.add_argument('--timeout',type=float,default=90)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[3]
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    raw=a.rtl.read_bytes();(out/'VexTop.v').write_bytes(raw)
    def execute(command,log,timeout):
        command=[str(root/'scripts/with-lock.sh'),'vex-equiv','nice','-n','10',*command]
        from rvw.common.proc import run_group
        result=run_group(command,cwd=out,timeout=timeout,capture=True)
        (out/log).write_text((result.stdout or '')+(result.stderr or ''))
        return result
    (out/'ports.ys').write_text('read_verilog VexTop.v\nhierarchy -check -top VexTop\nproc\nflatten\nwrite_json ports.json\n')
    result=execute(['yosys','-Q','-s','ports.ys'],'ports.log',a.timeout)
    if result.returncode:
        raise SystemExit('port capture failed; see ports.log')
    mod=json.loads((out/'ports.json').read_text())['modules']['VexTop']
    ports={n:{'direction':r['direction'],'width':len(r['bits'])} for n,r in mod['ports'].items()}
    common={'schema':'rvw.security-pair/1','rtl':'VexTop.v','top':'VexTop','clock':'clk','reset':'reset',
            'mode':'bmc','depth':a.depth,'ports':ports,
            'adversary':'controls shared instruction and bus responses; no bus protocol assumptions',
            'unmodeled_channels':['analog','power','debug','DMA','CSR secret injection','region-specific memory secrecy']}
    cases={
      'memory-observation':dict(common,kind='noninterference',secrets=['dBus_rsp_data'],
          architectural=['rvfi_pc_rdata','rvfi_rd_wdata'],observations=['iBus_cmd_valid','dBus_cmd_valid']),
      'initialization':dict(common,kind='initialization',secrets=[],architectural=[],
          observations=['iBus_cmd_valid','iBus_cmd_payload_pc','dBus_cmd_valid'])}
    summary={'rtl_sha256':hashlib.sha256(raw).hexdigest(), 'fresh_elaboration':False,
             'scope':'supplied real core RTL export; no source revision certification', 'cases':[]}
    for name,plan in cases.items():
        manifest=out/(name+'.json');manifest.write_text(json.dumps(plan,indent=2)+'\n')
        proof=out/name
        result=execute([str(root/'rvw/.venv/bin/rvw'),'formal','security','pair',
                        '--manifest',str(manifest),'--out',str(proof),'--timeout',str(a.timeout)],name+'.log',a.timeout+10)
        record=json.loads((proof/'result.json').read_text()) if (proof/'result.json').exists() else {}
        summary['cases'].append({'name':name,'status':record.get('status','inconclusive'),
            'proof_kind':record.get('proof_kind'),'depth':record.get('depth'),
            'reason':record.get('reason'),'exit':result.returncode})
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    policy={'clock':'clk','reset':'reset','sources':['dBus_rsp_data'],
            'sinks':['iBus_cmd_valid','dBus_cmd_valid'], 'kind':'secure_path',
            'adversary':common['adversary'],'unmodeled_channels':common['unmodeled_channels']}
    (out/'ift-policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    result=execute([str(root/'rvw/.venv/bin/rvw'),'formal','security','prove',
                    '--rtl',str(out/'VexTop.v'),'--top','VexTop','--policy',str(out/'ift-policy.json'),
                    '--out',str(out/'ift'),'--timeout',str(a.timeout)],'ift.log',a.timeout+10)
    record=json.loads((out/'ift/result.json').read_text()) if (out/'ift/result.json').exists() else {}
    summary['cases'].append({'name':'ift','status':record.get('status','inconclusive'),
                            'reason':record.get('reason'),'exit':result.returncode})
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
