import shutil
import subprocess
import pytest
from rvw.formal.resource_checks import render


def simulate(tmp_path, kind, ports, drive):
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus is not installed')
    (tmp_path/'check.sv').write_text(render(kind,3,4))
    (tmp_path/'tb.sv').write_text('module tb; reg clk=0; always #5 clk=~clk; reg reset=1; '+ports+
        f' rvw_{kind} dut(.*); initial begin #11; reset=0; '+drive+' #10; $finish; end endmodule')
    build = subprocess.run(['iverilog','-g2012','-s','tb','-o',str(tmp_path/'sim'),
                             str(tmp_path/'check.sv'),str(tmp_path/'tb.sv')],capture_output=True,text=True,timeout=15)
    assert build.returncode == 0, build.stderr
    run = subprocess.run(['vvp',str(tmp_path/'sim')],capture_output=True,text=True,timeout=15)
    return 'ERROR:' in run.stdout


@pytest.mark.parametrize('fault',['none','leak','double_allocate','duplicate_lane','free_unused','duplicate_free','out_of_range'])
def test_pool(tmp_path,fault):
    ports = ('reg [3:0] live=0; reg alloc0_valid=0,alloc1_valid=0,free0_valid=0,free1_valid=0; '
             'reg [2:0] alloc0=1,alloc1=1,free0=1,free1=1;')
    drive = 'alloc0_valid=1; #10; live=2; alloc0_valid=0; '
    drive += dict(none='free0_valid=1; alloc0_valid=1; #10; live=2; alloc0_valid=0; free0_valid=0;',
                  leak='live=0;',double_allocate='alloc0_valid=1;',
                  duplicate_lane='alloc0_valid=1; alloc1_valid=1;',free_unused='free0=0; free0_valid=1;',
                  duplicate_free='free0_valid=1; free1_valid=1;',out_of_range='alloc0=7; alloc0_valid=1;')[fault]
    assert simulate(tmp_path,'allocation_pool',ports,drive) == (fault != 'none')


@pytest.mark.parametrize('fault',['none','multi','missing'])
def test_cam(tmp_path,fault):
    ports = 'reg active=1,require_match=1; reg [3:0] match_bits=1;'
    drive = dict(none='#10; match_bits=8; #10; active=0; match_bits=15;',multi='match_bits=3;',missing='match_bits=0;')[fault]
    assert simulate(tmp_path,'cam_match',ports,drive) == (fault != 'none')


@pytest.mark.parametrize('bad',[False,True])
def test_bounds(tmp_path,bad):
    ports = 'reg active=1; reg [2:0] value=0;'
    assert simulate(tmp_path,'counter_bounds',ports,f'value={5 if bad else 4};') == bad


def test_widths_refused():
    with pytest.raises(ValueError): render('allocation_pool',1,4)
    with pytest.raises(ValueError): render('counter_bounds',2,4)
