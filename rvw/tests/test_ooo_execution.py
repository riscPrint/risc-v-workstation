from types import SimpleNamespace
import pytest
from rvw.ooo.execution import Execution


def test_shared_ports_and_nonpipelined_interval():
    e = Execution(dict(ports={'p0': 1}, bindings={'alu': ['p0'], 'divide': ['p0']}, intervals={'divide': 8}))
    assert e.reserve('divide', 2)
    assert not e.reserve('alu', 2)
    assert not e.reserve('alu', 9)
    assert e.reserve('alu', 10)
    assert e.events['shared_port_blocked'] == 2


def test_flexible_binding_and_distributed_capacity():
    e = Execution(dict(ports={'a': 1, 'b': 1}, bindings={'alu': ['a', 'b']}, queues={'alu': 2}))
    assert e.reserve('alu', 0)
    assert e.reserve('alu', 0)
    assert not e.reserve('alu', 0)
    assert not e.queue_full('alu', [SimpleNamespace(insn=SimpleNamespace(kind='alu'))])
    assert e.queue_full('alu', [SimpleNamespace(insn=SimpleNamespace(kind='alu'))] * 2)


@pytest.mark.parametrize('d', [{'ports': {'p': 0}}, {'ports': {'p': 1}}, {'bindings': {'alu': ['missing']}}, {'intervals': {'divide': True}}])
def test_invalid_description(d):
    with pytest.raises(ValueError):
        Execution(d)
