import shutil
import subprocess
import pytest
from rvw.formal.generated_checks import render


@pytest.mark.parametrize('kind', ['hpm', 'initialized_read', 'axi_lite'])
@pytest.mark.parametrize('bad', [False, True])
def test_native_sampled_monitor(tmp_path, kind, bad):
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus is not installed')
    if kind == 'hpm':
        ports = '''reg [7:0] observed=0, events=1, write_data=0;
reg inhibit=0, permitted=1, write_accepted=0, clear_pending=0, irq_enabled=0, pending=0, irq=0;'''
        drive = f'#11; reset=0; #10; observed={2 if bad else 1}; events=0; #10;'
    elif kind == 'initialized_read':
        ports = '''reg read_used=0; reg [7:0] read_mask=1, written_mask=1, required_mask=255;'''
        drive = f'#11; reset=0; #10; read_used=1; written_mask=0; read_mask={2 if bad else 1}; #10;'
    else:
        ports = '''reg aw_fire=0, w_fire=0, b_fire=0, ar_fire=0, r_fire=0;
reg [1:0] bresp=0, rresp=0;
reg awvalid=0, awready=0, wvalid=0, wready=0, bvalid=0, bready=0;
reg arvalid=0, arready=0, rvalid=0, rready=0;'''
        drive = ('#11; reset=0; aw_fire=1; awvalid=1; awready=1; '
                 '#10; aw_fire=0; awvalid=0; w_fire=1; wvalid=1; wready=1; '
                 '#10; w_fire=0; wvalid=0; b_fire=1; bvalid=1; bready=1; ' +
                 f'bresp={1 if bad else 0}; #10; b_fire=0; bvalid=0; #10;')
    tb = ('module tb; reg clk=0; always #5 clk=~clk; reg reset=1;\n' + ports +
          f'\nrvw_{kind} monitor(.*); initial begin {drive} $finish; end endmodule\n')
    (tmp_path/'monitor.sv').write_text(render(kind, 8, 4))
    (tmp_path/'tb.sv').write_text(tb)
    build = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(tmp_path/'sim'),
                            str(tmp_path/'monitor.sv'), str(tmp_path/'tb.sv')], capture_output=True, text=True, timeout=15)
    assert build.returncode == 0, build.stderr
    run = subprocess.run(['vvp', str(tmp_path/'sim')], capture_output=True, text=True, timeout=15)
    assert ('ERROR:' in run.stdout) == bad, run.stdout + run.stderr


def test_parameters_refuse_unsupported_width():
    with pytest.raises(ValueError): render('hpm', 65, 4)
