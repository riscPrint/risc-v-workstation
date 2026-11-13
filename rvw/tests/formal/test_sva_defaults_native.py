import shutil

import pytest

from rvw.common.proc import run_group
from rvw.formal.temporal import lower

SUPPORT_FEATURES = ['default clocking', 'default disable iff']


@pytest.mark.parametrize('feature', SUPPORT_FEATURES)
@pytest.mark.parametrize('mutant', [False, True])
def test_native(tmp_path, feature, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    if feature == 'default clocking':
        body = ('reg q=0; always @(posedge clk) q<=!q; '
                'default clocking cb @(posedge clk); endclocking '
                'p: assert property(q |=> ' + ('q' if mutant else '!q') + ');')
    else:
        body = ('reg [2:0] age=0; always @(posedge clk) if(age<7) age<=age+1; '
                'wire rst=age<2; wire ready=' + ('0' if mutant else 'age>=2') + '; '
                'default disable iff(rst); p: assert property(@(posedge clk) ready);')
    model, _ = lower('module Top(input clk); ' + body + ' endmodule')
    (tmp_path / 'model.sv').write_text(model)
    (tmp_path / 'job.sby').write_text('[options]\nmode bmc\ndepth 8\n[engines]\nsmtbmc yices\n'
        '[script]\nread_verilog -formal model.sv\nprep -top Top\nasync2sync\ndffunmap\n[files]\nmodel.sv\n')
    result = run_group(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path, timeout=30, capture=True)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), result.stdout
