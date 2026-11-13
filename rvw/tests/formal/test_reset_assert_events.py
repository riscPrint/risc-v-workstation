"""Do not accept reset-clocked checks before their event semantics qualify."""
import json
import shutil

import pytest

from rvw.formal import common


@pytest.mark.fast
@pytest.mark.parametrize('polarity',['1','0'])
def test_reset_trigger_stays_outside_primary_clock_model(tmp_path,polarity):
    path=tmp_path/'probe.json'
    path.write_text(json.dumps({'modules':{'dut':{
        'ports':{'clk':{'direction':'input','bits':[2]},
                 'reset':{'direction':'input','bits':[3]}},
        'netnames':{'reset':{'bits':[3]}},
        'cells':{'property':{'type':'$check',
                            'parameters':{'TRG_ENABLE':'1','TRG_POLARITY':polarity,
                                          'FLAVOR':'assert'},
                            'connections':{'TRG':[3]}}}}}}))
    assert common.clock_problems(path,'dut','clk')


@pytest.mark.slow
@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','sby','yices-smt2')),
                    reason='native formal tools')
@pytest.mark.parametrize('condition',['reset','!reset'])
def test_native_reset_assertion_is_qualified_or_refused(tmp_path,condition,capsys):
    from rvw.cli import main
    rtl=tmp_path/'dut.sv'
    rtl.write_text(f'module dut(input clk,reset,output y);assign y=reset;always @(posedge reset) assert({condition});endmodule')
    out=tmp_path/'proof'
    try:
        rc=main(['formal','bmc','--verilog',str(rtl),'--top','dut','--clock','clk','--reset','reset',
                 '--event-model','--async-reset','--free-reset','--clock-schedule','clk=01',
                 '--depth','8','--timeout','30','--out',str(out)])
    except SystemExit as error:
        assert error.code==2
        assert 'TRG is reset' in capsys.readouterr().err
        assert not (out/'result.json').exists()
        return
    # A future qualified implementation must agree with actual reset-edge
    # semantics. Relaxing the guard alone reversed these two controls.
    report=json.loads((out/'result.json').read_text())
    good=condition=='reset'
    assert rc==(0 if good else 1)
    assert report['status']==('pass' if good else 'fail')
    assert report['assertions']>=1
