"""Project C1 adapter for bounded instruction and IRQ reduction fixtures."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
from rvw.common.proc import run_group

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['run'])
    p.add_argument('--elf',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seed',type=int,default=7);p.add_argument('--config',default='rv32im')
    p.add_argument('--max-cycles',type=int,default=5000);p.add_argument('--mem-latency',type=int,default=1)
    p.add_argument('--rvfi-trace',action='store_true');p.add_argument('--json',action='store_true');p.add_argument('--irq-schedule')
    args=p.parse_args()
    if args.config!='rv32im' or args.mem_latency!=1:raise ValueError('unsupported reduction fixture configuration')
    spec=importlib.util.spec_from_file_location('reduction_engine_probe',HERE/'engine_probe.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    args.out=args.out.resolve();args.out.mkdir(parents=True,exist_ok=True)
    probe=argparse.Namespace(out=args.out/'native-run',rtl=HERE/'VexTop.v',ports=HERE/'engine-ports.json',elf=args.elf,
        backend='arcilator',seed=args.seed,max_cycles=args.max_cycles,allow_traps=bool(args.irq_schedule),irq_schedule=args.irq_schedule)
    code=module.run(probe)
    data=json.loads((probe.out/'result.json').read_text())
    data['artifacts']={'rvfi_trace':'native-run/rvfi.jsonl'}
    if os.environ.get('RVW_CAPTURE_SOURCE'):source=json.loads(os.environ['RVW_CAPTURE_SOURCE'])
    else:
        root=Path(os.environ['VEXRISCV']).resolve(strict=True)
        result=run_group(['git','-C',str(root),'rev-parse','HEAD'],timeout=10,capture=True)
        dirty=run_group(['git','-C',str(root),'status','--porcelain'],timeout=10,capture=True)
        if result.returncode or dirty.returncode:raise ValueError('private VexRiscv source identity is unavailable')
        source=dict(core_repo=str(root),core_rev=result.stdout.strip(),core_rev_full=result.stdout.strip(),core_dirty=bool(dirty.stdout.strip()))
    data['source']=source
    env={key:os.environ[key] for key in ('RVW_HOME','RVW_CIRCT','RVW_VEX_LOCK','VEXRISCV') if key in os.environ}
    argv=[str(HERE/'run.sh'),'run','--elf',str(args.elf),'--out',str(args.out),'--seed',str(args.seed),
          '--config',args.config,'--max-cycles',str(args.max_cycles),'--mem-latency','1','--rvfi-trace','--json']
    if args.irq_schedule:argv+=['--irq-schedule',args.irq_schedule]
    data['replay']=' '.join(shlex.quote(k+'='+v) for k,v in env.items())+' '+shlex.join(argv)
    (args.out/'result.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(dict(status=data['status'],cycles=data['cycles'],instret=data['instret'])));return code

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps(dict(status='inconclusive',error=str(error))));raise SystemExit(3)
