"""Buffered stores: issue when ready, hide memory service behind the store buffer."""
from dataclasses import replace

import pytest

from rvw.ooo.core import Config, Instruction, simulate

pytestmark = pytest.mark.fast


def config(**kw):
    return Config(4, 16, 4, 32, 4, 16, 8, 8, 4, {'alu': 1, 'divide': 12, 'load': 2, 'store': 1},
                  memory_policy='disambiguate', **kw)


class Memory:
    def __init__(self): self.writes = 0
    def access(self, address, size, write, cycle):
        self.writes += write
        return 20 if write else 0


def test_buffered_store_passes_older_slow_load():
    # The store waits for the older load only under the ordered policy; the
    # younger load then waits for the store address.
    ops = [Instruction('divide', (), 1), Instruction('load', (1,), 2, address=64, size=4),
           Instruction('alu', (), 3), Instruction('store', (3,), address=16, size=4),
           Instruction('load', (), 4, address=128, size=4)]
    ordered, buffered = simulate(ops, config()), simulate(ops, config(store_policy='buffered'))
    assert buffered['instret'] == ordered['instret'] == 5
    assert ordered['events']['store_address_blocked'] >= 10
    assert buffered['events'].get('store_address_blocked', 0) <= 1


def test_buffered_store_hides_service_but_updates_memory():
    ops = [Instruction('store', (), address=16 * i, size=4) for i in range(4)]
    m1, m2 = Memory(), Memory()
    ordered = simulate(ops, config(), memory=m1)
    buffered = simulate(ops, config(store_policy='buffered'), memory=m2)
    assert m1.writes == m2.writes == 4
    assert buffered['cycles'] + 60 <= ordered['cycles']
    assert buffered['events']['buffered_store_service_cycles'] == 80


def test_store_policy_is_checked():
    with pytest.raises(ValueError, match='unsupported store_policy'):
        config(store_policy='later')
    with pytest.raises(ValueError, match='buffered stores need'):
        replace(config(), memory_policy='ordered', store_policy='buffered')


def test_buffered_store_still_forwards_to_younger_load():
    ops = [Instruction('store', (), address=16, size=4),
           Instruction('load', (), 1, address=16, size=4)]
    result = simulate(ops, config(store_policy='buffered'), memory=Memory())
    assert result['instret'] == 2
    assert result['events']['forwarded_loads'] == 1


def test_buffered_store_uses_python_engine():
    from rvw.ooo.native import supported
    assert not supported(config(store_policy='buffered'))
