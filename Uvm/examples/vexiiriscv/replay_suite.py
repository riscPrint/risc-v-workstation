"""Check each complete native Vexii ISA capture in the pyuvm CPU environment."""
import argparse
import json
import os
from pathlib import Path
from rvw.sim.cocotb import run


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--jobs',type=Path,required=True)
    p.add_argument('--shim',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    jobs=json.loads(a.jobs.read_text())
    if not jobs or len({j['elf'] for j in jobs})!=len(jobs):raise ValueError('unique native jobs required')
    os.environ['RVW_CPU_CAPTURE_JOBS']=str(a.jobs.resolve())
    os.environ['RVW_CPU_SHIM']=str(a.shim.resolve())
    here=Path(__file__).resolve().parent
    result=run(here/'replay-bench.json',out/'run',timeout=600)
    summaries={p.name.removeprefix('cpu-checks-').removesuffix('.json'):json.loads(p.read_text())
               for p in (out/'run').rglob('cpu-checks-*.json')}
    rows=[]
    for job in jobs:
        name=Path(job['elf']).name
        native=Path(job['out'])/'result.json'
        status=json.loads(native.read_text())['status'] if native.exists() else 'missing'
        rows.append(dict(program=name,native_status=status,
            pyuvm_status='checked' if name in summaries else 'not established',**summaries.get(name,{})))
    report=dict(mode='offline-native-c2-pyuvm',programs=rows,selected=len(rows),checked=len(summaries),
        c3=str(out/'run/results.json'),failures=[r for r in result['tests'] if r['status']!='pass'])
    (out/'isa-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(selected=len(rows),checked=len(summaries),failures=len(report['failures']))))
    if len(summaries)!=len(rows) or report['failures']:raise SystemExit(1)


if __name__=='__main__':main()
