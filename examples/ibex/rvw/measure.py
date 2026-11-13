"""Regenerate external lint, coverage and declared-bus reports."""
import argparse, json, os, subprocess, sys
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('action',choices=['lint','coverage','checks'])
p.add_argument('--run',type=Path)
a=p.parse_args()
project=Path(__file__).resolve().parent.parent
work=Path(os.environ['IBEX_WORK']).resolve()
base=[sys.executable,'-m','rvw']
def run(*args):
    return subprocess.run([*base,*map(str,args)],check=True)
if a.action=='lint':
    settings=work/'lint-settings.json'
    settings.write_text(json.dumps(dict(schema='rvw.lint-settings/1',config='default',top='ibex_top',db=str(work/'design.db'),backends=['rules','structural'],files=[],waivers=[])))
    with (work/'lint.json').open('w') as f:
        # Findings are expected. A nonzero verdict is not a clean lint result.
        subprocess.run([*base,'lint','--settings',str(settings),'--json'],stdout=f,check=False)
elif a.action=='checks':
    manifest=work/'checks.generate.json'
    manifest.write_text(json.dumps(dict(schema='rvw.check-generation/1',buses=dict(database=str(work/'design.db'),port_map=str(project/'rvw/ports.json')))))
    run('checks','generate','--project',project,'--all','--manifest',manifest,'--out',work/'checks','--json')
else:
    if a.run is None: p.error('coverage needs --run with a regression output directory')
    from rvw.regress.run_evidence import owned_run_paths
    from rvw.results import load_run
    records=[load_run(p) for p in owned_run_paths(a.run)]
    run('cov','merge',*[r.artifact('coverage') for r in records],'--source-root',os.environ['IBEX_SOURCE'],'--out',work/'code-coverage.json','--json')
    run('cov','functional',*[r.artifact('rvfi_trace') for r in records],'--platform',project/'rvw/platform.json','--out',work/'functional.json','--json')
