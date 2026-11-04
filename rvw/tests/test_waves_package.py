import importlib.util
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2] / 'SpinalWaves'
spec = importlib.util.spec_from_file_location('waves_package', ROOT / 'scripts/package-source.py')
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)


def test_source_archive(tmp_path):
    a, b = tmp_path / 'a.tar.gz', tmp_path / 'b.tar.gz'
    pkg.package(a)
    pkg.package(b)
    assert a.read_bytes() == b.read_bytes()
    with tarfile.open(a) as tar:
        assert 'SpinalWaves/surfer-tywaves/LICENSE-EUPL-1.2.txt' in tar.getnames()
        assert 'SpinalWaves/third_party/tywaves-rs/LICENSE' in tar.getnames()
        tar.extractall(tmp_path / 'source', filter='data')
    root = tmp_path / 'source/SpinalWaves'
    pkg.verify(root)
    (root / 'surfer-tywaves/Cargo.lock').write_text('changed')
    with pytest.raises(ValueError, match='vendor input changed'):
        pkg.verify(root)


def test_installer(tmp_path):
    import os
    # Use the archive as the standalone build input. Stub Cargo creates only
    # the expected executable, so this does not claim a native build.
    archive = tmp_path / 'source.tar.gz'
    pkg.package(archive)
    with tarfile.open(archive) as tar:
        tar.extractall(tmp_path, filter='data')
    root = tmp_path / 'SpinalWaves'
    stub = tmp_path / 'stub'
    stub.mkdir()
    cargo = stub / 'cargo'
    cargo.write_text('''#!/usr/bin/env python3
import os,sys
from pathlib import Path
with open(os.environ['CARGO_LOG'], 'a') as f: f.write(' '.join(sys.argv[1:])+'\\n')
a=sys.argv
p=Path(a[a.index('--manifest-path')+1]).parent/'target/release/surfer-tywaves'
p.parent.mkdir(parents=True,exist_ok=True)
p.write_text('#!/bin/sh\\nexit 0\\n')
p.chmod(0o755)
''')
    cargo.chmod(0o755)
    log = tmp_path / 'cargo.log'
    subprocess.run(['bash', str(root / 'scripts/install.sh'), '--only', 'surfer', '--copy', '--prefix', str(tmp_path / 'bin')], check=True,
                   env={**os.environ, 'PATH': str(stub)+os.pathsep+os.environ['PATH'], 'CARGO_LOG': str(log)}, capture_output=True)
    assert '--locked' in log.read_text()
    assert '-p surfer-tywaves' in log.read_text()
    assert (tmp_path / 'share/spinalwaves/LICENSE-EUPL-1.2.txt').exists()
    assert (tmp_path / 'share/spinalwaves/source.tar.gz').exists()


def test_macos_app(tmp_path, monkeypatch):
    import plistlib
    app_spec = importlib.util.spec_from_file_location('waves_app', ROOT / 'scripts/package-app.py')
    app_pkg = importlib.util.module_from_spec(app_spec)
    app_spec.loader.exec_module(app_pkg)
    binary = tmp_path / 'viewer'
    binary.write_bytes(b'native viewer fixture')
    notices = tmp_path / 'notices'
    notices.mkdir()
    for name in ('LICENSE-EUPL-1.2.txt', 'vendor-lock.json', 'source.tar.gz'):
        (notices / name).write_text(name)
    calls = []
    monkeypatch.setattr(app_pkg.subprocess, 'run', lambda args, **kw: calls.append((args, kw)))
    app = tmp_path / 'prefix with spaces/SpinalWaves.app'
    app_pkg.package(binary, notices, app, ROOT / 'surfer-tywaves/Cargo.toml')
    contents = app / 'Contents'
    info = plistlib.loads((contents / 'Info.plist').read_bytes())
    assert info['CFBundleIdentifier'] == 'org.riscprint.spinalwaves'
    assert info['CFBundleName'] == 'SpinalWaves'
    assert info['CFBundlePackageType'] == 'APPL'
    assert info['CFBundleShortVersionString'] == '0.3.0'
    assert info['CFBundleVersion'] == '0.3.0'
    assert info['SpinalWavesForkVersion'] == '0.3.0-dev'
    executable = contents / 'MacOS' / info['CFBundleExecutable']
    assert executable.read_bytes() == binary.read_bytes()
    assert executable.stat().st_mode & 0o111
    assert not executable.is_symlink()
    for notice in notices.iterdir():
        assert (contents / 'Resources' / notice.name).read_bytes() == notice.read_bytes()
    assert calls == [(['codesign', '--force', '--sign', '-', str(app)], {'check': True})]
