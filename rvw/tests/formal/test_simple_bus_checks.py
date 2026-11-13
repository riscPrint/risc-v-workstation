import shutil
import subprocess
import pytest
from rvw.formal.simple_bus_checks import render


def simulate(tmp_path, kind, ports, drive):
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus is not installed')
    (tmp_path/'monitor.sv').write_text(render(kind, 8, 4))
    tb = ('module tb; reg clk=0; always #5 clk=~clk; reg reset=1;\n' + ports +
          f'\nrvw_{kind} dut(.*); initial begin #11; reset=0; {drive} #10; $finish; end endmodule\n')
    (tmp_path/'tb.sv').write_text(tb)
    build = subprocess.run(['iverilog','-g2012','-s','tb','-o',str(tmp_path/'sim'),
                            str(tmp_path/'monitor.sv'),str(tmp_path/'tb.sv')],
                           capture_output=True, text=True, timeout=15)
    assert build.returncode == 0, build.stderr
    run = subprocess.run(['vvp',str(tmp_path/'sim')], capture_output=True, text=True, timeout=15)
    return 'ERROR:' in run.stdout


@pytest.mark.parametrize('bad', [False, True])
def test_axis_stability(tmp_path, bad):
    ports = 'reg valid=0, ready=0; reg [7:0] payload=0;'
    drive = f'valid=1; payload=5; #10; payload={6 if bad else 5}; #10; ready=1; #10; valid=0;'
    assert simulate(tmp_path, 'axis', ports, drive) == bad


@pytest.mark.parametrize('fault', ['none','skip_setup','change_request','drop_select','skip_enable','repeat_access'])
def test_apb_setup_wait_and_back_to_back(tmp_path, fault):
    ports = 'reg select=0,enable=0,ready=0,error=0; reg [7:0] request=0;'
    if fault == 'skip_setup':
        drive = 'select=1; enable=1; ready=1;'
    else:
        drive = 'select=1; request=5; #10; enable=1; #10; '
        if fault == 'change_request': drive += 'request=6; '
        if fault == 'drop_select': drive += 'select=0; '
        if fault == 'skip_enable': drive += 'enable=0; '
        drive += '#10; ready=1; error=1; #10; error=0; '
        drive += 'enable=1; ' if fault == 'repeat_access' else 'enable=0; request=9; '
        drive += '#10; enable=1; #10; select=0; enable=0;'
    assert simulate(tmp_path, 'apb', ports, drive) == (fault != 'none')


@pytest.mark.parametrize('fault', ['none','address','one_cycle_error','extended_error'])
def test_ahb_wait_and_two_cycle_error(tmp_path, fault):
    ports = 'reg select=0,ready=1,response_error=0; reg [1:0] transfer=0; reg [7:0] request=0;'
    drive = 'select=1; transfer=2; request=8; #10; ready=0; #10; '
    if fault == 'address': drive += 'request=9; '
    drive += 'response_error=1; '
    if fault == 'one_cycle_error': drive += 'ready=1; '
    drive += '#10; '
    if fault != 'extended_error': drive += 'ready=1; '
    drive += '#10; response_error=0; ready=1; select=0; transfer=0;'
    assert simulate(tmp_path, 'ahb_lite', ports, drive) == (fault != 'none')


def test_ahb_error_allows_cancel_of_next_address(tmp_path):
    ports = 'reg select=0,ready=1,response_error=0; reg [1:0] transfer=0; reg [7:0] request=0;'
    drive = ('select=1; transfer=2; request=8; #10; ready=0; #10; response_error=1; '
             '#10; ready=1; select=0; transfer=0; request=0; #10; response_error=0;')
    assert not simulate(tmp_path, 'ahb_lite', ports, drive)


def test_axis_reset_cancels_stall(tmp_path):
    ports = 'reg valid=0,ready=0; reg [7:0] payload=0;'
    drive = 'valid=1; #10; reset=1; valid=0; payload=7; #10; reset=0;'
    assert not simulate(tmp_path, 'axis', ports, drive)


def test_apb_unselected_peripheral_can_observe_shared_enable(tmp_path):
    ports = 'reg select=0,enable=0,ready=1,error=0; reg [7:0] request=0;'
    drive = 'enable=1; request=5; #20; request=9; #10; enable=0;'
    assert not simulate(tmp_path, 'apb', ports, drive)
