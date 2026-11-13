import pytest
from rvw.formal.instruction_attempts import summarize
pytestmark=pytest.mark.fast


def test_conditional_proof_is_not_full_pipeline_signoff():
    result=summarize(dict(conditional_native_proof=True,rtlil_retry=dict(status='pass',rows=[dict(engine='abc:pdr',status='pass')]),stop_reason='conditional_engine_result'))
    assert result['status']=='inconclusive'
    assert result['conditional_native_proof'] is True
    assert result['engines'][0]['status']=='pass'


def test_abstract_failure_is_not_core_failure():
    result=summarize(dict(status='inconclusive',stop_reason='abstract_counterexample',rtlil_retry=dict(status='fail',rows=[dict(engine='smtbmc:bitwuzla',status='fail')])) )
    assert result['status']=='inconclusive'
    assert result['reason']=='abstract_counterexample'


def test_preparation_error_stays_visible():
    assert summarize(dict(error='RAM preparation budget exhausted'))['reason']=='RAM preparation budget exhausted'
