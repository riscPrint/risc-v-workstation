"""Fresh-process RTL restore, including an outstanding bus reply and UART state."""
import json
import os
import zipfile
from pathlib import Path
from rvw.common.proc import run_group
from test_adapter import GCC, EXAMPLE


def test_boot_slices(tmp_path):
    source = tmp_path / 'loop.S'
    source.write_text('''.option norvc
.text
.globl _start
_start:
  li t0, 0x10000000
  li t1, 75
  sb t1, 0(t0)
  li t2, 100
1: addi t2, t2, -1
  bnez t2, 1b
  sb t1, 0(t0)
  li t2, 100
  j 1b
.data
.dword 0
''')
    elf = tmp_path / 'loop.elf'
    built = run_group([GCC, '-march=rv64imac_zicsr', '-mabi=lp64', '-nostdlib',
                       '-T', str(EXAMPLE / 'programs/link.ld'), str(source), '-o', str(elf)], capture=True, timeout=30)
    assert built.returncode == 0, built.stderr
    manifest = tmp_path / 'payloads.json'
    manifest.write_text(json.dumps({'schema': 'rvw.boot-payloads/1', 'payloads': [],
                                    'ram': [{'base': '0x80000000', 'size': '0x1000000'}]}))
    checkpoint = tmp_path / 'slice.zip'
    env = dict(os.environ, RVW_BOOT_WORK=str(tmp_path / 'native'))
    snapshots = {}
    for label, mode, stop in [('first', 'fresh', 1000), ('resumed', 'restore', 2000),
                              ('straight', 'fresh', 2000)]:
        ran = run_group([str(EXAMPLE / 'boot-slices.sh'), str(elf), str(manifest),
                         str(EXAMPLE / 'live-devices.json'), str(tmp_path / label),
                         str(checkpoint), mode, str(stop)], capture=True, timeout=900, env=env)
        assert ran.returncode == 0, ran.stdout[-4000:] + ran.stderr[-4000:]
        with zipfile.ZipFile(checkpoint) as archive:
            snapshots[label] = (archive.read('state.json'), archive.read('ram.bin'))
    resumed = json.loads((tmp_path / 'resumed/result.json').read_text())
    straight = json.loads((tmp_path / 'straight/result.json').read_text())
    for key in ('cycle', 'retired', 'pc', 'trap', 'console'):
        assert resumed[key] == straight[key], key
    assert set(resumed['console']['uart']) == {'K'}
    assert len(resumed['console']['uart']) > 1
    assert int(resumed['retired']) > 100
    assert snapshots['resumed'] == snapshots['straight']
