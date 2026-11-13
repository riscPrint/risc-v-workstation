import pytest
from rvw.sec.gadgets import generate
pytestmark=pytest.mark.fast


def test_receiver_templates(tmp_path):
    result=generate(tmp_path/'suite',seed=3)
    assert result['status']=='generated'
    assert {c['kind'] for c in result['cases']}=={'v1','v2','v4','rsb'}
    for case in result['cases']:
        text=(tmp_path/'suite'/case['assembly']).read_text()
        assert text.count('rdcycle')==512
        assert 'sd t4, 2040(s5)' in text
        assert case['expected']=='no_leak_observed'
