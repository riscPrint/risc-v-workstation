"""The Linux profile must implement supervisor time, cycle and instret reads."""
import json
import os
from rvw.common.proc import run_group
from test_adapter import EXAMPLE, GCC


def test_supervisor_time(tmp_path):
    elf = tmp_path / 'time.elf'
    built = run_group([GCC, '-march=rv64imac_zicsr_zicntr', '-mabi=lp64', '-nostdlib',
        '-T', str(EXAMPLE / 'programs/link.ld'), str(EXAMPLE / 'linux/supervisor-time.S'),
        '-o', str(elf)], capture=True, timeout=30)
    assert built.returncode == 0, built.stderr
    manifest = tmp_path / 'payloads.json'
    manifest.write_text(json.dumps({'schema': 'rvw.boot-payloads/1', 'payloads': [],
        'ram': [{'base': '0x80000000', 'size': '0x1000000'}]}))
    devices = json.loads((EXAMPLE / 'live-devices.json').read_text())
    devices['regions'].append(dict(name='poweroff', kind='mmio', base='0x100000', size='0x1000',
        permissions='rw', cacheable=False, registers=[]))
    devices['devices'].append(dict(region='poweroff', model='syscon-poweroff', value='0x5555'))
    mapping = tmp_path / 'devices.json'
    mapping.write_text(json.dumps(devices))
    out = tmp_path / 'run'
    run = run_group([str(EXAMPLE / 'boot-slices.sh'), str(elf), str(manifest), str(mapping),
        str(out), str(tmp_path / 'checkpoint.zip'), 'fresh', '5000'],
        env=dict(os.environ), capture=True, timeout=900)
    assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-4000:]
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'shutdown' and result['console']['uart'] == 'T'
    assert result['mode'] == 1 and int(result['retired_by_mode'][1]) > 0
    assert result['trap'] is None
