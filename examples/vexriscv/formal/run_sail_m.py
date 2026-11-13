"""Run the project RV32 M slices with at most three native jobs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re

from rvw.formal.riscv import FIELDS, run as bounded
from rvw.formal.rvfi_binding import generate
from rvw.formal.isa_activation import run as activate
from rvw.common.project import load_project
from rvw.formal.architectural_state import monitor

NAMES=('mul','mulh','mulhsu','mulhu','div','divu','rem','remu')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('rtl','riscv-formal','models','out'): p.add_argument('--'+name,required=True)
    p.add_argument('--timeout',type=float,default=90)
    p.add_argument('--jobs',type=int,choices=(1,2,3),default=3)
    p.add_argument('--checks',default=','.join(NAMES))
    p.add_argument('--mul-depth',type=int,default=20)
    args=p.parse_args()
    selected_names=tuple(args.checks.split(','))
    if not selected_names or set(selected_names)-set(NAMES) or len(set(selected_names))!=len(selected_names):
        raise ValueError('select distinct M instructions')
    if not 2 <= args.mul_depth <= 200:
        raise ValueError('multiply bound must be 2..200')
    rtl=Path(args.rtl).resolve();models=Path(args.models).resolve();out=Path(args.out).resolve()
    manifest=json.loads((models/'manifest.json').read_text())
    if manifest['schema']!='rvw.sail-m/1' or set(manifest['files'])!=set(NAMES):
        raise ValueError('select all eight pinned Sail M models')
    for name in NAMES:
        if hashlib.sha256((models/('insn_'+name+'.v')).read_bytes()).hexdigest()!=manifest['files'][name]['model_sha256']:
            raise ValueError('generated model hash mismatch: '+name)
    out.mkdir(parents=True,exist_ok=False)
    header=rtl.read_text().split('module VexRiscv (',1)[1].split(');',1)[0]
    found=re.findall(r'(input|output)\s+(?:wire|reg)\s+(?:\[(\d+):(\d+)\]\s+)?(\w+)',header)
    if len(found)!=len(re.findall(r'\b(?:input|output)\b',header)):
        raise ValueError('unsupported formal-profile port declaration')
    ports={'inputs':{},'outputs':{}};rvfi_widths=monitor(32)[2]
    for direction,high,low,name in found:
        width=int(high)-int(low)+1 if high else 1
        if name in ('clk','reset'): continue
        if name.startswith('rvfi_'):
            field=name[5:]
            if field not in FIELDS or direction!='output' or width!=rvfi_widths[field]:
                raise ValueError('RVFI interface width/direction mismatch')
            continue
        ports['inputs' if direction=='input' else 'outputs'][name]=width
    options={'insn_'+name+'_ch0':dict(cycles=[args.mul_depth if name.startswith('mul') else 60],engine='abc bmc3') for name in selected_names}
    options['cover']=dict(cycles=[1,20],engine='smtbmc bitwuzla')
    constants={name:0 for name in ports['inputs'] if name in ('timerInterrupt','externalInterrupt','softwareInterrupt','iBus_rsp_payload_error','dBus_rsp_error')}
    plan=dict(schema='rvw.rvfi-binding/1',name='vex-rv32im-sail',top='VexRiscv',clock='clk',reset='reset',
              root=str(Path(args.riscv_formal).resolve()),verilog=[str(rtl)],isa='rv32im',nret=1,depth=60,solver='bitwuzla',
              checks=[*options],check_options=options,ports={f:'rvfi_'+f for f in FIELDS},
              environment_constants=constants,**ports)
    binding=out/'binding.json';binding.write_text(json.dumps(plan,indent=2)+'\n')
    generate(binding,out/'project')
    project=out/'project/rvw.toml'
    project.write_text(project.read_text()+'\n[riscv_formal.instruction_models]\n'+''.join(
        name+' = '+json.dumps(str(models/('insn_'+name+'.v')))+'\n' for name in NAMES))
    cfg=load_project(project).sections['riscv_formal']
    def check(name):
        key='insn_'+name+'_ch0';selected=dict(cfg)
        selected['checks']=[key,'cover']
        selected['check_options']={k:v for k,v in cfg['check_options'].items() if k in selected['checks']}
        directory=out/name
        bounded(selected,directory,args.timeout,'vex-rv32im-sail')
        suite=activate(selected,directory,args.timeout)
        entry=suite['tests'][0]
        status=('failed' if entry['status']=='fail' else 'bounded' if entry['status']=='pass' and not entry.get('inconclusive') else 'inconclusive')
        return dict(check=key,status=status,depth=options[key]['cycles'][-1],native_status=entry['status'],
                    instruction_activation=entry['instruction_activation'],evidence=name+'/results.json')
    with ThreadPoolExecutor(max_workers=args.jobs) as pool: rows=list(pool.map(check,selected_names))
    result=dict(schema='rvw.vex-sail-m/1',status='fail' if any(r['status']=='failed' for r in rows) else 'inconclusive',rows=rows,
                rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
                model_manifest_sha256=hashlib.sha256((models/'manifest.json').read_bytes()).hexdigest(),
                limits=['RV32 M arithmetic slices, not full Sail machine state.',
                        'Interrupts and bus errors are constrained to zero. Other bus inputs are unconstrained.',
                        'Bounds and per-instruction cover do not establish unbounded conformance.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__': main()
