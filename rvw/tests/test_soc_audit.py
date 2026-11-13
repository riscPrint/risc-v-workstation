import json
from pathlib import Path
import pytest
from lint_builder import Builder
from rvw.soc.audit import audit

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]


def test_all_ports_required(tmp_path):
    b=Builder(tmp_path/'d.db');b.domain(1,clock='clk');b.sig('clk',direction='in',role='clock');b.reg('q',1)
    ports={}
    for pin,width in [('PADDR',32),('PSEL',1),('PENABLE',1),('PWRITE',1),('PWDATA',32),('PRDATA',32),('PREADY',1)]:
        b.sig(pin,width=width,direction='in');ports[pin]=pin
    ram_ports=dict(ports)
    b.sig('RAM_ADDR',width=12,direction='in');ram_ports['PADDR']='RAM_ADDR'
    db=b.done()
    spec=dict(interrupts={},bus_ports={'core.bus':ports,'ram.io.bus':ram_ports})
    src=tmp_path/'bindings.json';src.write_text(json.dumps(spec))
    result=audit(ROOT/'SpinalSoc/examples/soc.json',db,src,tmp_path/'out.json')
    assert result['status']=='inconclusive'
    assert result['decode']['map_disjoint'] is True
    assert result['decode']['rtl_proof']=='not_run'
    assert len(result['bus_ports'])==2
    del spec['bus_ports']['ram.io.bus'];src.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match='every fabric'):audit(ROOT/'SpinalSoc/examples/soc.json',db,src,tmp_path/'bad.json')


def test_rv64_core_keeps_32_bit_apb_data(tmp_path):
    b = Builder(tmp_path/'d.db')
    b.domain(1, clock='clk')
    b.sig('clk', direction='in', role='clock')
    b.reg('q', 1)
    ports = {}
    for pin, width in [('PADDR',32), ('PSEL',1), ('PENABLE',1), ('PWRITE',1),
                       ('PWDATA',32), ('PRDATA',32), ('PREADY',1)]:
        b.sig(pin, width=width, direction='in')
        ports[pin] = pin
    ram_ports = dict(ports)
    b.sig('RAM_ADDR', width=12, direction='in')
    ram_ports['PADDR'] = 'RAM_ADDR'
    db = b.done()
    obj = json.loads((ROOT/'SpinalSoc/examples/soc.json').read_text())
    obj['platform'].update(xlen=64, isa='rv64im_zicsr_zifencei',
                           reference_isa='rv64im_zicsr_zifencei_zicntr_zihpm')
    model = tmp_path/'map.json'
    model.write_text(json.dumps(obj))
    bindings = tmp_path/'bindings.json'
    bindings.write_text(json.dumps(dict(interrupts={}, bus_ports={
        'core.bus': ports, 'ram.io.bus': ram_ports})))
    assert audit(model, db, bindings, tmp_path/'out.json')['status'] == 'inconclusive'
