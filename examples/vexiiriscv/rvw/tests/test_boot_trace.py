"""Native bounded trace/wave replay of a timer input masked after restore."""
import json
import os
from pathlib import Path
import shutil
from rvw.common.proc import run_group
from rvw.cosim.trace import Trace
from test_adapter import EXAMPLE, GCC


def test_checkpoint_timer_hang(tmp_path):
    elf = tmp_path / 'timer.elf'
    built = run_group([GCC, '-march=rv64imac_zicsr_zicntr', '-mabi=lp64', '-nostdlib',
        '-T', str(EXAMPLE / 'programs/link.ld'), str(EXAMPLE / 'linux/timer-hang.S'),
        '-o', str(elf)], capture=True, timeout=30)
    assert built.returncode == 0, built.stderr
    manifest = tmp_path / 'payloads.json'
    manifest.write_text(json.dumps({'schema': 'rvw.boot-payloads/1', 'payloads': [],
        'ram': [{'base': '0x80000000', 'size': '0x1000000'}]}))
    devices = json.loads((EXAMPLE / 'live-devices.json').read_text())
    devices['devices'][1]['cycles_per_tick'] = 1
    devices['regions'].append(dict(name='poweroff', kind='mmio', base='0x100000', size='0x1000',
        permissions='rw', cacheable=False, registers=[]))
    devices['devices'].append(dict(region='poweroff', model='syscon-poweroff', value='0x5555'))
    mapping = tmp_path / 'devices.json'
    mapping.write_text(json.dumps(devices))
    checkpoint = tmp_path / 'checkpoint.zip'
    fixture = tmp_path / 'before-timer.zip'
    env = dict(os.environ, RVW_BOOT_WORK=str(tmp_path / 'native'),
               RVW_BOOT_FREEZE_RUNTIME=str(tmp_path / 'runtime'), RVW_BOOT_REFERENCE_INPUTS='1')
    for label, mode, stop, flags in [
        ('first', 'fresh', 300, {}),
        ('control', 'restore', 1500, {'RVW_BOOT_TRACE': '300:1500'}),
        ('masked', 'restore', 1500, {'RVW_BOOT_TRACE': '300:1500', 'RVW_BOOT_WAVE': '300:1500',
                                  'RVW_BOOT_MASK_TIMER': '300:1500'}),
        ('recovered', 'restore', 2500, {'RVW_BOOT_TRACE': '1500:2500'}),
    ]:
        if label == 'masked':
            shutil.copyfile(fixture, checkpoint)
        run = run_group([str(EXAMPLE / 'boot-slices.sh'), str(elf), str(manifest), str(mapping),
            str(tmp_path / label), str(checkpoint), mode, str(stop)],
            env=dict(env, **flags), capture=True, timeout=900)
        (tmp_path / f'{label}.log').write_text(run.stdout + run.stderr)
        assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-4000:]
        if label == 'first':
            shutil.copyfile(checkpoint, fixture)
            env.pop('RVW_BOOT_FREEZE_RUNTIME')
            env['RVW_BOOT_CLASSPATH'] = str(tmp_path / 'runtime/classpath.txt')
        report = json.loads((tmp_path / label / 'result.json').read_text())
        if label == 'first':
            assert report['status'] == 'bounded' and report['console']['uart'] == 'A'
            assert not (tmp_path / label / 'rvfi.jsonl').exists()
        elif label == 'masked':
            assert report['status'] == 'bounded' and report['console']['uart'] == 'A'
            assert int(report['irq_levels'], 16) & 128 == 0
            assert int(report['device_irq_levels'], 16) & 128
            shutil.copyfile(checkpoint, tmp_path / 'masked.zip')
            assert (tmp_path / label / 'wave.fst').stat().st_size > 0
        else:
            assert report['status'] == 'shutdown' and report['console']['uart'] == 'AI'
            assert int(report['trap']['cause'], 16) == (1 << 63) + 7
            shutil.copyfile(checkpoint, tmp_path / f'{label}.zip')
        if flags:
            rows = [json.loads(line) for line in (tmp_path / label / 'rvfi.jsonl').read_text().splitlines()]
            assert list(Trace(tmp_path / label / 'rvfi.jsonl'))
            records = [row for row in rows if 'order' in row]
            assert int(report['trace_records']) == len(records)
            if label != 'masked':
                assert records
            assert [row['order'] for row in records] == list(range(len(records)))
            assert all('absolute_order' in row for row in records)
            assert rows[-1]['event'] == 'end'
    assert (tmp_path / 'masked/wave.fst').stat().st_size > 0
