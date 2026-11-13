"""Bounds of the explicit machine-only Sail profile."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from rvw.cosim.platform import Platform
from rvw.cosim.sail import Sail

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[3]


def model(*instructions):
    result = object.__new__(Sail)
    result.platform = SimpleNamespace(ecall_tval='insn', normalize_effect=lambda e: e)
    result.effects = iter(dict(insn=i, trap=False, intr=False, mode_after=3) for i in instructions)
    result.peeked = None
    return result


def test_ecall_policy_refuses_unpropagated_csr_read():
    reference = model(0x34302573)  # csrr a0, mtval
    reference.set_trap_tval(0x73)
    with pytest.raises(ValueError, match='cannot propagate'):
        reference.step()


def test_independent_full_write_restores_common_state():
    reference = model(0x34329073, 0x34302573)  # csrw mtval,t0; csrr a0,mtval
    reference.set_trap_tval(0x73)
    reference.step()
    assert not reference.tval_override_pending
    reference.step()


@pytest.mark.parametrize('value', [0, 0x74])
def test_policy_never_takes_arbitrary_trap_value(value):
    with pytest.raises(ValueError, match='cannot apply'):
        model().set_trap_tval(value)


@pytest.mark.parametrize('isa', ['rv64im', 32, 'anything'])
def test_sail_reference_isa_must_match_xlen(tmp_path, isa):
    data = json.loads((ROOT/'examples/vexriscv/rvw/platform.json').read_text())
    data['sail_reference_isa'] = isa
    path = tmp_path/'platform.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='invalid sail_reference_isa'):
        Platform.load('example', path)
