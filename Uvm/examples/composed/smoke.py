"""Native composed-SoC scenarios with staged Spinal memory images."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from cocotb_tools.runner import get_runner
from rvw.sim.cocotb import entries


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    here=Path(__file__).resolve().parent
    rtl=here/'rtl/ScenarioSoc.v'
    runner=get_runner('verilator')
    # WordMemory shifts a 14-bit byte address into a 12-bit word index.
    # The discarded upper two bits are zero. Keep all other warnings fatal.
    runner.build(sources=[rtl],hdl_toplevel='ScenarioSoc',build_dir=out/'build',
        build_args=['--assert','-j','2','-Wno-WIDTHTRUNC'],timescale=('1ns','1ps'))
    run=out/'run';run.mkdir()
    for image in (here/'rtl').glob('*.bin'):shutil.copyfile(image,run/image.name)
    sys.path.insert(0,str(here))
    os.environ.pop('PYTEST_CURRENT_TEST',None)
    runner.test(hdl_toplevel='ScenarioSoc',test_module='scenario_test',test_dir=run,seed=1,
        results_xml=str(run/'results.xml'))
    rows=entries(run/'results.xml',1)
    assert len(rows)==2 and all(r['status']=='pass' for r in rows),rows
    assert all((run/f'scenarios-{seed}.json').exists() for seed in (1,7)), 'missing checked scenario summaries'
    (out/'results.json').write_text(json.dumps(dict(tests=rows,rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256((here/'scenario_test.py').read_bytes()).hexdigest(),
        scenarios={str(seed):json.loads((run/f'scenarios-{seed}.json').read_text()) for seed in (1,7)}),indent=2)+'\n')


if __name__=='__main__':main()
