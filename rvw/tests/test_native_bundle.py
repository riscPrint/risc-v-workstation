"""Native bundle fixtures. No native build or network access."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_bundle', ROOT / 'scripts/native-bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


@pytest.fixture
def packed(tmp_path):
    home = tmp_path / 'checkout with spaces'
    (home / 'scripts').mkdir(parents=True)
    (home / 'Cosim').mkdir()
    (home / 'scripts/install.sh').write_text('gcc_revision=' + 'a' * 40 + '\n')
    source = tmp_path / 'source'
    (source / 'bin').mkdir(parents=True)
    binary = source / 'bin/riscv64-unknown-elf-gcc'
    binary.write_text('#!/bin/sh\necho GCC\n')
    binary.chmod(0o755)
    output = tmp_path / 'archives'
    bundle.pack(home, 'gcc', source, output)
    return home, output


def test_round_trip_offline(packed, monkeypatch):
    home, output = packed
    monkeypatch.setattr(bundle.subprocess, 'run', lambda *a, **k: pytest.fail('network request'))
    bundle.install(home, ['gcc'], directory=output)
    binary = home / '.tools/riscv/bin/riscv64-unknown-elf-gcc'
    assert binary.read_text().endswith('echo GCC\n')
    assert binary.stat().st_mode & 0o111


def test_corrupt_archive_preserves_install(packed):
    home, output = packed
    installed = home / '.tools/riscv/bin/old'
    installed.parent.mkdir(parents=True)
    installed.write_text('keep')
    archive = next(output.glob('*.tar.gz'))
    archive.write_bytes(archive.read_bytes() + b'corruption')
    with pytest.raises(ValueError, match='checksum mismatch'):
        bundle.install(home, ['gcc'], directory=output)
    assert installed.read_text() == 'keep'


def test_pin_mismatch(packed):
    home, output = packed
    (home / 'scripts/install.sh').write_text('gcc_revision=' + 'b' * 40 + '\n')
    with pytest.raises(ValueError, match='identity'):
        bundle.install(home, ['gcc'], directory=output)
    assert not (home / '.tools').exists()


def test_all_archives_checked_before_replacement(packed):
    home, output = packed
    with pytest.raises(FileNotFoundError):
        bundle.install(home, ['gcc', 'spike'], directory=output)
    assert not (home / '.tools').exists()


def test_download_exact_private_artifact(packed, monkeypatch):
    home, output = packed
    calls = []
    def download(args, **kwargs):
        import shutil
        calls.append(args)
        shutil.copytree(output, args[-1])
    monkeypatch.setattr(bundle.subprocess, 'run', download)
    bundle.install(home, ['gcc'], run='1234')
    assert calls[0][:7] == ['gh', 'run', 'download', '1234', '--repo', 'riscPrint/risc-v-workstation', '--name']
    assert calls[0][7] == f'gcc-{bundle.host()}'


def test_no_implicit_latest(packed):
    home, _ = packed
    with pytest.raises(ValueError, match='numeric'):
        bundle.install(home, ['gcc'], run='latest')


def test_wrong_host(packed, monkeypatch):
    home, output = packed
    archive = next(output.glob('*.tar.gz'))
    import tarfile
    with tarfile.open(archive, 'r:gz') as tar:
        metadata = json.load(tar.extractfile('bundle.json'))
    assert metadata['host'] == bundle.host()
    monkeypatch.setattr(bundle, 'host', lambda: 'wrong-host')
    with pytest.raises(FileNotFoundError):
        bundle.install(home, ['gcc'], directory=output)


def test_spike_manifest_keeps_embedded_identity(tmp_path):
    home = tmp_path / 'home'
    (home / 'scripts').mkdir(parents=True)
    (home / 'Cosim').mkdir()
    (home / 'scripts/install.sh').write_text('spike_revision=' + 'a' * 40 + '\n')
    (home / 'Cosim/spike_shim.cc').write_text('source')
    source = tmp_path / 'spike'
    (source / 'lib').mkdir(parents=True)
    (source / 'lib/libriscv.a').write_bytes(b'static library')
    shim = source / 'rvw-shim/librvw_spike.so'
    shim.parent.mkdir()
    shim.write_bytes(b'bound shim')
    manifest = shim.with_name(shim.name + '.manifest.json')
    data = {'build_id': 'immutable', 'build_inputs': {'source': '/ci/source'},
            'spike_library': '/ci/spike/lib/libriscv.a',
            'spike_library_sha256': bundle.digest(source / 'lib/libriscv.a')}
    manifest.write_text(json.dumps(data))
    output = tmp_path / 'artifacts'
    bundle.pack(home, 'spike', source, output)
    bundle.install(home, ['spike'], directory=output)
    copied = home / 'Cosim/build/librvw_spike.so'
    result = json.loads(copied.with_name(copied.name + '.manifest.json').read_text())
    assert copied.read_bytes() == b'bound shim'
    assert result['build_id'] == data['build_id']
    assert result['build_inputs'] == data['build_inputs']
    assert Path(result['spike_library']).read_bytes() == b'static library'
    assert bundle.digest(Path(result['spike_library'])) == result['spike_library_sha256']
