"""Check the userspace boot archive without a host cpio dependency."""
import importlib.util
from pathlib import Path
import stat
import pytest

pytestmark = pytest.mark.fast


def test_minimal_initramfs():
    path = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/linux/initramfs.py'
    spec = importlib.util.spec_from_file_location('linux_initramfs', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = module.archive(b'ELF fixture')
    offset = 0
    rows = {}
    while offset < len(data):
        assert data[offset:offset+6] == b'070701'
        fields = [int(data[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        offset += 110
        name = data[offset:offset+fields[11]-1].decode()
        assert data[offset+fields[11]-1] == 0
        offset = (offset + fields[11] + 3) & ~3
        body = data[offset:offset+fields[6]]
        offset = (offset + fields[6] + 3) & ~3
        rows[name] = (fields, body)
    assert rows['init'][1] == b'ELF fixture'
    assert rows['init'][0][1] == stat.S_IFREG | 0o755
    assert rows['dev/console'][0][1] == stat.S_IFCHR | 0o600
    assert rows['dev/console'][0][9:11] == [5, 1]
    assert set(rows) == {'dev', 'dev/console', 'init', 'TRAILER!!!'}

@pytest.mark.parametrize('resumable,ram,clock,poweroff', [
    (False, 128 * 1024 * 1024, 100000000, False),
    (True, 32 * 1024 * 1024, 1000000, True),
])
def test_linux_platform_is_opt_in(tmp_path, monkeypatch, resumable, ram, clock, poweroff):
    import json
    import sys
    from types import SimpleNamespace
    path = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/opensbi/prepare.py'
    spec = importlib.util.spec_from_file_location('linux_prepare', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def command(argv, **kwargs):
        Path(argv[argv.index('-o') + 1]).write_bytes(b'compiler fixture')
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(module, 'run_group', command)
    monkeypatch.setattr(module.shutil, 'which', lambda _: '/tool/gcc')
    firmware, image, out = tmp_path / 'firmware', tmp_path / 'Image', tmp_path / 'out'
    firmware.write_bytes(b'firmware')
    image.write_bytes(b'kernel')
    monkeypatch.setattr(sys, 'argv', ['prepare', '--firmware', str(firmware), '--kernel', str(image),
                                    '--out', str(out)] + (['--resumable'] if resumable else []))
    module.main()
    manifest = json.loads((out / 'payloads.json').read_text())
    devices = json.loads((out / 'devices.json').read_text())
    assert int(manifest['ram'][0]['size'], 16) == ram
    assert int(devices['regions'][0]['size'], 16) == ram
    assert (f'timebase-frequency = <{clock}>' in (out / 'soc.dts').read_text())
    assert 'riscv,isa-base = \"rv64i\"' in (out / 'soc.dts').read_text()
    assert '\"a\", \"c\", \"zicsr\"' in (out / 'soc.dts').read_text()
    assert '\"zicntr\"' in (out / 'soc.dts').read_text()
    assert any(d['model'] == 'syscon-poweroff' for d in devices['devices']) == poweroff

@pytest.mark.parametrize('status,console,expected', [
    ('bounded', '', 'timeout'),
    ('shutdown', '', 'timeout'),
    ('shutdown', 'RVW_LINUX_USERSPACE\r\n', 'pass'),
])
def test_debug_result_requires_userspace_and_shutdown(tmp_path, status, console, expected):
    import hashlib
    import json
    import zipfile
    from rvw.results import load_run
    path = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/linux/debug_result.py'
    spec = importlib.util.spec_from_file_location('linux_debug_result', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    elf = tmp_path / 'reset.elf'
    elf.write_bytes(b'ELF fixture')
    sample = dict(schema='rvw.vexii-boot-slice-result/1', status=status, cycle='100', retired='20',
                  pc='0x80000000', trap=None, wall_seconds=1, console={'uart': console},
                  wave_cycle_origin='99', wave_time_origin='58', wave_time_of_cycle_1=str(58+(1-99)*11))
    report, checkpoint = tmp_path / 'slice.json', tmp_path / 'slice.zip'
    report.write_text(json.dumps(sample))
    state = {k: sample[k] for k in ('cycle', 'retired', 'pc', 'trap')}
    state.update(schema='rvw.vexii-boot-slice/1', identity={'inputs': [hashlib.sha256(elf.read_bytes()).hexdigest()], 'rtl': '1' * 64})
    with zipfile.ZipFile(checkpoint, 'w') as archive:
        archive.writestr('state.json', json.dumps({'state': state}))
    module.convert(report, checkpoint, elf, tmp_path / 'debug')
    result = load_run(tmp_path / 'debug/result.json')
    assert result.status == expected
    assert result.why_inconclusive
    from rvw.bundle.clock import wave_clock
    clock = wave_clock(result.to_dict(), {})
    assert clock.known and clock.time(100) == 58
    assert result.to_dict()['details']['boot_trace_cycle_base'] == 0
    elf.write_bytes(b'different ELF')
    with pytest.raises(ValueError, match='ELF differs'):
        module.convert(report, checkpoint, elf, tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()
