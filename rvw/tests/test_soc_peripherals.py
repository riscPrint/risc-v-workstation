import copy
import json
from pathlib import Path
import pytest
from rvw.soc.peripherals import peripheral
from rvw.soc.model import load, svd

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('kind',['clint','plic','gpio','timer','finisher','uart16550','spi','i2c','watchdog'])
def test_maps(tmp_path,kind):
    obj = json.loads((ROOT/'SpinalSoc/examples/soc.json').read_text())
    result = peripheral(kind,kind,0x10000000)
    obj['regions'].append(result['region'])
    p=tmp_path/'soc.json'
    p.write_text(json.dumps(obj))
    mapped=load(p)
    assert f'<name>{kind}</name>' in svd(mapped)
    assert result['binder']['class'].startswith('rvwsoc.')
    regs={r['name']:r for r in result['region']['registers']}
    if kind=='clint':
        assert regs['mtime_low']['offset']==0xbff8
    if kind=='plic':
        assert regs['claim_complete']['reset'] is None


def test_alignment():
    with pytest.raises(ValueError,match='align'):
        peripheral('plic','plic',1)


def test_watchdog_side_effect_map():
    result = peripheral('watchdog','wdt',0x10000000)
    regs = {r['name']:r for r in result['region']['registers']}
    assert regs['status']['write_action'] == 'one_to_clear'
    assert regs['status']['reset'] is None
    assert regs['service']['access'] == 'w'
    assert regs['count']['access'] == 'r'
