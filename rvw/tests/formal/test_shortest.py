import json
import shutil
from argparse import Namespace
import pytest
from rvw.formal.shortest import search, run
from rvw.common.proc import run_group


def test_increasing_depth_and_shortest_certificate():
    report = search(5, lambda d: {'status': 'fail' if d == 3 else 'pass'})
    assert report['depth'] == 3 and report['shortest']
    assert [r['depth'] for r in report['attempts']] == [1, 2, 3]


def test_unknown_and_bounded_pass_cannot_certify_shortest():
    assert search(5, lambda d: {'status': 'unknown'})['status'] == 'inconclusive'
    report = search(3, lambda d: {'status': 'pass'})
    assert report['status'] == 'inconclusive' and not report['shortest']


def test_native_shortest(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'z3')):
        pytest.skip('native formal tools required')
    root = tmp_path / 'run'
    (root / 'sby/model').mkdir(parents=True)
    rtl = tmp_path / 'top.v'
    rtl.write_text('module top(input clk); reg [2:0] count=0; always @(posedge clk) count<=count+1; always @* assert(count<2); endmodule')
    il = root / 'sby/model/design.il'
    proc = run_group(['yosys', '-Q', '-T', '-p', f'read_verilog -formal {rtl}; prep -top top; write_rtlil {il}'], capture=True, timeout=10)
    assert proc.returncode == 0
    (root / 'result.json').write_text(json.dumps(dict(schema='rvw.formal/1', assertions=1, flow='bmc', top='original')))
    out = tmp_path / 'out'
    assert run(Namespace(result=str(root), out=str(out), max_depth=5, timeout=30, engine='smtbmc:z3', json=False)) == 1
    report = json.loads((out / 'result.json').read_text())
    assert report['shortest'] and report['depth'] == 3
