"""Native parity on synthetic integer schedules. Requires a host C compiler."""
import random
import shutil
import pytest
from dataclasses import replace
from rvw.ooo.core import Config, Instruction, simulate
from rvw.ooo import native

pytestmark = pytest.mark.fast


@pytest.fixture(scope='module')
def library(tmp_path_factory):
    if not shutil.which('cc'):
        pytest.skip('host C compiler not installed')
    return native.build(tmp_path_factory.mktemp('ooo-native') / 'libooo.so')


def test_native_reference_parity(library, monkeypatch):
    monkeypatch.setenv('RVW_OOO_NATIVE', str(library))
    rng = random.Random(1582)
    for _ in range(100):
        c = Config(rng.randint(1, 8), rng.randint(1, 16), rng.randint(1, 8),
                   rng.randint(1, 32), rng.randint(1, 8), rng.randint(1, 32),
                   4, 4, rng.randint(1, 8), {'alu': 1, 'multiply': 3, 'divide': 12},
                   physical_registers=rng.choice([0, 33, 40, 64]))
        ops = [Instruction(rng.choice(list(c.latencies)), tuple(rng.randrange(32) for _ in range(rng.randrange(3))), rng.randrange(32)) for _ in range(100)]
        expected = simulate(ops, c, 10000, backend="python")
        expected.pop("backend")
        actual = native.simulate(ops, c, 10000)
        assert actual == expected


def test_fallback_and_cycle_budget(library, monkeypatch):
    monkeypatch.setenv('RVW_OOO_NATIVE', str(library))
    c = Config(1, 4, 1, 8, 1, 4, 2, 2, 1, {'alu': 1, 'load': 4})
    assert native.simulate([Instruction('load')], replace(c, memory_policy='disambiguate'), 100) is None
    assert native.simulate([Instruction('alu')], replace(c, frontend={'decode_width': 4}), 100) is None
    with pytest.raises(ValueError, match='budget'):
        native.simulate([Instruction('alu')], c, 1)
    monkeypatch.setenv('RVW_OOO_NATIVE', '0')
    assert native.simulate([Instruction('alu')], c, 100) is None


def test_public_backend_selection(library, monkeypatch):
    monkeypatch.setenv('RVW_OOO_NATIVE', str(library))
    c = Config(1, 4, 1, 8, 1, 4, 2, 2, 1, {'alu': 1})
    assert simulate([Instruction('alu')], c)['backend'] == 'native'
    assert simulate([Instruction('alu')], c, backend='python')['backend'] == 'python'


def test_mixed_native_parity(library, monkeypatch):
    monkeypatch.setenv('RVW_OOO_NATIVE', str(library))
    rng = random.Random(98511)
    for _ in range(150):
        c = Config(rng.randint(1, 8), rng.randint(1, 16), rng.randint(1, 8),
                   rng.randint(1, 32), rng.randint(1, 8), rng.randint(1, 32),
                   rng.randint(1, 8), rng.randint(1, 8), rng.randint(1, 8),
                   dict(zip(native.KINDS, [1, 3, 12, 7, 2, 3, 1])),
                   ports={'alu': 1, 'load': 1}, branch_penalty=rng.randint(0, 12),
                   branch_speculation=rng.choice([False, True]),
                   physical_registers=rng.choice([0, 33, 40, 64]))
        ops = [Instruction(rng.choice(native.KINDS),
                           tuple(rng.randrange(32) for _ in range(rng.randrange(3))),
                           rng.randrange(32), pc=i*4,
                           next_pc=(i+1)*4 if rng.random()<0.6 else 0)
               for i in range(200)]
        expected = simulate(ops, c, 100000, backend='python')
        expected.pop('backend')
        assert native.simulate(ops, c, 100000) == expected
