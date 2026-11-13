from argparse import Namespace
import json
import shutil
import pytest
from rvw.formal.recheck import inject, run
from rvw.cli import main


def test_pin_adds_assumption_without_replacing_driver():
    model = 'module \\Top\n  wire \\bad\n  connect \\bad 1\'1\nend\n'
    modified = inject(model, 'Top', [('bad', 1, 0)], 3)
    assert "connect \\bad 1'1" in modified
    assert 'cell $assume' in modified and 'cell $cover' in modified
    assert "connect \\B 1'0" in modified
    assert modified.endswith('end\n')
    with pytest.raises(ValueError, match='width'):
        inject(model, 'Top', [('bad', 1, 2)], 3)


@pytest.fixture(scope='module')
def captured(tmp_path_factory):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'z3')):
        pytest.skip('Yosys/SBY/Z3 required')
    root = tmp_path_factory.mktemp('recheck')
    rtl = root / 'Top.sv'
    rtl.write_text('module Top(input clk, bad, guard);\n'
                   'always @(posedge clk) begin assert(!bad); assume(!guard); end\nendmodule\n')
    main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'Top', '--engine', 'smtbmc:z3',
          '--depth', '3', '--out', str(root / 'proof')])
    assert json.loads((root / 'proof/result.json').read_text())['status'] == 'fail'
    return root / 'proof'


@pytest.mark.parametrize('pin,expected', [('bad=0', 'pass'), ('bad=1', 'fail'), ('guard=1', 'inconclusive')])
def test_native_recheck(captured, tmp_path, pin, expected):
    args = Namespace(result=str(captured), pin=[pin], out=str(tmp_path / 'out'),
                     depth=3, engine='smtbmc:z3', timeout=20, json=False)
    code = run(args)
    result = json.loads((tmp_path / 'out/result.json').read_text())
    assert result['status'] == expected, result
    assert code == (0 if expected == 'pass' else 1)
    assert result['proof_kind'] == 'bounded'
