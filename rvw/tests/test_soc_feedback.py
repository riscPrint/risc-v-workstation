import hashlib
import json
import pytest
from lint_builder import Builder
from rvw.soc.feedback import import_feedback

pytestmark=pytest.mark.fast


def test_feedback(tmp_path):
    b=Builder(tmp_path/'design.db');b.sig('clk',direction='in');db=b.done()
    report=tmp_path/'timing.txt';report.write_text('external timing result')
    spec=dict(schema='rvw.soc-feedback/1',database_sha256=hashlib.sha256(db.read_bytes()).hexdigest(),tool='example STA',scope='post synthesis only',constraints=['clock 10ns'],reports=['timing.txt'],findings=[dict(kind='timing',endpoint='clk',message='endpoint',report='timing.txt'),dict(kind='area',endpoint='absent',message='unknown',report='timing.txt')])
    src=tmp_path/'feedback.json';src.write_text(json.dumps(spec))
    result=import_feedback(db,src,tmp_path/'out.json')
    assert result['status']=='imported_claims'
    assert [f['match'] for f in result['findings']]==['matched','unmatched']
    spec['database_sha256']='wrong';src.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match='identity'):import_feedback(db,src,tmp_path/'bad.json')
