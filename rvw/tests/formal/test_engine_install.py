import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('formal_install', ROOT / 'scripts/install-formal-engine.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_sources_stay_external():
    with pytest.raises(ValueError, match='outside'):
        mod.install('ric3', ROOT / '.tools', dry=True)


@pytest.mark.parametrize('engine,revision', [('ric3', mod.RIC3_REV), ('ebmc', mod.EBMC_REV)])
def test_dry_run_pins_native_sources(tmp_path, capsys, engine, revision):
    mod.install(engine, tmp_path / 'absent', dry=True)
    text = capsys.readouterr().out
    assert revision in text and 'nice -n 10' in text
    assert not (tmp_path / 'absent').exists()


def test_failed_lock_preflight_does_not_create_environment(tmp_path):
    import os
    import shlex
    import subprocess
    marker = tmp_path / 'venv-called'
    uv = tmp_path / 'uv'
    uv.write_text('#!/bin/sh\ncase "$1" in\n'
                  '--version) echo "uv 0.13.6" ;;\n'
                  'lock|sync) exit 42 ;;\n'
                  'venv) touch ' + shlex.quote(str(marker)) + ' ;;\n'
                  'esac\n')
    uv.chmod(0o755)
    result = subprocess.run(['bash', str(ROOT / 'scripts/install.sh'), '--yes'],
        cwd=ROOT, env={**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH']},
        text=True, capture_output=True, timeout=20)
    assert result.returncode == 42, (result.stdout, result.stderr)
    assert not marker.exists(), result.stdout


@pytest.fixture
def tmp_path(external_tmp_path):
    return external_tmp_path
