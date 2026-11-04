import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('install_verible', Path(__file__).parents[2] / 'scripts/install-verible.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


@pytest.mark.parametrize('system,machine,expected', [
    ('Darwin','arm64','macOS'), ('Darwin','x86_64','macOS'),
    ('Linux','aarch64','linux-static-arm64'), ('Linux','x86_64','linux-static-x86_64')])
def test_archive_selection(system, machine, expected):
    assert installer.target(system, machine) == expected
    assert len(installer.CHECKSUMS[expected]) == 64


def test_unsupported():
    with pytest.raises(ValueError, match='No pinned'):
        installer.target('Linux', 'riscv64')


def test_checksum_before_mutation(tmp_path):
    with pytest.raises(ValueError, match='checksum'):
        installer.install(tmp_path, b'corrupt archive')
    assert not (tmp_path / '.tools').exists()


def test_dry_run_with_lint():
    from test_install_script import invoke
    r = invoke('--with-lint', '--dry-run')
    assert r.returncode == 0, r.stderr
    assert 'install-verible.py' in r.stdout
