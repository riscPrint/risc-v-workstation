import json
import pytest
from rvw.cosim.exchange import export, import_stream, convert
from test_state import fixture

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('kind', ['rvvi', 'spike'])
def test_lossless_roundtrip_and_mutation(kind):
    header, row = fixture()
    rows = [header, row, dict(event='irq', cycle=2, levels='0x80'), dict(event='end', cycle=3, status='pass')]
    encoded = export(rows, kind)
    restored, sparse = import_stream(encoded, kind)
    assert restored == rows
    assert not sparse
    encoded = encoded.replace('0x80000000', '0x80000004', 1)
    with pytest.raises(ValueError, match='conflict'):
        import_stream(encoded, kind)


def test_sparse_spike_refuses_c2(tmp_path):
    source = tmp_path/'spike.log'
    source.write_text('core   0: 3 0x80000000 (0x00000013)\n')
    out = tmp_path/'out'
    with pytest.raises(ValueError, match='sparse'):
        convert(source, out, 'spike', 'c2')
    assert not out.exists()
    result = convert(source, out, 'spike', 'observations')
    assert result['sparse'] and not result['independent_check']
    assert json.loads(out.read_text())['missing']


def test_spike_unsupported_effect_is_error():
    with pytest.raises(ValueError, match='unsupported Spike effect'):
        import_stream('core 0: 3 0x80000000 (0x13) mem 0x0 0x1', 'spike')


@pytest.mark.parametrize('old,new', [
    ('XLEN 64', 'XLEN 32'), ('NHART 1', 'NHART 2'),
    ('CYCLE 1 HART 0', 'CYCLE 2 HART 0'), ('HART 0 ORDER', 'HART 1 ORDER'),
    ('ORDER 0', 'ORDER 1'), ('MODE 0x3', 'MODE 0x1'),
    ('NET "rvw.irq_levels" 0x80', 'NET "rvw.irq_levels" 0x8'),
])
def test_rvvi_declared_fields_must_agree_with_state(old, new):
    header, row = fixture()
    encoded = export([header, row, dict(event='irq', cycle=2, levels='0x80'),
                      dict(event='end', cycle=3, status='pass')], 'rvvi')
    assert old in encoded
    with pytest.raises(ValueError, match='conflict'):
        import_stream(encoded.replace(old, new, 1), 'rvvi')


def test_rvvi_mixed_sparse_retirement_is_not_discarded():
    header, row = fixture()
    encoded = export([header, row, dict(event='end', cycle=2, status='pass')], 'rvvi')
    encoded += 'RET 0x80000004 0x13\n'
    with pytest.raises(ValueError, match='mixed'):
        import_stream(encoded, 'rvvi')
