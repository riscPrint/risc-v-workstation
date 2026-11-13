"""Conservative paths are not Boolean influence proofs."""
from rvw.formal.internal_paths import analyze,check
import pytest
import shutil


def module(cell_type='$xor'):
    return dict(netnames={'a':{'bits':[2]},'middle':{'bits':[3]},'other':{'bits':[4]},'out':{'bits':[5]}},
        cells={'first':{'type':cell_type,'port_directions':{'A':'input','Y':'output'},'connections':{'A':[2],'Y':[3]}},
               'second':{'type':'$not','port_directions':{'A':'input','Y':'output'},'connections':{'A':[3],'Y':[5]}}})


def test_internal_path_and_absence():
    assert analyze(module(),'a','out')['status']=='path_found'
    assert analyze(module(),'other','out')['status']=='no_path'
    assert analyze(module(),'middle','out')['status']=='path_found'
    assert analyze(module('opaque'),'other','out')['status']=='incomplete'
    assert analyze(module(),'other','out',max_nodes=1)['status']=='incomplete'
    assert analyze(module(),'middle','middle')['status']=='path_found'


def test_native_no_path(tmp_path):
    if not shutil.which('yosys'):
        pytest.skip('Yosys required')
    rtl=tmp_path/'unit.sv'
    rtl.write_text('module Unit(input a,b,c,output y); wire middle=a^b; wire isolated=c; assign y=middle; endmodule')
    result=check([rtl],'Unit','isolated','y',tmp_path/'no-path',20)
    assert result['status']=='no_path'
    result=check([rtl],'Unit','middle','y',tmp_path/'path',20)
    assert result['status']=='path_found'


def test_missing_direction_is_incomplete():
    data=module()
    data['cells']['first']['port_directions'].pop('Y')
    assert analyze(data,'other','out')['status']=='incomplete'


def test_command_and_mcp_registration():
    import argparse
    from rvw.formal.internal_paths import register,mcp_tools
    parser=argparse.ArgumentParser()
    register(parser.add_subparsers())
    args=parser.parse_args(['internal-path','secret','public','--verilog','dut.sv','--top','Unit','--out','out'])
    assert args.source=='secret' and args.destination=='public'
    assert mcp_tools()[0].name=='formal_internal_path'


def test_uncaptured_include_refused(tmp_path):
    source=tmp_path/'unit.sv'
    source.write_text('`include "outside.sv"\n')
    with pytest.raises(ValueError,match='includes are not captured'):
        check([source],'Unit','a','b',tmp_path/'out')
