"""Build the formal profile with a supplied pinned Spinal compiler classpath."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from rvw.common.proc import run_group

PIN='baf7dc82f855eddaf5b0a20a6802c526f127e38a'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','classpath','plugin','out'): p.add_argument('--'+name,required=True)
    args=p.parse_args()
    source=Path(args.source).resolve();out=Path(args.out).resolve()
    revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if revision!=PIN or subprocess.check_output(['git','-C',str(source),'status','--porcelain','--','src/main/scala'],text=True):
        raise ValueError('select the clean pinned VexRiscv source')
    out.mkdir(parents=True,exist_ok=False);classes=out/'classes';classes.mkdir()
    cp=Path(args.classpath).read_text().strip();plugin=Path(args.plugin).resolve()
    top=Path(__file__).resolve().parents[1]/'rvw/src/main/scala/FormalMTop.scala'
    sources=sorted((source/'src/main/scala').rglob('*.scala'))
    (out/'FormalMTop.scala').write_bytes(top.read_bytes())
    with (out/'compile.log').open('w') as log:
        result=run_group(['java','-Xmx3g','-cp',cp,'scala.tools.nsc.Main','-classpath',cp,
                          '-language:reflectiveCalls','-Xplugin:'+str(plugin),'-d',str(classes),
                          *[str(s) for s in sources],str(out/'FormalMTop.scala')],stdout=log,stderr=log,timeout=240)
    if result.returncode or result.timed_out: raise SystemExit('formal-profile compile failed; see compile.log')
    with (out/'elaborate.log').open('w') as log:
        result=run_group(['java','-Xmx3g','-Xss64m','-cp',str(classes)+':'+cp,'FormalMTop',str(out/'rtl')],stdout=log,stderr=log,timeout=120)
    if result.returncode or result.timed_out: raise SystemExit('formal-profile elaboration failed; see elaborate.log')
    report=dict(status='generated',source_revision=revision,config_sha256=hashlib.sha256(top.read_bytes()).hexdigest(),
                plugin_sha256=hashlib.sha256(plugin.read_bytes()).hexdigest(),
                rtl_sha256=hashlib.sha256((out/'rtl/VexRiscv.v').read_bytes()).hexdigest(),
                limits=['Compiler classpath is supplied by the caller. Record its Spinal revision.', 'Generation grants no proof.'])
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
