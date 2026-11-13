import pytest
from rvw.csim.target_status import classify
from rvw.csim.rtl import read_model

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('taken,pred,hit,addr,status',[(True,True,False,0,'btb-miss'),
 (True,False,True,0,'not-predicted'),(True,True,True,0,'correct'),
 (True,True,True,4,'wrong-target'),(False,False,False,4,'not-taken'),
 (True,None,None,None,'unknown')])
def test_target_classes(taken,pred,hit,addr,status):
    assert classify(taken=taken,predicted_taken=pred,btb_hit=hit,predicted_target=addr,target=0) == status


def test_prediction_versions_preserve_missing_hit_evidence(tmp_path):
    p=tmp_path/'predictions'
    p.write_text('rvw.csim-predictions/1\n1 80 cond 1 1 0 0\n')
    assert read_model(p)[1]['btb_hit'] is None
    p.write_text('rvw.csim-predictions/2\n1 80 cond 1 1 0 0 -1\n')
    assert read_model(p)[1]['btb_hit'] is False
    p.write_text('rvw.csim-predictions/2\n1 80 cond 1 1 0 0 0\n')
    assert read_model(p)[1]['btb_hit'] is True
    from rvw.csim.qualify import _preds
    assert _preds(p)[1] == (0x80, True, True)
