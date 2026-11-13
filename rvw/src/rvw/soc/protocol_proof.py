"""Run a small bounded protocol proof on the actual composed fabric."""
import json
import sys
from pathlib import Path
from rvw.common.proc import run_group
from .model import load


def prove(source, out, classpath, timeout=30):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    windows = [f"{r['base']:x}:{r['size']:x}" for r in load(source)['regions']]
    command = ['nice','-n','10','java','-cp',classpath,'rvwsoc.FabricProtocolProofGenerate',str(out/'rtl'),*windows]
    with (out/'generate.log').open('w') as log:
        build = run_group(command,cwd=out,stdout=log,stderr=log,timeout=timeout)
    if build.returncode or build.timed_out:
        return dict(status='inconclusive',reason='Protocol target generation failed; see generate.log.')
    command = [sys.executable,'-m','rvw','formal','bmc','--verilog',str(out/'rtl/FabricProtocolProof.v'),
               '--top','FabricProtocolProof','--clock','clk','--reset','reset','--depth','8',
               '--engine','smtbmc:yices','--timeout',str(timeout),'--out',str(out/'proof'),'--json']
    with (out/'prove.log').open('w') as log:
        process = run_group(command,cwd=out,stdout=log,stderr=log,timeout=timeout+10)
    path = out/'proof/result.json'
    report = json.loads(path.read_text()) if path.is_file() else {}
    valid = not process.timed_out and report.get('assertions',0)>=5*len(windows)+6 and report.get('proof_kind')=='bounded'
    status = 'pass' if valid and process.returncode==0 and report.get('status')=='pass' else (
        'fail' if valid and report.get('status')=='fail' else 'inconclusive')
    return dict(status=status,checks=report.get('assertions',0),depth=8,
                scope='Bounded APB fabric protocol safety with legal master assumptions; CPU ingress and device state are outside this proof.',formal_result=str(path))
