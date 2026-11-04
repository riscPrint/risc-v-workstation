"""Targeted tests for the SpinalChecks register import boundary."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2] / 'SpinalChecks'
spec = importlib.util.spec_from_file_location('checks_map', ROOT / 'scripts/import-map.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_ipxact_masks():
    text = module.convert(ROOT / 'src/test/maps/status.xml', 'ipxact')
    assert 'status.address=16\n' in text
    assert 'status.reset=12\n' in text
    assert 'status.writeMask=3\n' in text
    assert 'status.w1cMask=4\n' in text
    assert 'status.readClearMask=8\n' in text


def test_systemrdl_matches_ipxact():
    pytest.importorskip('systemrdl')
    rdl = module.systemrdl(ROOT / 'src/test/maps/status.rdl')
    xml = module.ipxact(ROOT / 'src/test/maps/status.xml')
    assert rdl[0][1] == xml[0][1]


@pytest.mark.parametrize('before,after', [
    ('oneToClear', 'oneToSet'),
    ('<readAction>clear</readAction>', '<readAction>modify</readAction>'),
    ('<bitOffset>2</bitOffset>', '<bitOffset>1</bitOffset>'),
    ('<size>32</size>', '<size>2</size>'),
])
def test_refuse_unsupported_semantics(tmp_path, before, after):
    path = tmp_path / 'bad.xml'
    path.write_text((ROOT / 'src/test/maps/status.xml').read_text().replace(before, after))
    with pytest.raises(ValueError):
        module.ipxact(path)
