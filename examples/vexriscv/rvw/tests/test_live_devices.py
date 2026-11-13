"""Real UART RX/echo and CLINT/PLIC pin wiring on VexRiscv."""
import json
import os

from rvw.common.proc import run_group
from test_adapter import EXAMPLE, GCC


def test_interrupt_driven_echo(tmp_path):
    project = EXAMPLE.parent
    elf = tmp_path / 'echo'
    build = run_group([GCC, '-march=rv32im_zicsr', '-mabi=ilp32', '-nostdlib',
                       '-T', str(EXAMPLE / 'programs/link.ld'),
                       str(EXAMPLE / 'programs/device-echo.S'), '-o', str(elf)],
                      capture=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    no_rx = json.loads((project / 'live-devices.json').read_text())
    no_rx['devices'][0]['rx'] = []
    negative = tmp_path / 'no-rx.json'
    negative.write_text(json.dumps(no_rx))
    jobs = [dict(elf=str(elf), out=str(tmp_path / name), soc_map=str(mapping),
                 seed=1, mem_latency=0, max_cycles=20000, rvfi_trace=True)
            for name, mapping in [('run', project / 'live-devices.json'),
                                  ('no-rx', negative), ('fresh', project / 'live-devices.json')]]
    result = run_group(
        [str(EXAMPLE / 'run.sh'), 'serve'],
        input=''.join(json.dumps(j) + '\n' for j in jobs), env=dict(os.environ),
        capture=True, text=True, timeout=600)
    assert result.returncode == 0, result.stderr
    replies = [json.loads(line)['result'] for line in result.stdout.splitlines()]
    assert [r['status'] for r in replies] == ['pass', 'timeout', 'pass'], replies
    assert replies[1]['details']['device_output']['uart'] == ''
    assert replies[2]['details']['device_output']['uart'] == 'echo\n'
    report = replies[0]
    assert report['status'] == 'pass', report
    assert report['details']['device_output']['uart'] == 'echo\n'
    trace = [json.loads(line) for line in (tmp_path / 'run/rvfi.jsonl').read_text().splitlines()]
    traps = [r for r in trace if r.get('event') == 'trap']
    causes = {int(r['cause'], 0) for r in traps}
    assert {0x80000003, 0x80000007, 0x8000000b} <= causes, traps
    # No external IRQ schedule was supplied. Device MMIO drove all pins.
    assert not report.get('inconclusive'), report
