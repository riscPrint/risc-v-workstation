"""Synthetic orchestration checks. These tests do not boot Linux or RTL."""
import json
from pathlib import Path

import pytest

from rvw.arch import linux
from rvw.cli import main
from rvw.common.proc import Result


@pytest.fixture
def reference(tmp_path, monkeypatch):
    images = tmp_path / 'build/images'
    images.mkdir(parents=True)
    for name in ('Image', 'rootfs.cpio.gz', 'fw_jump.bin', 'fw_jump.elf'):
        (images / name).write_bytes(name.encode())
    platform = tmp_path / 'platform.json'
    platform.write_text(json.dumps({'schema': 'rvw.linux-platform/1', 'machine': 'virt',
                                   'harts': 1, 'memory_mib': 128, 'command_line': 'rdinit=/init',
                                   'dt_checks': [{'node': '/cpus', 'property': 'timebase-frequency',
                                                  'type': 'u', 'expected': '10000000'}]}))
    fake = tmp_path / 'tool'
    fake.write_bytes(b'fixture tool')
    monkeypatch.setattr(linux, 'tool', lambda name: str(fake))
    def command(argv, out, timeout, **kw):
        (out / 'platform.dtb').write_bytes(b'fixture DTB')
    monkeypatch.setattr(linux, 'command', command)
    def run(argv, **kw):
        if 'capture' in kw:
            return Result(0, stdout='10000000\n')
        kw['stdout'].write('\nRVW_LINUX_USERSPACE_OK\nPower down\n')
        return Result(0)
    monkeypatch.setattr(linux, 'run_group', run)
    return dict(images=images, platform=platform, out=tmp_path / 'out')


def test_prepare_captures_tables_and_marks_rtl_blocked(reference):
    result = linux.execute('prepare', **reference)
    assert result['status'] == 'prepared_reference'
    assert result['rtl_preparation']['status'] == 'blocked'
    assert result['equivalence'] == 'not_checked'
    assert len(result['artifacts']) == 4
    assert result['device_checks'][0]['matches']


def test_boot_observes_userspace_and_shutdown(reference):
    result = linux.execute('boot', **reference)
    assert result['status'] == 'reference_userspace_observed'
    assert '-dtb' in result['argv']
    assert result['rtl_boot'] == 'not_run'


@pytest.mark.parametrize('content,code,timed_out', [
    ('login: Power down', 0, False),
    ('\nRVW_LINUX_USERSPACE_OK\nPower down', 124, True),
    ('\nRVW_LINUX_USERSPACE_OK\nPower down\nKernel panic', 0, False),
    ('\nRVW_LINUX_USERSPACE_OK\n', 0, False),
    ('\nRVW_LINUX_USERSPACE_OK\nPower down', 1, False),
])
def test_incomplete_boot_never_passes(reference, monkeypatch, content, code, timed_out):
    def run(argv, **kw):
        if 'capture' in kw:
            return Result(0, stdout='10000000')
        kw['stdout'].write(content)
        return Result(code, timed_out)
    monkeypatch.setattr(linux, 'run_group', run)
    with pytest.raises(ValueError, match='incomplete'):
        linux.execute('boot', **reference)
    assert json.loads((reference['out'] / 'manifest.json').read_text())['status'] == 'inconclusive'


def test_mismatched_device_table_blocks(reference, monkeypatch):
    monkeypatch.setattr(linux, 'run_group', lambda *a, **kw: Result(0, stdout='999'))
    with pytest.raises(ValueError, match='differs'):
        linux.execute('prepare', **reference)
    result = json.loads((reference['out'] / 'manifest.json').read_text())
    assert not result['device_checks'][0]['matches']


def test_macos_build_is_explicit_blocker(tmp_path, monkeypatch):
    monkeypatch.setattr(linux.host, 'system', lambda: 'Darwin')
    with pytest.raises(ValueError, match='native Linux'):
        linux.execute('build', tmp_path / 'out')


@pytest.mark.parametrize('timeout,jobs', [(0, 2), (float('nan'), 2), (1, 0), (1, 5)])
def test_bad_bounds(tmp_path, timeout, jobs):
    with pytest.raises(ValueError):
        linux.execute('prepare', tmp_path / 'out', timeout=timeout, jobs=jobs)
    assert not (tmp_path / 'out').exists()


