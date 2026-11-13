"""Full UART map and composer binding checks. Serial behavior uses native VIP."""
import json
from pathlib import Path
import pytest
from rvw.soc.peripherals import peripheral
from rvw.soc.model import load
from rvw.soc.compose import compose

pytestmark = pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]


def test_full_uart_map_and_pins(tmp_path):
    profile=peripheral('uart16550-full','uart',0x10000000)
    assert profile['binder']['class']=='rvwsoc.Uart16550Full'
    assert profile['binder']['exports']==['serial','modem']
    registers={r['name']:r for r in profile['region']['registers']}
    assert registers['lcr']['reset']==0 and registers['mcr']['offset']==16
    assert registers['msr']['offset']==24 and registers['msr']['reset'] is None
    assert registers['iir_fcr']['reset'] is None
    assert peripheral('uart16550','legacy',0x10000000)['region']['registers'][3]['reset']==3
    model=json.loads((ROOT/'SpinalSoc/examples/soc.json').read_text())
    model['regions'].append(profile['region'])
    source=tmp_path/'map.json';source.write_text(json.dumps(model))
    load(source)
    spec=dict(schema='rvw.soc-compose/1',map='map.json',core={'class':'rvwsoc.IdleCore','bus':'apb3'},
              clock_hz=50000000,reset='async_high',devices={'ram':dict(type='ram'),'uart':profile['binder']})
    plan=tmp_path/'compose.json';plan.write_text(json.dumps(spec))
    compose(plan,tmp_path/'generated')
    scala=(tmp_path/'generated/ComposedSoc.scala').read_text()
    assert 'new rvwsoc.Uart16550Full' in scala
    assert 'uart_modem' in scala and 'uart_serial' in scala


def test_full_uart_device_tree(tmp_path):
    from rvw.soc.software import board_dts
    profile = peripheral('uart16550-full', 'uart', 0x10000000)
    obj = json.loads((ROOT/'SpinalSoc/examples/soc.json').read_text())
    obj['regions'].append(profile['region'])
    spec = dict(clock_hz=50000000, domains={'slow': {'clock_hz': 10000000}},
                devices={'ram': {'type': 'ram'}, 'uart': dict(profile['binder'], domain='slow')})
    source = tmp_path/'soc.json'
    source.write_text(json.dumps(obj))
    tree = board_dts(load(source), spec)
    assert 'compatible = "ns16550a";' in tree
    assert 'reg-shift = <2>;' in tree
    assert 'reg-io-width = <4>;' in tree
    assert 'clock-frequency = <10000000>;' in tree
