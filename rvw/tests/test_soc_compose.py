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
    ({'core': {'class': 'Good', 'bus': 'axi4'}}, 'APB3'),
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
