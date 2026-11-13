"""Bounded standalone RTL qualification. No UVM runtime build."""
import argparse
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET
from cocotb_tools.runner import get_runner


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--protocol',choices=['spi','uart','gpio','i2c','axi','axilite','tilelink'],required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    src=Path(__file__).resolve().parent;started=time.monotonic()
    runner=get_runner('icarus')
    top='bus_top' if a.protocol in ('axi','axilite','tilelink') else 'serial_top'
    runner.build(sources=[src/(top+'.sv')],hdl_toplevel=top,build_dir=out/'build')
    os.environ['PYTHONPATH']=str(src)+os.pathsep+os.environ.get('PYTHONPATH','')
    diagnostic={'spi':'SPI_RTL_DATA','uart':'UART_RTL_DATA','gpio':'GPIO_STATE_OR_IRQ','i2c':'I2C_RTL_ACK','axi':'AXI_RTL_DATA','axilite':'AXILITE_RTL_DATA','tilelink':'TILELINK_RTL_DATA'}[a.protocol]
    for bad in (0,1):
        run=out/str(bad);run.mkdir()
        runner.test(hdl_toplevel=top,test_module='bus_test' if top=='bus_top' else 'serial_test',test_dir=run,
            seed=17,extra_env={'VIP_PROTOCOL':a.protocol,'VIP_SEED':'17','VIP_BAD':str(bad)},
            results_xml=str(run/'results.xml'))
        root=ET.parse(run/'results.xml'); failures=list(root.iter('failure'))+list(root.iter('error'))
        if bad: assert failures and diagnostic in ''.join(ET.tostring(f,encoding='unicode') for f in failures)
        else: assert not failures
    elapsed=time.monotonic()-started
    assert elapsed<60,f'qualification exceeded one minute: {elapsed:.1f}s'
    print(f'{a.protocol}: seeded good RTL passed; bad RTL detected; {elapsed:.1f}s')


if __name__=='__main__':main()
