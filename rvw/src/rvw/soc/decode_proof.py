"""Prove the real SpinalSoc fabric for the selected map windows."""
import json
import sys
from pathlib import Path
from rvw.common.proc import run_group
from .model import load


def prove(source, out, classpath, timeout=60):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    model = load(source)
    windows = [f"{r['base']:x}:{r['size']:x}" for r in model['regions']]
    command = ['nice','-n','10','java','-cp',classpath,'rvwsoc.FabricProofGenerate',str(out/'rtl'),*windows]
    with (out/'generate.log').open('w') as log:
        generated = run_group(command,cwd=out,stdout=log,stderr=log,timeout=timeout)
    if generated.returncode or generated.timed_out:
        return dict(status='inconclusive', generated=False, reason='Fabric RTL generation failed; see generate.log.')
    command = [sys.executable,'-m','rvw','formal','prove','--verilog',str(out/'rtl/FabricProof.v'),
               '--top','FabricProof','--clock','clk','--reset','reset','--depth','4',
               '--engine','smtbmc:yices','--timeout',str(timeout),'--out',str(out/'proof'),'--json']
    with (out/'prove.log').open('w') as log:
        executed = run_group(command,cwd=out,stdout=log,stderr=log,timeout=timeout+10)
    path = out/'proof/result.json'
    report = json.loads(path.read_text()) if path.is_file() else {}
    assertions = report.get('assertions',0)
    required = len(windows)+2
    status = 'inconclusive'
    if not executed.timed_out and assertions >= required and report.get('proof_kind') == 'unbounded':
        if executed.returncode == 0 and report.get('status') == 'pass':
            status = 'proven'
        elif report.get('status') == 'fail':
            status = 'fail'
    result = dict(status=status,generated=True,ran=True,assertions=assertions,
                  expected_assertions=required,formal_result=str(path),command=command,
                  scope='unbounded decode proof of a Fabric.connect instance with the selected windows; no core or peripheral state',
                  limitations=['No ingress protocol, register behavior, IRQ wiring or clock crossings are covered.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
