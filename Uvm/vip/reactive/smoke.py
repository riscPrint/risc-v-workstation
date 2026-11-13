"""Qualify Python reactive roles against small RTL managers with Icarus."""
import argparse
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET
from cocotb_tools.runner import get_runner


def main():
    p=argparse.ArgumentParser();p.add_argument('--protocol',choices=['apb','ahb'],required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);src=Path(__file__).resolve().parent
    start=time.monotonic();runner=get_runner('icarus');top=a.protocol+'_manager'
    runner.build(sources=[src/(top+'.sv')],hdl_toplevel=top,build_dir=out/'build')
    os.environ['PYTHONPATH']=str(src)+os.pathsep+os.environ.get('PYTHONPATH','')
    for bad in (0,1):
        run=out/str(bad);run.mkdir()
        runner.test(hdl_toplevel=top,test_module='reactive_test',test_dir=run,seed=17,
            extra_env={'VIP_PROTOCOL':a.protocol,'VIP_BAD':str(bad),'VIP_SEED':'17'},results_xml=str(run/'results.xml'))
        root=ET.parse(run/'results.xml');failures=list(root.iter('failure'))+list(root.iter('error'))
        if bad:assert failures and a.protocol.upper()+'_REACTIVE_DATA' in ''.join(ET.tostring(f,encoding='unicode') for f in failures)
        else:assert not failures
    elapsed=time.monotonic()-start;assert elapsed<60
    print(f'{a.protocol}: reactive good passed; bad subordinate detected; {elapsed:.1f}s')


if __name__=='__main__':main()
