"""Check ordered eventual milestones against an independent infinite-trace oracle."""
import random
import shutil
import subprocess

import pytest

from rvw.formal.liveness import lower_live

pytestmark = pytest.mark.fast
SUPPORT_FEATURES = ['nested eventual Boolean milestones']


def lower(expr='req |-> s_eventually (a && s_eventually b)'):
    return lower_live('module m(input clk,req,a,b); assert property (@(posedge clk) '
                      + expr + '); endmodule', 'm')


def test_nested_lowering_and_capacity():
    rtl, rows, _ = lower()
    assert rows[0]['milestones'] == 2
    assert 's_eventually' not in rtl
    for expr in ['s_eventually s_eventually b',
                 's_eventually (a && s_eventually (b && s_eventually a))']:
        assert lower(expr)[1][0]['operator'] == 'nested_eventually'
    with pytest.raises(ValueError):
        lower('s_eventually (a || s_eventually b)')


def oracle(prefix, loop):
    # Each request needs a later (or coincident) a followed by b. Two full
    # loop periods suffice for these two existential milestones.
    trace = prefix + loop * 4
    for start, row in enumerate(prefix + loop):
        if row[0] and not any(trace[i][1] and any(r[2] for r in trace[i:])
                              for i in range(start, len(trace))):
            return False
    return True


def test_oracle_checks_order_and_pending_requests():
    assert not oracle([], [(1, 0, 1)])
    assert not oracle([], [(1, 1, 0)])
    assert oracle([], [(1, 0, 1), (0, 1, 0)])
    assert not oracle([(1, 0, 0)], [(0, 0, 1)])
