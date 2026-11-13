"""Native OpenSBI and supervisor payload control."""
import json
import os
from pathlib import Path
import sys
import pytest
from rvw.common.proc import run_group
from rvw.cosim.trace import Trace


def test_opensbi_supervisor_payload(tmp_path):
    firmware=os.environ.get('RVW_OPENSBI_FIRMWARE')
    if not firmware: pytest.skip('pinned RV64IMA fw_jump.bin required')
    root=Path(__file__).resolve().parents[1]
    prepared=tmp_path/'prepared'
    built=run_group([sys.executable,str(root/'opensbi/prepare.py'),
        '--firmware',firmware,'--out',str(prepared)],capture=True,timeout=60)
    assert built.returncode==0,built.stdout+built.stderr
    out=tmp_path/'run'
    ran=run_group([str(root/'run64.sh'),'run','--config','rv64imasu',
        '--elf',str(prepared/'reset.elf'),'--boot-payloads',str(prepared/'payloads.json'),
        '--soc-map',str(prepared/'devices.json'),'--out',str(out),'--seed','1',
        '--mem-latency','0','--max-cycles','10000000','--wall-timeout','900',
        '--rvfi-trace','--json'],capture=True,timeout=1500)
    assert ran.returncode==0,ran.stdout+ran.stderr
    result=json.loads(ran.stdout)
    assert result['status']=='pass' and not result.get('inconclusive')
    console=result['details']['device_output']['uart']
    assert console.rstrip().endswith('S')
    assert 'Can not configure pmp' not in console
    trace=Trace(out/'rvfi.jsonl')
    supervisor=False;ecall=False;last=None
    try:
        for record in trace:
            supervisor |= record.get('mode')==1
            ecall |= record.get('event')=='trap' and int(record['cause'])==9
            last=record
    finally:trace.close()
    assert supervisor and ecall
    assert last['event']=='end' and last['status']=='pass'
    assert result['details']['last_retired_mode']==1
    assert sum(result['details']['retired_by_mode'].values())==result['instret']
