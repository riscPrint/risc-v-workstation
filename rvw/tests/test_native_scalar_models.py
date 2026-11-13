"""Native reset, seeded input and state updates through both model engines."""
import os
from pathlib import Path
import random
import shutil
import pytest
from rvw.sim.native_models import Model


def test_two_native_engines_observe_seeded_register_updates(tmp_path):
    circt=os.environ.get('RVW_CIRCT')
    if not circt or not (Path(circt)/'bin/arcilator').is_file():pytest.skip('pinned CIRCT install required')
    if not shutil.which('verilator'):pytest.skip('Verilator required')
    rtl=tmp_path/'small.sv'
    rtl.write_text('''module Small(input clk,reset,valid,input [31:0] data,output reg [31:0] value);
    always @(posedge clk) if(reset) value<=0; else if(valid) value<=value+data;
    endmodule''')
    ports=dict(clk=('input',1),reset=('input',1),valid=('input',1),data=('input',32),value=('output',32))
    sequences=[]
    for backend in ('arcilator','verilator'):
        m=Model(backend,[rtl],'Small',ports,tmp_path/backend,circt=circt)
        try:
            for n,v in dict(clk=0,reset=1,valid=0,data=0).items():m.write(n,v)
            m.eval();m.write('clk',1);m.eval();m.write('clk',0);m.eval();m.write('reset',0)
            expected=0;observed=[];rng=random.Random(17)
            for _ in range(40):
                valid=rng.randrange(2);data=rng.randrange(1<<32)
                m.write('valid',valid);m.write('data',data);m.eval()
                m.write('clk',1);m.eval();m.write('clk',0);m.eval()
                expected=(expected+valid*data)&0xffffffff
                observed.append(m.read('value'))
                assert observed[-1]==expected
            sequences.append(observed)
            with pytest.raises(ValueError):m.write('value',1)
        finally:m.close()
    assert sequences[0]==sequences[1]


def test_refuse_unknown_backend_before_build(tmp_path):
    with pytest.raises(ValueError,match='unsupported'):
        Model('unknown',[],'Small',{},tmp_path/'out')
    assert not (tmp_path/'out').exists()
