#!/usr/bin/env python3
"""Build the project-selected RV64 families with the existing shared generators."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from rvw.regress.commands.applicability import plan
from rvw.regress import mmu
from rvw.privilege.campaign import build as privilege_build


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--gcc',default='riscv64-unknown-elf-gcc')
    args=parser.parse_args();here=Path(__file__).resolve().parent
    root=Path(os.environ['RVW_HOME']).resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    selection=plan(here/'features.json',here/'catalog.json')
    enabled={r['name'] for r in selection['suites'] if r['applicable']}
    families=[]
    if 'mmu-sv39' in enabled:
        selected=[];excluded=[];target=0
        for row in mmu.load(root/'examples/mmu/matrix.json'):
            if row.get('mode','sv39')!='sv39':continue
            target+=1
            reason=('PMP is absent' if row.get('walk_deny') or 'walk_deny_level' in row else
                    'ASIDLEN is zero' if row.get('asid',0) or row.get('switch_asid') else
                    'hardware A/D updates are absent' if row.get('ad_mode')=='hardware' else
                    'control family uses the privilege generator' if 'control' in row else None)
            if reason:excluded.append(dict(id=row['id'],reason=reason));continue
            selected.append(dict(row,pmp_regions=0))
        source=out/'mmu.json';source.write_text(json.dumps(dict(schema='rvw.mmu/1',scenarios=selected),indent=2)+'\n')
        mmu.build(source,out/'mmu',args.gcc)
        families.append(dict(name='mmu',generated_for_sv39=target,selected=len(selected),excluded=excluded))
    for name,kind,source in [('privilege','controls','controls.json'),('random-privilege','random-transitions','random-transitions.json'),('scheduled','scheduled-wfi','scheduled-wfi.json')]:
        key={'privilege':'privilege-controls','random-privilege':'random-privilege-rv64','scheduled':'scheduled-wfi'}[name]
        if key not in enabled:continue
        description=json.loads((root/'examples/privilege'/source).read_text())
        description.update(isa='rv64ima_zicsr_zifencei',pmp=dict(entries=0))
        if name == 'random-privilege':
            description['random_transitions']['delegatable_causes'] = [0, 3, 8, 9, 12, 13, 15]
        file=out/(name+'.json');file.write_text(json.dumps(description,indent=2)+'\n')
        built=privilege_build(file,out/name,args.gcc)
        families.append(dict(name=name,selected=len(built['scenarios'])))
    names=[name for name in ('lrsc','amo','fence','fence-i') if name+'-rv64' in enabled]
    if names:
        command=[sys.executable,str(root/'RiscvSim/tests/ordering/run.py'),'--out',str(out/'ordering'),'--xlen','64','--seeds','1','--gcc',args.gcc]
        for name in names:command+=['--suite',name]
        subprocess.run(command,check=True)
        families.append(dict(name='ordering',selected=len(names)))
    (out/'selection.json').write_text(json.dumps(dict(plan=selection,families=families,evidence='generation only; no DUT execution'),indent=2)+'\n')
    print(json.dumps(families,indent=2))


if __name__=='__main__':main()
