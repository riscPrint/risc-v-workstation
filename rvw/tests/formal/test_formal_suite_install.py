import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('formal_suite_install', ROOT / 'scripts/install-formal-suite.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_bundle_is_external_and_checksum_pinned(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mod.shutil, 'which', lambda _: None)
    monkeypatch.setattr(mod.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(mod.platform, 'machine', lambda: 'arm64')
    out = tmp_path / 'absent'
    assert mod.install('pono', out, dry=True) == out / 'bin'
    text = capsys.readouterr().out
    assert mod.VERSION in text and mod.CHECKSUMS['darwin-arm64'] in text
    assert text.index('Verify SHA-256') < text.index('tar -xzf')
    assert not out.exists()
    with pytest.raises(ValueError, match='outside'):
        mod.install('pono', ROOT / '.tools', dry=True)


def test_existing_engine_is_not_a_qualification_claim(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mod.shutil, 'which', lambda _: '/native/bin/cvc5')
    assert mod.install('cvc5', tmp_path) == Path('/native/bin')
    text = capsys.readouterr().out
    assert 'PRESENT' in text and 'qualification is separate' in text
    assert 'curl' not in text


def test_missing_engine_in_cached_bundle_is_not_reported_installed(tmp_path, monkeypatch):
    monkeypatch.setattr(mod.shutil, 'which', lambda _: None)
    monkeypatch.setattr(mod.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(mod.platform, 'machine', lambda: 'arm64')
    (tmp_path / 'oss-cad-suite').mkdir()
    with pytest.raises(ValueError, match='absent from the cached pinned'):
        mod.install('suprove', tmp_path)


def test_shell_accepts_native_engine_flags(tmp_path):
    import subprocess
    r = subprocess.run(['bash', str(ROOT / 'scripts/install.sh'), '--dry-run', '--prefix', str(tmp_path / 'new'),
                        '--with-pono', '--with-avy', '--with-suprove', '--with-bitwuzla', '--with-cvc5', '--with-yices'],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for engine in mod.ENGINES:
        assert 'install-formal-suite.py ' + engine in r.stdout


def test_cached_suite_publishes_selected_backend_and_trace_dependency(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(mod.shutil, 'which', lambda _: None)
    suite_bin = tmp_path / 'oss-cad-suite/bin'
    suite_bin.mkdir(parents=True)
    for name in ('pono', 'btorsim', 'yosys'):
        tool = suite_bin / name
        tool.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
        tool.chmod(0o755)
    bindir = mod.install('pono', tmp_path)
    assert sorted(p.name for p in bindir.iterdir()) == ['btorsim', 'pono']
    r = subprocess.run([str(bindir / 'pono'), '--argument', 'two words'], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.splitlines() == ['--argument', 'two words']