def test_existing_output_refused(reference):
    reference['out'].mkdir()
    with pytest.raises(FileExistsError):
        linux.execute('prepare', **reference)


def test_missing_images_is_cli_error(tmp_path, capsys):
    assert main(['arch', 'linux', 'prepare', '--out', str(tmp_path / 'out'), '--json']) == 2
    assert 'required' in json.loads(capsys.readouterr().out)['error']


def test_changed_image_refuses_build_provenance(reference):
    path = reference['images'].parent.parent / 'manifest.json'
    path.write_text(json.dumps({'artifacts': {name: {'sha256': '0' * 64} for name in
                                            ('Image', 'rootfs.cpio.gz', 'fw_jump.bin', 'fw_jump.elf')}}))
    try:
        with pytest.raises(ValueError, match='differs from build manifest'):
            linux.execute('prepare', **reference)
    finally:
        path.unlink()


def test_firmware_uses_pinned_commit_and_llvm(tmp_path, monkeypatch):
    compiler = tmp_path / 'clang'
    compiler.write_bytes(b'fixture clang')
    monkeypatch.setattr(linux, 'tool', lambda name: str(compiler))
    monkeypatch.setattr(linux.host, 'system', lambda: 'Darwin')
    commands = []
    def command(argv, out, timeout, **kw):
        commands.append(argv)
        root = out / 'opensbi/build/platform/generic'
        (root / 'firmware').mkdir(parents=True, exist_ok=True)
        (root / 'kconfig').mkdir(exist_ok=True)
        (root / 'kconfig/.config').write_bytes(b'fixture config')
        for name in ('fw_jump.bin', 'fw_jump.elf'):
            (root / 'firmware' / name).write_bytes(b'fixture firmware')
    monkeypatch.setattr(linux, 'command', command)
    result = linux.execute('firmware', tmp_path / 'out', llvm=True)
    assert result['status'] == 'built'
    assert linux.OPENSBI in commands[1]
    assert 'LLVM=1' in commands[-1]
    assert result['configuration']['LLVM']
    assert result['effective_configuration']['sha256']


def test_build_captures_config_and_images(tmp_path, monkeypatch):
    import hashlib
    import tarfile
    source = tmp_path / f'buildroot-{linux.BUILDROOT}'
    source.mkdir()
    archive = tmp_path / 'fixture.tar.xz'
    with tarfile.open(archive, 'w:xz') as tar:
        tar.add(source, arcname=source.name)
    monkeypatch.setattr(linux, 'BUILDROOT_SHA256', hashlib.sha256(archive.read_bytes()).hexdigest())
    monkeypatch.setattr(linux.host, 'system', lambda: 'Linux')
    monkeypatch.setattr(linux, 'tool', lambda name: name)
    monkeypatch.setenv('RVW_HOME', str(Path(__file__).resolve().parents[2]))
    def command(argv, out, timeout, **kw):
        if argv[0] == 'curl':
            (out / 'buildroot.tar.xz').write_bytes(archive.read_bytes())
        else:
            for relative in ('build/.config', 'build/build/linux-6.12.9/.config',
                             'build/build/opensbi-1.6/build/platform/generic/kconfig/.config',
                             'build/images/Image', 'build/images/rootfs.cpio.gz',
                             'build/images/fw_jump.bin', 'build/images/fw_jump.elf'):
                path = out / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture build output')
    monkeypatch.setattr(linux, 'command', command)
    result = linux.execute('build', tmp_path / 'out')
    assert result['status'] == 'built'
    assert len(result['artifacts']) == 4
    assert result['source']['sha256'] == linux.BUILDROOT_SHA256
    assert '@OVERLAY@' not in (tmp_path / 'out/defconfig').read_text()


def test_bad_source_hash_blocks_build(tmp_path, monkeypatch):
    monkeypatch.setattr(linux.host, 'system', lambda: 'Linux')
    monkeypatch.setattr(linux, 'tool', lambda name: name)
    monkeypatch.setattr(linux, 'command', lambda argv, out, timeout: (out / 'buildroot.tar.xz').write_bytes(b'bad source'))
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        linux.execute('build', tmp_path / 'out')
