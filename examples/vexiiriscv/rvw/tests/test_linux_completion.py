"""A Linux profile must not pass through the bare-metal completion mailbox."""
import json
from pathlib import Path
from rvw.common.proc import run_group
from rvw.cosim.trace import Trace
from test_adapter import GCC,EXAMPLE


def check_control(out):
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='timeout' and result['cycles']==500
    assert result['details']['completion']=='bounded'
    assert result['details']['tohost'] is None
    trace=Trace(out/'rvfi.jsonl');stored=False
    try:
        for r in trace:
            if r.get('mem_wmask') and int(r['mem_wdata'])==1:stored=True
    finally:trace.close()
    assert stored


def test_linux_ignores_baremetal_pass(tmp_path):
    source=tmp_path/'pass.S'
    source.write_text('.text\n.global _start\n_start:\nla t0,tohost\nli t1,1\nsd t1,0(t0)\n1: j 1b\n.data\n.balign 8\n.global tohost\ntohost: .dword 0\n')
    elf=tmp_path/'pass.elf'
    built=run_group([GCC,'-march=rv64ima_zicsr','-mabi=lp64','-nostdlib',
        '-T',str(EXAMPLE/'programs/link.ld'),str(source),'-o',str(elf)],capture=True,timeout=30)
    assert built.returncode==0,built.stderr
    out=tmp_path/'run'
    ran=run_group([str(EXAMPLE/'run64.sh'),'run','--config','rv64imacsu_linux',
        '--elf',str(elf),'--out',str(out),'--seed','1','--mem-latency','0',
        '--max-cycles','500','--rvfi-trace','--json'],capture=True,timeout=900)
    assert ran.returncode==1,ran.stdout+ran.stderr
    check_control(out)
