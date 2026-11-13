import pytest
from rvw.formal.engine_limits import avy_failure, rlive_failure

pytestmark = pytest.mark.fast


def test_observed_avy_class(tmp_path):
    p = tmp_path / 'problem/model'
    p.mkdir(parents=True)
    (p / 'design_aiger_fold.aig').write_bytes(b'aig 5 5 0 1 0\n0\n')
    assert avy_failure(tmp_path, 'returncode=-11')['observed_input_classes'] == ['zero_latches']
    assert avy_failure(tmp_path, 'returncode=0') == {}
    (p / 'design_aiger_fold.aig').write_bytes(b'aig 10 2 3 23 5\n')
    assert avy_failure(tmp_path, 'returncode=-11')['observed_input_classes'] == ['multiple_outputs']


def test_rlive_removed_internal_option():
    assert rlive_failure('', "error: unexpected argument '--no-ic3-pred-prop' found")['reason'] == 'unsupported_backend_cli'
    assert rlive_failure('UNSAT', '') == {}
