from argparse import Namespace
import json
import shutil
import subprocess

import pytest

from rvw.formal.temporal import Unsupported, lower
from rvw.formal.snapshot import InputSnapshot


CHECKER = '''checker response_check(input clk, input a, input b);
property response; @(posedge clk) a |=> b; endproperty
p: assert property (response);
endchecker
bind m response_check contract(.clk(clk), .a(a), .b(b));
'''


def test_named_property():
    rtl, rows = lower('''module m(input clk,a,b);
    property p; @(posedge clk) a |=> b; endproperty
    property q; p; endproperty
    check: assert property (q); endmodule''')
    assert len(rows) == 1 and rows[0]['id'] == 'check'
    assert 'endproperty' not in rtl
    with pytest.raises(Unsupported, match='recursive_property'):
        lower('module m; property p; p; endproperty assert property(p); endmodule')


def test_snapshot_bind_file(tmp_path):
    rtl = tmp_path / 'rtl.sv'
    binding = tmp_path / 'bind.sv'
    rtl.write_text('module m(input clk,a,b); endmodule')
    binding.write_text(CHECKER)
    out = tmp_path / 'out'
    out.mkdir()
    snap = InputSnapshot(Namespace(verilog=[str(rtl), str(binding)], checks=None, frontend='temporal'), out)
    assert len(snap.sources) == 1
    assert 'response_check contract' in snap.sources[0].read_text()
    assert len(snap.files) == 2
    assert snap.artifacts[0]['path'] == 'inputs/temporal.sv'
    (out / 'module_ports.d').write_text(f'{out / "module_ports.json"} {out / "module_ports.il"}: {snap.sources[0]}')
    snap.check_frontend()
    result = {'status': 'unknown'}
    snap.finish(result)
    assert result['temporal_properties'][0]['id'] == 'p'


@pytest.mark.parametrize('source', [
    CHECKER.replace('bind m', 'bind top.u'),
    CHECKER.replace('input clk', 'event clk'),
    CHECKER.replace('(.clk(clk), .a(a), .b(b))', '(clk,a,b)'),
    CHECKER.replace('response_check contract', 'missing contract'),
])
def test_bind_refusals(source):
    with pytest.raises(Unsupported):
        lower('module m(input clk,a,b); endmodule\n' + source)


@pytest.mark.parametrize('mutant', [False, True])
def test_native_bound_checker(tmp_path, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    source = ('module m(input clk); wire a=1; wire b=' + ('0;' if mutant else '1;')
              + ' endmodule\n' + CHECKER)
    rtl, _ = lower(source)
    (tmp_path / 'm.sv').write_text(rtl)
    (tmp_path / 'job.sby').write_text('''[options]
mode bmc
depth 8
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    run = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                         capture_output=True, text=True, timeout=30)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), run.stdout


@pytest.mark.parametrize('mutant', [False, True])
def test_native_multifile_bmc(tmp_path, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    import sys
    rtl, bind = tmp_path / 'm.sv', tmp_path / 'bind.sv'
    rtl.write_text('module m(input clk); wire a=1; wire b=' + ('0;' if mutant else '1;') + ' endmodule')
    bind.write_text(CHECKER)
    out = tmp_path / 'proof'
    run = subprocess.run(['nice', '-n', '10', sys.executable, '-m', 'rvw', 'formal', 'bmc',
                          '--frontend', 'temporal', '--verilog', str(rtl), str(bind),
                          '--top', 'm', '--depth', '8', '--out', str(out)],
                         capture_output=True, text=True, timeout=30)
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == ('fail' if mutant else 'pass'), run.stdout + run.stderr
    assert len(result['input_snapshot']['files']) == 2
