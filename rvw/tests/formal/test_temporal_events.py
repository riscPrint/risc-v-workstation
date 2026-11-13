"""Sampled multi-clock and asynchronous cancellation semantic references."""
import shutil
import subprocess

import pytest

from rvw.formal.temporal import lower


@pytest.mark.parametrize('case', ['pulse', 'two_clocks'])
@pytest.mark.parametrize('mutant', [False, True])
def test_native_events(tmp_path, case, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    head = '''module m;
      reg [5:0] sample=0;
      always @($global_clock) if(sample<31) sample<=sample+1;
      wire clk=sample[1]; wire clk2=sample[2];
    '''
    if case == 'pulse':
        # Request at the first edge. Reset pulses at the next falling edge,
        # then deasserts before the next rising edge. No later requests occur.
        text = head + '''wire req=sample<2; wire rst=sample==4; wire response=0;
        assert property (@(posedge clk) ''' + ('' if mutant else 'disable iff(rst) ') + '''
          req |-> ##2 response); endmodule'''
    else:
        text = head + '''reg a=0,b=0;
          always @(posedge clk) a<=1;
          always @(posedge clk2) b<=''' + ('0;' if mutant else '1;') + '''
          assert property (@(posedge clk) 1 |=> a);
          assert property (@(posedge clk2) 1 |=> b); endmodule'''
    rtl, rows = lower(text)
    if case == 'two_clocks':
        assert {r['clock'] for r in rows} == {'clk', 'clk2'}
    (tmp_path / 'm.sv').write_text(rtl)
    (tmp_path / 'job.sby').write_text('''[options]
mode bmc
depth 30
multiclock on
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    result = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), result.stdout
