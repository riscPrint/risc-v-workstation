"""The narrow native reader must preserve shared-parser rejection and timing."""
import json
import shutil
from dataclasses import asdict, replace
import pytest
from rvw.ooo import native
from rvw.ooo.core import Config, _instructions, simulate, run
from test_ooo import trace

pytestmark = pytest.mark.fast


@pytest.fixture
def setup(tmp_path, monkeypatch):
    if not shutil.which('cc'):
        pytest.skip('host C compiler absent')
    monkeypatch.setenv('RVW_OOO_NATIVE', str(native.build(tmp_path/'libooo.so')))
    c = Config(4,16,4,32,4,16,8,8,4, dict(zip(native.KINDS,[1,3,12,1,1,1,1])))
    t = tmp_path/'trace.jsonl'
    trace(t)
    return c,t


@pytest.mark.parametrize('components', [{}, {'branch': {'model':'bimodal','entries':64},
                                           'btb': {'entries':16,'ways':2}}])
def test_public_native_reader_matches_python(setup, tmp_path, components):
    c,t = setup
    c = replace(c,components=components)
    p = tmp_path/'config.json'
    p.write_text(json.dumps(asdict(c)))
    rows = [json.loads(line) for line in t.read_text().splitlines()]
    for i,r in enumerate(rows[1:-1]):
        r.update(insn='0x63' if i%2 else '0x13',pc='0x100',pc_next='0x100' if i%2 else '0x104')
    t.write_text('\n'.join(map(json.dumps,rows))+'\n')
    actual = run(p,t)
    assert actual['trace_reader'] == 'native-c2'
    expected = simulate(_instructions(t.read_bytes()),c,backend='python')
    for key in ('cycles','instret','ipc','events','max_occupancy','topdown'):
        assert actual[key] == expected[key]


@pytest.mark.parametrize('change', [
    {'order':2}, {'cycle':-1}, {'rs1':32}, {'trap':True},
    {'mem_rmask':5}, {'pc':'0X1'}, {'insn':'0x100000000'},
    {'rd':True}, {'intr':0}, {'hart':0}, {'pc':'0x10000000000000000'},
])
def test_invalid_row_falls_back_to_shared_rejection(setup, change):
    c,t=setup
    rows=[json.loads(line) for line in t.read_text().splitlines()]
    rows[1].update(change)
    data=('\n'.join(map(json.dumps,rows))+'\n').encode()
    assert native.parse_c2(data,c) is None
    with pytest.raises(ValueError):
        _instructions(data)


def test_extensions_and_missing_end_fall_back(setup):
    c,t=setup
    data=t.read_bytes()
    assert native.parse_c2(b'\n'.join(data.splitlines()[:-1]),c) is None
    rows=[json.loads(line) for line in data.splitlines()]
    rows[1]['csr_state']={}
    data=('\n'.join(map(json.dumps,rows))+'\n').encode()
    assert native.parse_c2(data,c) is None
    assert len(_instructions(data)) == 4


@pytest.mark.parametrize('xlen', [32,64])
def test_compressed_memory_and_dependencies(setup, xlen):
    c,t=setup
    c=replace(c,components={'memory':{'dram_latency':10,'l1d':{'size_kib':1,'ways':1,'latency':2}}})
    rows=[json.loads(line) for line in t.read_text().splitlines()]
    rows[0].update(xlen=xlen,isa=f'rv{xlen}imc')
    for i,row in enumerate(rows[1:-1]):
        row.update(insn=('0x4082','0x2083','0x20a023','0x8506')[i],rd=(1,1,0,10)[i],pc=hex(0x100+4*i),pc_next=hex(0x104+4*i))
        if i<3:
            row.update(mem_addr='0x3e',mem_rmask=15 if i<2 else 0,mem_wmask=15 if i==2 else 0)
    data=('\n'.join(map(json.dumps,rows))+'\n').encode()
    packed=native.parse_c2(data,c)
    assert packed is not None
    actual=native.simulate(packed,c,10000)
    expected=simulate(_instructions(data),c,backend='python')
    expected.pop('backend')
    assert actual==expected
