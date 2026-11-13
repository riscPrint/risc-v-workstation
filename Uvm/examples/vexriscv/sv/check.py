"""Require positive program completion and an independent PC fault control."""
import argparse
import json
from pathlib import Path
from rvw.common.proc import run_group
from rvw.uvm.flow import regress


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    report=regress(a.build,out/'good',seeds=[1,3])
    assert len(report['tests'])==2 and all(r['status']=='pass' for r in report['tests']),report
    built=json.loads((a.build/'build.json').read_text())
    command=[str(a.build/'obj/simulation'),*built['manifest']['plusargs'],'+corrupt']
    with (out/'corrupt.log').open('w') as log:
        result=run_group(command,cwd=out,stdout=log,stderr=log,timeout=120)
    text=(out/'corrupt.log').read_text()
    assert not result.timed_out and result.returncode!=0 and '[SPIKE_MISMATCH]' in text and 'pc_next actual=' in text and 'RVW_UVM_DONE' not in text,text
    (out/'qualification.json').write_text(json.dumps(dict(good_tests=report['tests'],
        corrupt_pc_detected=True,negative_command=command,binary_sha256=built['binary_sha256'],
        native_dependency_sha256=built['native_dependency_sha256']),indent=2)+'\n')
    print('VexRiscv SV: two checked program runs and one PC-corruption control')


if __name__=='__main__':main()
