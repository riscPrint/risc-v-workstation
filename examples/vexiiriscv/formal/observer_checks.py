"""Run short diagnostic instruction checks on the VexiiRiscv observer export."""
import argparse
import json
from pathlib import Path
from rvw.common.project import load_project
from rvw.formal.rvfi_binding import generate
from rvw.formal.riscv import run as bounded
from rvw.formal.isa import run, table


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rtl',required=True);p.add_argument('--riscv-formal',required=True)
    p.add_argument('--out',required=True);p.add_argument('--timeout',type=float,default=20)
    a=p.parse_args();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    plan=json.loads(Path(__file__).with_name('binding.json').read_text())
    plan['name']='vexii-observer-diagnostic'
    plan['verilog']=[str(Path(a.rtl).resolve())];plan['root']=str(Path(a.riscv_formal).resolve())
    checks=['insn_'+name+'_ch0' for name in ('add','lui','beq','lw','sw')]
    plan['checks']=[*checks,'cover']
    plan['check_options']={name:dict(engine='abc bmc3',cycles=[60]) for name in checks}
    plan['check_options']['cover']=dict(engine='smtbmc bitwuzla',cycles=[1,60])
    plan['environment_constants']={name:0 for name in plan['inputs'] if 'int_m_' in name or name.endswith('_error') or name.endswith('_rdtime')}
    (out/'binding.json').write_text(json.dumps(plan,indent=2)+'\n')
    generate(out/'binding.json',out/'project')
    cfg=load_project(out/'project/rvw.toml').sections['riscv_formal']
    small={**cfg,'checks':['insn_add_ch0','cover'],'depth':12,
           'check_options':{'insn_add_ch0':dict(engine='abc bmc3',cycles=[12]),'cover':dict(engine='smtbmc bitwuzla',cycles=[1,60])}}
    bounded(small,out/'small',a.timeout,plan['name'])
    result=run(cfg,out/'isa',a.timeout,plan['name'])
    (out/'table.md').write_text(table(result)+'\n')
    print(table(result))


if __name__=='__main__':main()
