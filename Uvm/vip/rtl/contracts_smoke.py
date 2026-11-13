"""Bounded standalone RTL qualification. No UVM runtime build."""
from rvw.sim.uvm import require_evidence
import argparse
import json
import hashlib
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET
from cocotb_tools.runner import get_runner


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--protocol',choices=['pcie','ethernet','dram','coherent'],required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    src=Path(__file__).resolve().parent;started=time.monotonic()
    runner=get_runner('icarus')
    top='contracts_top'
    runner.build(sources=[src/(top+'.sv')],hdl_toplevel=top,build_dir=out/'build')
    os.environ['PYTHONPATH']=str(src)+os.pathsep+os.environ.get('PYTHONPATH','')
    diagnostic={'pcie':'PCIE_COMPLETION_DATA','ethernet':'ETH_TX_DATA_OR_ERROR','dram':'DRAM_MODEL_DATA','coherent':'COH_DATA'}[a.protocol]
    rows=[]
    for bad in (0,1):
        run=out/str(bad);run.mkdir()
        runner.test(hdl_toplevel=top,test_module='contracts_test',test_dir=run,
            seed=17,extra_env={'VIP_PROTOCOL':a.protocol,'VIP_SEED':'17','VIP_BAD':str(bad)},
            results_xml=str(run/'results.xml'))
        root=ET.parse(run/'results.xml'); failures=list(root.iter('failure'))+list(root.iter('error'))
        require_evidence(len(list(root.iter('testcase')))==1 and not list(root.iter('skipped')), 'missing executed RTL test')
        if bad: require_evidence(failures and diagnostic in ''.join(ET.tostring(f,encoding='unicode') for f in failures), "missing conformance evidence")
        else: require_evidence(not failures, "missing conformance evidence")
        rows.append(dict(bad=bool(bad),checked=True,results=str(run/'results.xml')))
    elapsed=time.monotonic()-started
    require_evidence(elapsed<60, f'qualification exceeded one minute: {elapsed:.1f}s')
    report=dict(protocol=a.protocol,seed=17,scope='seeded digital semantic RTL endpoint',elapsed_s=elapsed,runs=rows,
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (src/'contracts_top.sv',src/'contracts_test.py')})
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'{a.protocol}: seeded good RTL passed; bad RTL detected; {elapsed:.1f}s')


if __name__=='__main__':main()
