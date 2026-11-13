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
