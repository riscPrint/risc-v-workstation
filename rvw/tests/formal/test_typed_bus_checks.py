import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.typed_bus_checks import render, CHANNELS

pytestmark = pytest.mark.slow


def fields(kind):
    rows = {}
    for ch in CHANNELS[kind]:
        for field, width in [('valid',1), ('ready',1), ('payload.data',8)]:
            key = ch+'.'+field
            rows[key] = (key.replace('.', '_'), None, None, width, 1, False)
        extra = {}
        if kind.startswith('axi') and ch in ('aw', 'ar'):
            extra['addr'] = 32
            if kind == 'axi4': extra.update(burst=2, len=8, size=3)
        if kind == 'axi_lite4' and ch in ('b', 'r'): extra['resp'] = 2
        if kind == 'tilelink': extra['opcode'] = 3
        for field, width in extra.items():
            key=ch+'.payload.'+field
            rows[key]=(key.replace('.', '_'), None, None, width, 1, False)
    return rows


@pytest.mark.parametrize('kind', CHANNELS)
@pytest.mark.parametrize('bad', [False, True])
def test_native_typed_protocol(tmp_path, kind, bad):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    signals=fields(kind)
    source, ports=render(kind, signals, 'monitor')
    wires=[]
    for key, row in signals.items():
        value=1 if key.endswith(('valid','ready')) else 0
        if bad and key == 'aw.payload.burst': value=3
        if bad and key == 'b.payload.resp': value=1
        if bad and key == 'd.payload.opcode': value=7
        wires.append(f'wire [{row[3]-1}:0] {row[0]}={value};')
    source+='module fixture(input clk); reg reset=1; always @(posedge clk) reset<=0;\n'
    source+='\n'.join(wires)+'\nmonitor dut(.*); endmodule\n'
    (tmp_path/'design.sv').write_text(source)
    (tmp_path/'proof.sby').write_text('''[options]
mode prove
depth 8
[engines]
smtbmc yices
[script]
read -formal design.sv
prep -top fixture
[files]
design.sv
''')
    run=run_group(['nice','-n','10','sby','-f','proof.sby'],cwd=tmp_path,capture=True,timeout=30)
    status=tmp_path/'proof/status'
    assert status.exists(),run.stdout+run.stderr
    assert status.read_text().split()[0] == ('FAIL' if bad else 'PASS'),run.stdout+run.stderr
