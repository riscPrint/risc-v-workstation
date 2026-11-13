from argparse import Namespace
from itertools import product
import json
import shutil
import subprocess

import pytest

from rvw.formal.liveness import lower_live, run, script
from rvw.formal.temporal import Unsupported

SOURCE = '''module m(input clk, req, ack);
p: assert property (@(posedge clk) req |-> s_eventually ack);
endmodule'''


def test_lower():
    rtl, rows, finite = lower_live(SOURCE, 'm')
    assert rows == [dict(id='p', wire='rvw_live_0', clock='clk', kind='live')]
    assert not finite
    assert 'pending || (req)' in rtl
    assert 'add -live rvw_live_0' in script('m', rows)
    _, fair, _ = lower_live(SOURCE.replace('assert property', 'assume property'), 'm')
    assert fair[0]['kind'] == 'fair'


@pytest.mark.parametrize('req_loop,response', list(product((False, True), repeat=2)))
def test_periodic_semantics(req_loop, response):
    # For every short finite prefix, repeat one pair forever. This independent
    # lasso oracle checks that pending obligations survive the prefix.
    for prefix in product(product((False, True), repeat=2), repeat=3):
        pending = False
        for req, ack in prefix:
            pending = (pending or req) and not ack
        expected = response or (not pending and not req_loop)
        values = []
        for _ in range(4):
            pending = (pending or req_loop) and not response
            values.append(not pending)
        assert all(values[-2:]) == expected


@pytest.mark.parametrize('expr', [
    'req |=> s_eventually ack',
    'req |-> s_eventually $past(ack)',
    'disable iff(rst) req |-> s_eventually ack',
    'req |-> s_eventually (ack ##1 ack)',
])
def test_unsupported(expr):
    with pytest.raises(ValueError):
        lower_live('module m; assert property (@(posedge clk) ' + expr + '); endmodule', 'm')


def test_no_unearned_pass(tmp_path, monkeypatch):
    source = tmp_path / 'm.sv'
    source.write_text(SOURCE)
    monkeypatch.setattr(shutil, 'which', lambda tool: None)
    out = tmp_path / 'proof'
    assert run(Namespace(source=str(source), top='m', out=str(out), run=True, timeout=2)) == 1
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'unknown'
    assert result['observation'] == 'missing_tool'


def test_native_live_cells(tmp_path):
    if not shutil.which('yosys'):
        pytest.skip('Yosys required')
    rtl, rows, _ = lower_live(SOURCE, 'm')
    (tmp_path / 'lowered.sv').write_text(rtl)
    commands = script('m', rows) + '\nwrite_json model.json'
    run = subprocess.run(['nice', '-n', '10', 'yosys', '-Q', '-p', commands], cwd=tmp_path,
                         capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    cells = json.loads((tmp_path / 'model.json').read_text())['modules']['m']['cells']
    assert sum(c['type'] == '$live' for c in cells.values()) == 1
