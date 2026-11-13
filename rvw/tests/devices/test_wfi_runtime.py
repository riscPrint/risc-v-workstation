"""Bounded WFI wake runs. IRQ schedules are fixed before simulation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from rvw.common.proc import run_group
from rvw.cosim.elf import Elf
from native_sdks import require_core

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'rvw/tests/interrupts'))
from window_check import check_interrupts


@pytest.mark.parametrize('core,xlen', [('vexriscv', 32), ('boom', 64)])
def test_wfi_timer_wakeup(tmp_path, core, xlen):
    require_core(core)
    source = ROOT / 'RiscvSim/tests/programs/wfi-timer.S'
    elf = tmp_path / 'wfi-timer'
    subprocess.run([os.environ.get('RISCV_GCC', 'riscv64-unknown-elf-gcc'),
                    f'-march=rv{xlen}im_zicsr', '-mabi=' + ('ilp32' if xlen == 32 else 'lp64'),
                    *(['-DNO_PMP'] if xlen == 32 else []), '-nostdlib', '-nostartfiles', '-static',
                    '-T', str(source.parent / 'link.ld'), '-o', str(elf), str(source)], check=True)
    adapter = ROOT / ('examples/vexriscv/rvw/run.sh' if xlen == 32 else 'RiscvSim/boom/run.sh')
    schedule = '1:0x0,1000:0x80'
    out = tmp_path / core
    result = run_group([str(adapter), 'run', '--elf', str(elf), '--out', str(out),
                        '--max-cycles', '20000', '--wall-timeout', '120', '--mem-latency', '0',
                        '--seed', '1', '--irq-schedule', schedule, '--rvfi-trace', '--json'], timeout=1800,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, (result.stdout[-2000:], result.stderr[-2000:])
    c1 = json.loads((out / 'result.json').read_text())
    assert c1['status'] == 'pass' and not c1.get('inconclusive')
    assert c1['irq_schedule'] == schedule and c1['rtl_sha256']
    trace = out / 'rvfi.jsonl'
    symbols = Elf(elf).symbols
    checked = check_interrupts(trace, [(1, 0), (1000, 128)], cause=(1 << (xlen-1)) | 7,
          window=(1001, 19999), handler_pc=symbols['irq_handler'], mode=3,
          epc_range=(symbols['irq_wait'], symbols['irq_wait_end']))
    assert checked['status'] == 'consistent', checked
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    assert any(int(r.get('insn', '0'), 16) == 0x10500073 for r in rows if 'order' in r)
    args = ['--core', 'boom']
    if xlen == 32:
        args += ['--platform', str(ROOT / 'examples/vexriscv/rvw/platform.json')]
    spike = subprocess.run([str(ROOT / 'rvw/.venv/bin/rvw'), 'cosim', 'check', *args,
                            '--trace', str(trace), '--elf', str(elf), '--json'], capture_output=True, text=True)
    (out / 'cosim.json').write_text(spike.stdout)
    assert spike.returncode == 0, spike.stdout[-2000:]
