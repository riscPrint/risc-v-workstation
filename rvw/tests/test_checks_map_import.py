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
    ('<resets><reset><value>0</value></reset></resets>', ''),
    ('<resets><reset><value>0</value></reset></resets>', '<resets><reset><value>0</value><mask>1</mask></reset></resets>'),
    ('<name>device</name>', '<name>device</name><addressUnitBits>16</addressUnitBits>'),
])
def test_refuse_unsupported_semantics(tmp_path, before, after):
    path = tmp_path / 'bad.xml'
    path.write_text((ROOT / 'src/test/maps/status.xml').read_text().replace(before, after))
    with pytest.raises(ValueError):
        module.ipxact(path)


def test_systemrdl_refuses_unmodeled_side_effect(tmp_path):
    pytest.importorskip('systemrdl')
    path = tmp_path / 'bad.rdl'
    path.write_text((ROOT / 'src/test/maps/status.rdl').read_text().replace('onwrite=woclr', 'onwrite=woset'))
    with pytest.raises(ValueError, match='unsupported'):
        module.systemrdl(path)
