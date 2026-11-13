"""CSR-only DUT capture must not claim floating-point observations."""
import pytest
from test_state import fixture, Model, run


def csr_only():
    header, row = fixture()
    header.update(capabilities=['csr'], csr_snapshot=['0x300'])
    for key in ('fd_valid', 'fd', 'fd_wdata', 'fflags', 'fcsr'):
        del row[key]
    row['csr_state'] = {'0x300': '0x7'}
    model = Model(row)
    model.csr_snapshot = lambda addresses: {'0x300': 7}
    return header, row, model


def test_csr_only_snapshot_compares(tmp_path):
    header, row, model = csr_only()
    result = run(tmp_path, row, model, header)
    assert result['status'] == 'match'
    assert result['state_coverage']['fp'] is False
    assert result['state_coverage']['csr_snapshot_steps'] == 1
    row['csr_state']['0x300'] = '0x9'
    assert 'csr[0x300]' in run(tmp_path, row, model, header)['mismatch']['differences']


@pytest.mark.parametrize('change', ['schema', 'csr_snapshot', 'capabilities'])
def test_csr_only_requires_declaration(tmp_path, change):
    header, row, model = csr_only()
    if change == 'schema':
        header[change] = 'rvw.rvfi/1'
    elif change == 'csr_snapshot':
        del header[change]
    else:
        header[change] = ['state']
    with pytest.raises(ValueError):
        run(tmp_path, row, model, header)


def test_csr_only_does_not_accept_fp_data(tmp_path):
    header, row, model = csr_only()
    row['fcsr'] = '0x0'
    with pytest.raises(ValueError, match='FP fields'):
        run(tmp_path, row, model, header)
