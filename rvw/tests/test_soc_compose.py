import json
import struct
from pathlib import Path
import pytest
from rvw.soc.compose import compose

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def setup(tmp_path):
    spec = json.loads((ROOT/'SpinalSoc/examples/compose.json').read_text())
    (tmp_path/'soc.json').write_text((ROOT/'SpinalSoc/examples/soc.json').read_text())
    p = tmp_path/'compose.json'
    p.write_text(json.dumps(spec))
    return p, spec


def test_compose(tmp_path):
    p, _ = setup(tmp_path)
    result = compose(p, tmp_path/'out')
    text = (tmp_path/'out/ComposedSoc.scala').read_text()
    assert result['status'] == 'generated'
    assert 'new rvwsoc.IdleCore()' in text
    assert 'new WordMemory(12, 1024, false, Seq())' in text
    assert 'Fabric.connect(core.bus' in text
    assert 'core.interrupts(7) := False' in text
    assert (tmp_path/'out/registers.svd').exists()
    with pytest.raises(ValueError, match='must be new'):
        compose(p, tmp_path/'out')


@pytest.mark.parametrize('change,match', [
    ({'devices': {}}, 'every region'),
    ({'core': {'class': 'bad;code', 'bus': 'apb3'}}, 'Scala'),
    ({'core': {'class': 'Good', 'bus': 'unknown'}}, 'core bus'),
    ({'clock_hz': 0}, 'clock_hz'),
])
def test_refuse(tmp_path, change, match):
    p, spec = setup(tmp_path)
    spec.update(change)
    p.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match=match):
        compose(p, tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_elf_preload(tmp_path):
    p, _ = setup(tmp_path)
    ident = b'\x7fELF\x01\x01\x01' + bytes(9)
    header = struct.pack('<16sHHIIIIIHHHHHH', ident, 2, 243, 1, 0x80000000, 52, 0, 0, 52, 32, 1, 0, 0, 0)
    phdr = struct.pack('<IIIIIIII', 1, 84, 0x80000000, 0x80000000, 4, 8, 5, 4)
    elf = tmp_path/'program.elf'
    elf.write_bytes(header + phdr + b'\x13\0\0\0')
    compose(p, tmp_path/'out', elf)
    assert 'BigInt("13",16)' in (tmp_path/'out/ComposedSoc.scala').read_text()
    elf.write_bytes(header + phdr[:-1])
    with pytest.raises(ValueError, match='truncated'):
        compose(p, tmp_path/'bad', elf)


def test_mcp(tmp_path):
    from rvw.soc.commands.compose import mcp_tools
    p, _ = setup(tmp_path)
    tool = mcp_tools()[0]
    assert tool.handler(source=str(p), out=str(tmp_path/'out'))['status'] == 'generated'


def test_pin_and_irq_binders(tmp_path):
    from rvw.soc.peripherals import peripheral
    p, spec = setup(tmp_path)
    obj = json.loads((tmp_path/'soc.json').read_text())
    device = peripheral('clint','clint',0x2000000)
    obj['regions'].append(device['region'])
    obj['interrupts'] = [dict(name='soft',region='clint',register='msip',cause=3)]
    (tmp_path/'soc.json').write_text(json.dumps(obj))
    spec['devices']['clint'] = dict(device['binder'], irq={'soft':'softwareIrq'}, exports=['softwareIrq'])
    p.write_text(json.dumps(spec))
    compose(p,tmp_path/'out')
    text=(tmp_path/'out/ComposedSoc.scala').read_text()
    assert 'core.interrupts(3) := clint.io.softwareIrq' in text
    assert 'clint.io.softwareIrq.toIo()' in text


@pytest.mark.parametrize('bus', ['axi4', 'axi4-lite', 'tilelink'])
def test_byte_bus(tmp_path, bus):
    p, spec = setup(tmp_path)
    spec['core']['bus'] = bus
    p.write_text(json.dumps(spec))
    result = compose(p, tmp_path/'out')
    text = (tmp_path/'out/ComposedSoc.scala').read_text()
    assert 'BusIngress(core.bus)' in text
    assert 'byteWrites = true' in text
    assert result['profile'] == bus + '-rv32-byte'


def test_domain_binding(tmp_path):
    p, spec = setup(tmp_path)
    spec['domains'] = {'slow': {'clock_hz': 10000000, 'reset': 'async_high'}}
    spec['devices']['ram']['domain'] = 'slow'
    p.write_text(json.dumps(spec))
    compose(p, tmp_path/'out')
    text = (tmp_path/'out/ComposedSoc.scala').read_text()
    assert 'new ClockingArea(slow_domain)' in text
    assert 'BusClockCrossing(ram_crossing, slow_domain)' in text
    assert 'val ram = ram_area.device' in text
    spec['devices']['ram']['domain'] = 'missing'
    p.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match='unknown domain'):
        compose(p, tmp_path/'bad')


def test_device_clock_export(tmp_path):
    from rvw.soc.software import board_dts
    from rvw.soc.model import load
    p, spec = setup(tmp_path)
    spec['domains'] = {'slow': {'clock_hz': 10000000, 'reset': 'sync_high'}}
    from rvw.soc.peripherals import peripheral
    obj = json.loads((tmp_path/'soc.json').read_text())
    for kind in ('clint', 'uart16550'):
        device = peripheral(kind, kind, 0x2000000 if kind == 'clint' else 0x10000000)
        obj['regions'].append(device['region'])
        spec['devices'][kind] = dict(device['binder'], domain='slow')
    (tmp_path/'soc.json').write_text(json.dumps(obj))
    text = board_dts(load(tmp_path/'soc.json'), spec)
    assert 'timebase-frequency = <10000000>' in text
    assert 'clock-frequency = <10000000>' in text


@pytest.mark.parametrize('domains', [[], {'bad-name': {}}, {'core': {}}, {'slow': {'clock_hz': 0, 'reset': 'sync_high'}}])
def test_invalid_domains(tmp_path, domains):
    p, spec = setup(tmp_path)
    spec['domains'] = domains
    p.write_text(json.dumps(spec))
    with pytest.raises(ValueError):
        compose(p, tmp_path/'out')
    assert not (tmp_path/'out').exists()
