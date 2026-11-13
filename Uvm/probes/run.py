"""Small measured engine probes. A compile refusal is a profile gap, not a pass."""
import argparse
import json
from pathlib import Path
from rvw.common.proc import run_group


def run(out, verilator='verilator'):
    out = Path(out).resolve()
    out.mkdir(parents=True,exist_ok=False)
    version = run_group([verilator,'--version'],capture=True,timeout=10)
    rows = []
    for name in ('randc','transition'):
        directory = out/name
        directory.mkdir()
        cmd = [verilator,'--binary','--timing','--coverage','--assert','-Wno-fatal','-j','2',
               '--top-module','top','--Mdir',str(directory/'obj'),
               str(Path(__file__).parent/(name+'.sv'))]
        built = run_group(cmd,capture=True,timeout=60)
        (directory/'build.log').write_text(built.stdout+built.stderr)
        row = dict(feature=name,command=cmd)
        if built.timed_out:
            row['status']='inconclusive'
        elif built.returncode:
            row['status']='compile_refused'
        else:
            result = run_group([str(directory/'obj/Vtop')],capture=True,timeout=10,cwd=directory)
            (directory/'run.log').write_text(result.stdout+result.stderr)
            row['status'] = ('inconclusive' if result.timed_out else
                'checked' if result.returncode==0 and result.stdout.count('RVW_PROBE_DONE')==1 else 'runtime_gap')
        if '%Warning-COVERIGN' in built.stdout+built.stderr:
            row['ignored_feature_warning'] = True
            if row['status'] == 'checked':
                row['status'] = 'ignored_feature'
        rows.append(row)
    report = dict(engine=version.stdout.strip(),probes=rows)
    (out/'probes.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--verilator',default='verilator')
    args=parser.parse_args()
    print(json.dumps(run(args.out,args.verilator)))
