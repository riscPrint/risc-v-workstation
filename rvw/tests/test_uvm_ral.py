import json
from pathlib import Path
import pytest
from rvw.sim.ral import generate

ROOT = Path(__file__).resolve().parents[2]


def test_map_addresses_and_widths():
    source = ROOT / 'examples/boom/soc.json'
    text = generate(source)
    assert text == generate(source)
    assert 'super.new(name,64,UVM_NO_COVERAGE)' in text
    assert "64'h2004000" in text
    assert 'lock_model();' in text
    assert 'UVM_LITTLE_ENDIAN' in text


@pytest.mark.parametrize('access,read,write,policy', [
    ('r','none','normal','RO'), ('w','none','normal','WO'),
    ('rw','none','normal','RW'), ('r','clear','normal','RC'),
    ('rw','none','one_to_clear','W1C')])
def test_policies(tmp_path, access, read, write, policy):
    obj = json.loads((ROOT / 'examples/boom/soc.json').read_text())
    reg = obj['regions'][1]['registers'][0]
    reg.update(access=access, read_action=read, write_action=write)
    path = tmp_path / 'map.json'
    path.write_text(json.dumps(obj))
    assert f'"{policy}"' in generate(path)


def test_refuse_unrepresented_side_effect(tmp_path):
    obj = json.loads((ROOT / 'examples/boom/soc.json').read_text())
    obj['regions'][1]['registers'][0].update(read_action='clear',write_action='one_to_clear')
    path = tmp_path / 'map.json'
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='combined'):
        generate(path)


def test_flat_symbol_collision_is_rejected(tmp_path):
    obj=json.loads((ROOT/'examples/vexriscv/soc.json').read_text())
    for name,register,base in [('a_b','c',0),('a','b_c',16)]:
        obj['regions'].append(dict(name=name,kind='mmio',base=base,size=16,permissions='rw',
            cacheable=False,registers=[dict(name=register,offset=0,width=32,access='rw',reset=0,
                                          read_action='none',write_action='normal')]))
    path=tmp_path/'map.json'
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='duplicate SystemVerilog'):
        generate(path)


def test_cli_refuses_overwrite(tmp_path):
    from rvw.cli import main
    output=tmp_path/'ral.sv'
    output.write_text('keep')
    assert main(['regress','uvm-ral','--map',str(ROOT/'examples/boom/soc.json'),'--out',str(output)])==2
    assert output.read_text()=='keep'
