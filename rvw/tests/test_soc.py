import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from rvw.soc.model import generate, load
from rvw.cosim.platform import Platform

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('core,original', [('boom', 'rvw/src/rvw/cosim/configs/boom.json'), ('vexriscv', 'examples/vexriscv/rvw/platform.json')])
def test_examples(tmp_path, core, original):
    source = ROOT / 'examples' / core / 'soc.json'
    generate(source, tmp_path)
    assert Platform.load(None, tmp_path / 'platform.json') == Platform.load(None, ROOT / original)
    assert Platform.load(None, tmp_path / 'platform.json').name == core
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    generate(source, tmp_path)
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert '0x80000000' in (tmp_path / 'memory.ld').read_text()
    assert 'RVW_RAM_BASE' in (tmp_path / 'soc.h').read_text()
    assert ET.parse(tmp_path / 'registers.svd').getroot().tag == 'device'
    if core == 'boom':
        assert 'RVW_CLINT_MTIMECMP_ADDR UINT64_C(0x2004000)' in (tmp_path / 'soc.h').read_text()


@pytest.mark.parametrize('change', [
    lambda x: x.update(schema='bad'),
    lambda x: x['regions'][1].update(base='0x80000000'),
    lambda x: x['regions'][0].update(size='0x1234'),
    lambda x: x['regions'][0].update(base='0x80000001'),
    lambda x: x['regions'][1]['registers'][0].update(offset='0x10000'),
    lambda x: x['regions'][1]['registers'][0].update(width=True),
    lambda x: x['regions'][1]['registers'][0].update(reset='0x100000000'),
    lambda x: x['regions'][1]['registers'][1].update(offset=0),
    lambda x: x['interrupts'][0].update(register='absent'),
    lambda x: x.update(unknown=True),
])
def test_invalid(tmp_path, change):
    obj = json.loads((ROOT / 'examples/boom/soc.json').read_text())
    change(obj)
    src = tmp_path / 'soc.json'
    src.write_text(json.dumps(obj))
    with pytest.raises(ValueError):
        load(src)


def test_export_side_effects(tmp_path):
    obj = json.loads((ROOT / 'examples/boom/soc.json').read_text())
    obj['regions'][1]['registers'][0].update(read_action='clear', write_action='one_to_clear')
    src = tmp_path / 'soc.json'
    src.write_text(json.dumps(obj))
    generate(src, tmp_path / 'out')
    reg = ET.parse(tmp_path / 'out/registers.svd').find('.//register')
    assert reg.findtext('readAction') == 'clear'
    assert reg.findtext('modifiedWriteValues') == 'oneToClear'
