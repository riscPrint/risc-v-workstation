"""Build the exact historical VexTop source with a matched project adapter."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import time
from rvw.common.proc import run_group

HERE=Path(__file__).resolve().parent


def step(argv,log,timeout=90):
    r=run_group(['nice','-n','10',*map(str,argv)],timeout=timeout,capture=True)
    with log.open('a') as stream:stream.write(json.dumps(list(map(str,argv)))+'\n'+r.stdout+r.stderr)
    if r.returncode or r.timed_out:raise ValueError('historical adapter build failed; see '+str(log))


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('action',choices=['run'])
    p.add_argument('--elf',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seed',type=int,default=7);p.add_argument('--config',default='rv32im')
    p.add_argument('--mem-latency',type=int,default=1)
    p.add_argument('--max-cycles',type=int,default=5000);p.add_argument('--rvfi-trace',action='store_true');p.add_argument('--json',action='store_true')
    args=p.parse_args();started=time.monotonic()
    if args.mem_latency!=1 or args.config!='rv32im':raise ValueError('unsupported historical probe configuration')
    args.out=args.out.resolve();build=args.out/'history-build';build.mkdir(parents=True,exist_ok=False)
    settings=json.loads((HERE/'settings.json').read_text())
    source=Path(os.environ['RVW_HISTORY_SOURCE']).resolve()
    top=source/'examples/vexriscv/rvw/src/main/scala/rvwvex/VexTop.scala'
    era=os.environ.get('RVW_HISTORY_ERA','m-only')
    if ('supervisorGen = false' in top.read_text()) != (era=='m-only'):
        raise ValueError('unsupported revision for selected historical adapter era')
    classes=build/'classes';classes.mkdir()
    cp=settings['classpath']
    compiler_cp=os.pathsep.join(settings['compiler_jars'])
    step([settings['java'],'-Xmx2g','-cp',compiler_cp,'scala.tools.nsc.Main','-classpath',cp,
          '-Xplugin:'+settings['plugin'],'-d',classes,top,HERE/'Generate.scala'],build/'build.log')
    step([settings['java'],'-Xmx2g','-cp',str(classes)+os.pathsep+cp,'rvwvex.HistoryGenerate',build/'rtl'],build/'build.log')
    rtl=build/'rtl/VexTop.v'
    header=rtl.read_text().split('module VexTop (',1)[1].split(');',1)[0]
    ports={}
    for direction,first,last,name in re.findall(r'(input|output)\s+(?:wire|reg)\s+(?:\[(\d+):(\d+)\]\s+)?(\w+)',header):
        ports[name]=[direction,int(first)-int(last)+1 if first else 1]
    if 'clk' not in ports or 'rvfi_valid' not in ports:raise ValueError('unsupported historical port interface')
    portfile=build/'ports.json';portfile.write_text(json.dumps(ports))
    spec=importlib.util.spec_from_file_location('historical_engine_probe',HERE/'engine_probe.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    probe=argparse.Namespace(out=args.out/'native-run',rtl=rtl,elf=args.elf,ports=portfile,backend='arcilator',
          seed=args.seed,max_cycles=args.max_cycles,allow_traps=True)
    code=module.run(probe)
    data=json.loads((probe.out/'result.json').read_text())
    data['source']=json.loads(os.environ.get('RVW_CAPTURE_SOURCE',json.dumps(dict(
        core_repo=str(source),core_rev=settings['bad'],core_rev_full=settings['bad'],core_dirty=False))))
    data['wall_s']=time.monotonic()-started
    data['details'].update(history_era=era,historical_source_sha256=hashlib.sha256(top.read_bytes()).hexdigest(),
                           settings_sha256=hashlib.sha256((HERE/'settings.json').read_bytes()).hexdigest())
    data['artifacts']={'rvfi_trace':'native-run/rvfi.jsonl'}
    env={k:os.environ[k] for k in ('RVW_HOME','RVW_CIRCT','RVW_VEX_LOCK') if k in os.environ}
    data['replay']=' '.join(shlex.quote(k+'='+v) for k,v in env.items())+' '+shlex.join([
        str(HERE/'run.sh'),'run','--elf',str(args.elf),'--out',str(args.out),
        '--seed',str(args.seed),'--config','rv32im','--max-cycles',str(args.max_cycles),'--rvfi-trace','--json'])
    (args.out/'result.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data));return code

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps(dict(status='inconclusive',error=str(error))));raise SystemExit(3)
