"""Native sampled Spike comparison across a supervisor counter checkpoint."""
import json
import os
from pathlib import Path
import shutil
import sys
import pytest
from rvw.common.proc import run_group
from test_adapter import EXAMPLE, GCC


def test_sampled_counter_continuation(tmp_path):
    shim = os.environ.get('RVW_SPIKE_SHIM')
    if not shim or not Path(shim).is_file():
        pytest.skip('build a matching Spike shim and set RVW_SPIKE_SHIM')
    elf = tmp_path / 'time.elf'
    built = run_group([GCC, '-march=rv64imac_zicsr_zicntr', '-mabi=lp64', '-nostdlib',
        '-T', str(EXAMPLE / 'programs/link.ld'), str(EXAMPLE / 'linux/supervisor-time.S'),
        '-o', str(elf)], capture=True, timeout=30)
    assert built.returncode == 0, built.stderr
    payloads = tmp_path / 'payloads.json'
    payloads.write_text(json.dumps(dict(schema='rvw.boot-payloads/1', payloads=[],
        ram=[dict(base='0x80000000', size='0x1000000')])) )
    devices = json.loads((EXAMPLE / 'live-devices.json').read_text())
    devices['regions'].append(dict(name='poweroff', kind='mmio', base='0x100000', size='0x1000',
        permissions='rw', cacheable=False, registers=[]))
    devices['devices'].append(dict(region='poweroff', model='syscon-poweroff', value='0x5555'))
    mapping = tmp_path / 'devices.json'
    mapping.write_text(json.dumps(devices))
    checkpoint = tmp_path / 'checkpoint.zip'
    before = tmp_path / 'before.zip'
    env = dict(os.environ, RVW_BOOT_WORK=str(tmp_path / 'native'), RVW_BOOT_REFERENCE_INPUTS='1',
               RVW_BOOT_FREEZE_RUNTIME=str(tmp_path / 'runtime'))
    for label, mode, stop in [('first', 'fresh', 100), ('continued', 'restore', 5000)]:
        if mode == 'restore':
            env['RVW_BOOT_TRACE'] = '100:5000'
        run = run_group([str(EXAMPLE / 'boot-slices.sh'), str(elf), str(payloads), str(mapping),
            str(tmp_path / label), str(checkpoint), mode, str(stop)], env=env, capture=True, timeout=900)
        (tmp_path / f'{label}.log').write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-4000:]
        if mode == 'fresh':
            shutil.copyfile(checkpoint, before)
            env.pop('RVW_BOOT_FREEZE_RUNTIME')
            env['RVW_BOOT_CLASSPATH'] = str(tmp_path / 'runtime/classpath.txt')
    trace = tmp_path / 'continued/rvfi.jsonl'
    rows = [json.loads(line) for line in trace.read_text().splitlines()]
    records = [row for row in rows if 'order' in row]
    n = min(12, len(records))
    assert n >= 6
    base = [sys.executable, str(EXAMPLE / 'linux/sample.py'), '--checkpoint', str(before),
            '--end-checkpoint', str(checkpoint), '--elf', str(elf), '--payloads', str(payloads),
            '--map', str(mapping), '--shim', shim, '-n', str(n)]
    run = run_group([*base, '--trace', str(trace), '--out', str(tmp_path / 'sample')],
                    capture=True, timeout=60)
    (tmp_path / 'sample.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr
    result = json.loads((tmp_path / 'sample/result.json').read_text())
    assert result['status'] == 'match' and result['compared'] == n
    assert result['counter_inputs'] >= 1
    records[0]['rd_wdata'] = hex(int(records[0]['rd_wdata'], 16) ^ 1)
    mutant = tmp_path / 'mutant.jsonl'
    mutant.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    bad = run_group([*base, '--trace', str(mutant), '--out', str(tmp_path / 'mutant-sample')],
                    capture=True, timeout=60)
    assert bad.returncode == 1, bad.stdout[-3000:] + bad.stderr
    assert json.loads((tmp_path / 'mutant-sample/result.json').read_text())['status'] == 'mismatch'
