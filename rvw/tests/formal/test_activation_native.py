import json
from pathlib import Path
import shutil

import pytest

from rvw.common.proc import run_group


@pytest.mark.parametrize('req_value,ack,expected,activation', [(0, 0, 'bounded-pass', 'not_reached_within_bound'),
                                                          (1, 1, 'bounded-pass', 'reached'),
                                                          (1, 0, 'failed', 'reached')])
def test_activation_and_failure_location(tmp_path, req_value, ack, expected, activation):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    from rvw.formal.temporal import lower
    model = f'module Top(input clk); wire req={req_value}; wire ack={ack}; '
    assertion, _ = lower(model + 'p: assert property (@(posedge clk) req |=> ack); endmodule')
    cover, _ = lower(model + 'cover property (@(posedge clk) req); endmodule')
    (tmp_path / 'assert.sv').write_text(assertion)
    (tmp_path / 'cover.sv').write_text(cover)
    for mode, source in [('bmc', 'assert'), ('cover', 'cover')]:
        (tmp_path / (source + '.sby')).write_text(f'[options]\nmode {mode}\ndepth 5\n[engines]\nsmtbmc yices\n'
            f'[script]\nread_verilog -formal {source}.sv\nprep -top Top\n[files]\n{source}.sv\n')
    (tmp_path / 'suite.toml').write_text('[[property]]\nid="p"\ntop="Top"\nsby="assert.sby"\n'
                                      'activation_sby="cover.sby"\nsource={file="Core.scala",line=42}\n')
    import sys
    result = run_group([sys.executable, '-m', 'rvw.cli', 'formal', 'regress', str(tmp_path / 'suite.toml'),
                        '--out', str(tmp_path / 'out'), '--timeout', '20', '--proof-cache', str(tmp_path / 'cache'), '--json'], timeout=60, capture=True)
    assert result.returncode == 1, result.stderr
    row = json.loads((tmp_path / 'out/results.json').read_text())['tests'][0]
    assert row['formal_status'] == expected
    assert row['activation']['status'] == activation
    assert row['source'] == dict(file='Core.scala', line=42)

    if req_value == ack == 1:
        again = run_group([sys.executable, '-m', 'rvw.cli', 'formal', 'regress', str(tmp_path / 'suite.toml'),
                           '--out', str(tmp_path / 'again'), '--proof-cache', str(tmp_path / 'cache'),
                           '--timeout', '20', '--json'], timeout=60, capture=True)
        assert again.returncode == 1, again.stderr
        cached = json.loads((tmp_path / 'again/results.json').read_text())['tests'][0]
        assert cached['cache']['hit'] is True
        assert cached['activation']['status'] == 'reached'
        for trace in cached['activation']['traces']:
            assert (tmp_path / 'again' / trace).is_file()
