"""Project Linux startup preparation checks. These do not simulate a core."""
import importlib.util
import json
from pathlib import Path
import pytest
from rvw.arch.linux import identity
from rvw.common.proc import Result


@pytest.fixture
def startup(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[2] / 'examples/qemu-linux/prepare-rtl.py'
    spec = importlib.util.spec_from_file_location('linux_startup', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prepared = tmp_path / 'prepared'
    prepared.mkdir()
    for name in ('fw_jump.bin', 'Image', 'rootfs.cpio.gz', 'platform.dtb'):
        (prepared / name).write_bytes(name.encode())
    manifest = {'status': 'prepared_reference', 'command_line': 'rdinit=/rvw-init',
                'artifacts': {n: identity(prepared / n) for n in ('fw_jump.bin', 'Image', 'rootfs.cpio.gz')},
                'device_tree': identity(prepared / 'platform.dtb')}
    (prepared / 'manifest.json').write_text(json.dumps(manifest))
    tool = tmp_path / 'tool'
    tool.write_bytes(b'fixture tool')
    monkeypatch.setattr(module, 'tool', lambda _: str(tool))
    calls = []
    def command(argv, out, timeout, **kw):
        calls.append(argv)
        if '-o' in argv:
            (out / argv[-1]).write_bytes(b'fixture ELF')
    monkeypatch.setattr(module, 'command', command)
    return module, prepared, tmp_path / 'out', calls


def test_fixed_layout_and_chosen_properties(startup):
    module, prepared, out, calls = startup
    result = module.prepare(prepared, out)
    payloads = json.loads((out / 'payloads.json').read_text())
    assert [p['address'] for p in payloads['payloads']] == ['0x80200000', '0x80400000', '0x86000000', '0x87e00000']
    assert result['device_bus'] == 'not_connected' and result['rtl_boot'] == 'not_run'
    assert result['prefix_instructions'] == 164
    assert 'lui t0,0x40100' in (out / 'reset.S').read_text()
    assert 'lui a1,0x43f00' in (out / 'reset.S').read_text()
    chosen = [a for a in calls if '/chosen' in a]
    assert len(chosen) == 3
    assert chosen[2][-2:] == ['0', f'{0x86000000 + len(b"rootfs.cpio.gz"):x}']


@pytest.mark.parametrize('name', ['Image', 'platform.dtb'])
def test_changed_reference_bytes_block_preparation(startup, name):
    module, prepared, out, calls = startup
    (prepared / name).write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed reference'):
        module.prepare(prepared, out)
    assert not (out / 'manifest.json').exists()


@pytest.mark.parametrize('console,code,timed_out,observed', [
    ('\nRVW_LINUX_USERSPACE_OK\nPower down', 0, False, True),
    ('\nRVW_LINUX_USERSPACE_OK\nPower down\nKernel panic', 0, False, False),
    ('\nRVW_LINUX_USERSPACE_OK\nPower down', 124, True, False),
    ('login:', 0, False, False),
])
def test_fixed_qemu_boot_requires_userspace_and_shutdown(startup, monkeypatch, console, code, timed_out, observed):
    module, prepared, out, calls = startup
    module.prepare(prepared, out)
    def run(argv, **kw):
        assert '-kernel' not in argv and '-dtb' not in argv and '-initrd' not in argv
        assert f'loader,file={out}/reference.elf,cpu-num=0' in argv
        kw['stdout'].write(console)
        return Result(code, timed_out=timed_out)
    monkeypatch.setattr(module, 'run_group', run)
    if observed:
        assert module.verify_qemu(out)['qemu_boot']['status'] == 'reference_userspace_observed'
    else:
        with pytest.raises(ValueError, match='incomplete'):
            module.verify_qemu(out)
        assert json.loads((out / 'manifest.json').read_text())['qemu_boot']['status'] == 'inconclusive'
