"""Unspecified FCSR alignment must not hide later state changes."""
import pytest
from rvw.cosim.platform import Platform
from rvw.cosim.reset_fp import seed
from test_state import fixture, Model, run

pytestmark = pytest.mark.fast


class ResetModel(Model):
    def seed_fcsr(self, value):
        self.effect.update(fcsr=value, fflags=value & 31)


def neutral():
    _, row = fixture()
    row.update(fd_valid=False, fflags='0x19', fcsr='0xd9')
    return row


def test_once_at_reset_then_compare_exactly(tmp_path):
    row = neutral()
    model = ResetModel(row)
    model.effect.update(fflags=0, fcsr=0)
    result = run(tmp_path, row, model)
    assert result['status'] == 'match', result
    assert result['recent_synchronizations'][0]['reason'] == 'fcsr_reset_unspecified'
    model = ResetModel(row)
    original = model.step
    def corrupt(**kwargs):
        result = original(**kwargs)
        result['fcsr'] ^= 0x20
        return result
    model.step = corrupt
    assert 'fcsr' in run(tmp_path, row, model)['mismatch']['differences']


@pytest.mark.parametrize('changes', [dict(order=1), dict(pc=0x80000004),
    dict(insn=0x00301073), dict(insn=0x53), dict(fd_valid=True), dict(trap=True)])
def test_never_seed_after_effect_or_at_later_instruction(changes):
    actual = dict(order=0, pc=0x80000000, insn=0x13, trap=False, fd_valid=False, fcsr=0xd9)
    actual.update(changes)
    class Ref:
        def seed_fcsr(self, value):
            pytest.fail('unsafe initialization')
    assert seed(actual, Ref(), Platform.load('boom')) is None


def test_non_reset_platform_refused(tmp_path):
    import json
    path = tmp_path/'platform.json'
    data = json.loads((__import__('pathlib').Path(__file__).resolve().parents[2]/'src/rvw/cosim/configs/boom.json').read_text())
    data['trace_from_reset'] = False
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='trace from reset'):
        Platform.load('boom', path)
