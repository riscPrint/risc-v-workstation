import pytest
from rvw.soc.binding_help import diagnose, HELP
from rvw.soc.verify import verify, table
from test_soc_verify import MAP

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('kind', list(HELP))
def test_each_kind_names_specific_missing_bindings(kind):
    d=diagnose(kind,{},dict(regions=[dict(registers=[])]))
    assert d['missing_bindings']
    assert all(d['binding_help'][key] for key in d['missing_bindings'])
    assert all(key.startswith(('checks.'+kind+'.','map.')) for key in d['missing_bindings'])


def test_existing_command_needs_evidence_not_another_binding():
    d=diagnose('protocol',dict(command=['native-consumer']),dict(regions=[]))
    assert d['missing_bindings']==[] and 'fresh evidence' in d['needed_evidence']


def test_native_register_binding_is_complete():
    assert diagnose('registers',dict(capture='capture.jsonl',write_read=['uart.scratch']),dict(regions=[dict(registers=[{}])]))['missing_bindings']==[]


def test_verify_exposes_help_without_promoting_generation(tmp_path):
    result=verify(MAP,tmp_path/'out')
    assert result['status']=='inconclusive'
    assert 'missing checks.decode.classpath_file' in table(result)
    for row in result['checks']:
        assert row['result']=='inconclusive' and row['missing_bindings'] and row['binding_help']


def test_composition_consumer_can_use_private_build_lock(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from rvw.soc import uvm_run
    seen=[]
    def generate(source,out,rtl,expected_map=None):
        out.mkdir()
        return dict(scala='verification.scala')
    monkeypatch.setattr(uvm_run,'generate',generate)
    monkeypatch.setattr(uvm_run,'run_group',lambda argv,**kwargs: seen.append(argv) or SimpleNamespace(returncode=1,timed_out=False))
    r=uvm_run.run('project',tmp_path/'native','classpath',lock='sbt-cosim')
    assert not r['ran'] and seen[0][1]=='sbt-cosim'


@pytest.mark.parametrize('width',[8,16])
def test_composed_consumers_accept_subword_registers(tmp_path,width):
    import json
    from rvw.uvm.composed import generate
    from rvw.soc.vip_bench import generate as vip
    model=json.loads(MAP.read_text())
    for region in model['regions']:
        for reg in region['registers']:
            reg['width']=width
            if reg['reset'] is not None:reg['reset']=0
    source=tmp_path/'soc.json';source.write_text(json.dumps(model))
    spec=dict(schema='rvw.soc-compose/1',map='soc.json',clock_hz=50000000,reset='sync_high',
              core=dict(bus='simple',**{'class':'rvwsoc.VerificationCore'}),
              devices={r['name']:dict(type='ram') if r['kind']=='ram' else dict(type='project',**{'class':'rvwsoc.Uart16550'}) for r in model['regions']})
    composition=tmp_path/'compose.json';composition.write_text(json.dumps(spec))
    out=tmp_path/'bench'
    generate(composition,out,out/'dut.v')
    bindings=json.loads((out/'bindings.json').read_text())
    assert bindings['registers']
    assert all(vip(out).values())


@pytest.mark.parametrize('width,expected',[(8,0x78),(16,0x5678),(32,0x12345678)])
def test_subword_frontdoor_preserves_declared_value_width(width,expected):
    import ast,asyncio
    from rvw.uvm.composed import TEST
    tree=ast.parse(TEST)
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Frontdoor')
    namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),'generated-frontdoor','exec'),namespace)
    frontdoor=namespace['Frontdoor'](None,10)
    writes=[]
    async def transfer(address,write=False,data=0):
        if write:writes.append(data)
        return 0x12345678
    frontdoor.transfer=transfer
    assert asyncio.run(frontdoor.read(0,width))==expected
    asyncio.run(frontdoor.write(0,0x12345678,width))
    assert writes==[expected]
