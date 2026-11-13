import random
import shutil
import subprocess
from argparse import Namespace
import json

import pytest

from rvw.formal.liveness import lower_live, run


def lower():
    return lower_live('module m(input clk,req,a,b); assert property (@(posedge clk) '
                      'req |-> s_eventually (a && s_eventually b)); endmodule', 'm')


def oracle(prefix, loop):
    trace = prefix + loop * 4
    return all(not row[0] or any(trace[i][1] and any(r[2] for r in trace[i:])
                                for i in range(start, len(trace)))
               for start, row in enumerate(prefix + loop))


def test_native_lassos_match_existential_oracle(tmp_path):
    if not all(shutil.which(t) for t in ('iverilog', 'vvp')):
        pytest.skip('Icarus required')
    rng = random.Random(61)
    cases = [([], [(1, 0, 1)]), ([], [(1, 1, 0)]),
             ([], [(1, 0, 1), (0, 1, 0)]), ([], [(1, 1, 1)])]
    cases += [([tuple(rng.randrange(2) for _ in range(3)) for _ in range(3)],
               [tuple(rng.randrange(2) for _ in range(3)) for _ in range(3)]) for _ in range(40)]
    statements = []
    for index, (prefix, loop) in enumerate(cases):
        # A new instance per lasso preserves the monitor's initial state.
        statements.append(f'reg clk{index}=0,req{index}=0,a{index}=0,b{index}=0; '
                          f'm d{index}(clk{index},req{index},a{index},b{index}); initial begin')
        trace = prefix + loop * 12
        for step, (req, a, b) in enumerate(trace):
            statements.append(f'req{index}={req}; a{index}={a}; b{index}={b}; #1; clk{index}=1; #1; '
                              f'$display("P {index} {step} %b",d{index}.rvw_live_0); clk{index}=0;')
        statements.append('end')
    source = tmp_path / 'm.sv'
    source.write_text(lower()[0] + '\nmodule tb;\n' + '\n'.join(statements) +
                      '\ninitial begin #100; $finish; end endmodule\n')
    subprocess.run(['nice','-n','10','iverilog','-g2012','-s','tb','-o',str(tmp_path/'sim'),str(source)],
                   capture_output=True, text=True, check=True, timeout=30)
    result = subprocess.run(['nice','-n','10','vvp',str(tmp_path/'sim')],
                            capture_output=True,text=True,check=True,timeout=30)
    observed = {i: [] for i in range(len(cases))}
    for line in result.stdout.splitlines():
        if not line.startswith('P '):
            continue
        _, case, step, value = line.split()
        if int(step) >= len(cases[int(case)][0]) + len(cases[int(case)][1]) * 8:
            observed[int(case)].append(value)
    for index, (prefix, loop) in enumerate(cases):
        assert ('1' in observed[index]) == oracle(prefix, loop), (prefix, loop, observed[index])


@pytest.mark.parametrize('mutant', [False, True])
def test_native_nested_liveness_to_safety(tmp_path, mutant):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yosys-abc')):
        pytest.skip('Yosys, SBY and ABC required')
    source = tmp_path / 'm.sv'
    source.write_text('module m(input clk,reset); reg n=0; '
        'always @(posedge clk) if(reset)n<=0; else n<=!n; '
        'assert property (@(posedge clk) 1 |-> s_eventually (n && s_eventually '
        + ('0' if mutant else '!n') + ')); endmodule')
    out = tmp_path / 'proof'
    run(Namespace(source=str(source), top='m', out=str(out), run=True, timeout=30,
                  backend='l2s', reset='reset', engine='abc:pdr', mode='prove', depth=12))
    result = json.loads((out/'result.json').read_text())
    assert result['observation'] == ('FAIL' if mutant else 'PASS'), result
