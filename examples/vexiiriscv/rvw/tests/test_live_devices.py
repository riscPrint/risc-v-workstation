"""Native VexiiRiscv interrupt-driven UART, CLINT and PLIC control."""
import json
import os
from pathlib import Path
from rvw.common.proc import run_group


def test_live_echo(tmp_path):
    root = Path(__file__).resolve().parents[1]
    elf = tmp_path / 'echo.elf'
    built = run_group(['riscv64-unknown-elf-gcc', '-march=rv32im_zicsr', '-mabi=ilp32',
                       '-nostdlib', '-Wl,--build-id=none', '-T', str(root / 'programs/link.ld'),
                       str(root / 'programs/device-echo.S'), '-o', str(elf)],
                      capture=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    out = tmp_path / 'echo'
    ran = run_group([str(root / 'run.sh'), 'run', '--elf', str(elf), '--out', str(out),
                     '--soc-map', str(root / 'live-devices.json'), '--seed', '1',
                     '--mem-latency', '0', '--max-cycles', '30000', '--rvfi-trace', '--json'],
                    env=dict(os.environ), capture=True, text=True, timeout=1200)
    assert ran.returncode == 0, ran.stderr
    report = json.loads(ran.stdout)
    assert report['status'] == 'pass' and not report.get('inconclusive')
    assert report['details']['device_output']['uart'] == 'echo\n'
    records = [json.loads(line) for line in (out / 'rvfi.jsonl').read_text().splitlines()]
    assert records[-1]['event'] == 'end' and records[-1]['status'] == 'pass'
    levels = [int(r['levels'], 16) for r in records if r.get('event') == 'irq']
    assert any(n & 8 for n in levels)
    assert any(n & 128 for n in levels)
    assert any(n & 2048 for n in levels)
