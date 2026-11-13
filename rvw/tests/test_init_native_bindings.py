import json
import pytest
from rvw.init.native_bindings import files, security
from rvw.init.mapped import parse_bus
from rvw.sec.rtl import load

pytestmark = pytest.mark.fast


def core():
    return dict(reset_pc='0x80000000', core='testcore', xlen=32, isa='rv32im', top=dict(kind='spinal', **{'class':'Example'}),
                rvfi=dict(prefix='io_rvfi_'), constants={}, ram=dict(base='0x80000000', size='0x10000'),
                buses=[parse_bus('mem:req-rsp:cmd_valid=req,cmd_ready=ready,address=addr,write=wr,wdata=data,mask=mask,rsp_valid=rsp,rdata=rdata')])


def test_security_scaffold_uses_bus_roles(tmp_path):
    result = security(core())
    for name, text in result.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    b = load(tmp_path/'rvw/sec/core.json')
    assert b['buses'][0]['cmd_address'] == 'addr'
    assert b['buses'][0]['rsp_data'] == 'rdata'
    assert b['retire']['prefix'] == 'io_rvfi_'
    assert b['rtl'][0] == tmp_path/'rvw/out/export/core.v'
    assert b['march'] == 'rv32im'
    pair = json.loads(result['rvw/sec/constant-time.json'])
    assert pair['secrets'][0] != pair['secrets'][1]


def test_export_uses_simulation_elaboration():
    result = files(core())
    assert 'adapter.elaborate(ModelKey(map.config)' in result['rvw/src/main/scala/RvwExport.scala']
    assert 'sbt-testcore' in result['rvw/export-rtl.sh']


def test_security_does_not_guess_other_protocol_or_reset():
    c=core(); c['buses'][0]['protocol']='valid-ready'
    assert security(c) == {}
    c=core(); c['top']['reset_active']='low'
    assert security(c) == {}


def test_security_missing_field_is_named(tmp_path):
    p=tmp_path/'binding.json'
    p.write_text('{"schema":"rvw.sec-core/1"}')
    with pytest.raises(ValueError, match='binding needs rtl'):
        load(p)

