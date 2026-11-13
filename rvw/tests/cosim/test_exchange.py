import json
import pytest
from rvw.cosim.exchange import export, import_stream, convert
from test_state import fixture


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
