import json
import pytest
from rvw.sec import ift_core
from rvw.sec.budget import BudgetExpired, limit, remaining
pytestmark = pytest.mark.fast


def test_budget_keeps_native_timeout_bounded():
    with limit(10):
        assert 0 < remaining(900) <= 10
    assert remaining(900) == 900


def test_timeout_publishes_partial_cost(tmp_path, monkeypatch):
    out = tmp_path/'run'
    def expire(*args):
        out.mkdir()
        ift_core.progress(out, 'compile', cells=100, shadow_bytes=4000)
        raise BudgetExpired('compile timeout')
    monkeypatch.setattr(ift_core, '_run', expire)
    result = ift_core.run('binding','policy','elf',out,timeout=1)
    assert result['status']=='inconclusive'
    assert result['cost_estimate']['cells']==100
    assert not result['complete']
    assert json.loads((out/'report.json').read_text())['partial']['phase']=='compile'


def test_generated_flow_is_short_and_declares_loaded_word():
    from test_init_native_bindings import core
    from rvw.init.native_bindings import security
    generated = security(core())
    assert 'lw t1, 0(t0)' in generated['rvw/sec/flow.S']
    assert 'scratch: .word 7' in generated['rvw/sec/flow.S']
    assert json.loads(generated['rvw/sec/flow.json'])['memory_regions']==[dict(symbol='scratch',size='0x4')]
    assert json.loads(generated['rvw/sec/constant-time.json'])['program']==['div x10, x6, x7']
