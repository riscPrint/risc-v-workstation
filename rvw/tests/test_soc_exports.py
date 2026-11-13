import json
from pathlib import Path
import pytest
from rvw.soc.exports import export
from rvw.soc.importer import import_ipxact
from rvw.soc.model import load

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]


def test_roundtrip(tmp_path):
    source=ROOT/'SpinalSoc/examples/stub/soc.json'
    export(source,tmp_path/'registers.xml')
    import_ipxact(tmp_path/'registers.xml',source,tmp_path/'soc.json')
    assert load(tmp_path/'soc.json')==load(source)


def test_scaffold(tmp_path):
    from rvw.soc.scaffold import new
    from rvw.soc.compose import compose
    dest=tmp_path/'board'
    assert new('my_board',dest)['core']=='idle_wrapper'
    compose(dest/'compose.json',dest/'generated')
    assert 'new board.ProjectCore()' in (dest/'generated/ComposedSoc.scala').read_text()
    assert load(dest/'soc.json')['name']=='my_board'
    with pytest.raises(ValueError,match='must be new'):new('my_board',dest)


def test_software_descriptions():
    from rvw.soc.software import board_dts,linker
    obj=load(ROOT/'SpinalSoc/examples/stub/soc.json')
    spec=json.loads((ROOT/'SpinalSoc/examples/stub/compose.json').read_text())
    tree=board_dts(obj,spec)
    assert 'riscv,cpu-intc' in tree
    assert 'interrupts-extended = <&rvw_cpu_intc 7>' in tree
    assert 'riscv,ndev = <7>' in tree
    assert 'rvw,uart16550-subset' in tree
    assert 'ENTRY(_start)' in linker(obj)
    assert '.bss (NOLOAD)' in linker(obj)


def test_side_effect_roundtrip(tmp_path):
    source=ROOT/'SpinalSoc/examples/stub/soc.json'
    obj=json.loads(source.read_text())
    register=obj['regions'][-1]['registers'][0]
    register.update(read_action='clear',write_action='one_to_clear')
    src=tmp_path/'input.json';src.write_text(json.dumps(obj))
    export(src,tmp_path/'registers.xml')
    import_ipxact(tmp_path/'registers.xml',src,tmp_path/'output.json')
    assert load(tmp_path/'output.json')==load(src)
