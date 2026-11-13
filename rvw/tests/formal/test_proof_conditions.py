import hashlib
import pytest
from rvw.formal.proof_conditions import condition

pytestmark = pytest.mark.fast


def test_exact_source_and_elaborated_predicate(tmp_path):
    source = tmp_path / 'input0.sv'
    source.write_text('module t;\nrestrict property (resetn != $initstate);\nendmodule\n')
    row = condition('t', 'a', {'attributes': {'src': 'input0.sv:2.1-2.49'},
                              'connections': {'A': [14], 'EN': ['1']}}, tmp_path)
    assert row['source_excerpt'] == 'restrict property (resetn != $initstate);'
    assert row['predicate_bits'] == [14] and row['enable_bits'] == ['1']
    assert row['source_sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_missing_context_is_not_invented(tmp_path):
    row = condition('t', 'a', {'attributes': {'src': 'absent.sv:2.1-2.4'}}, tmp_path)
    assert 'source_excerpt' not in row
