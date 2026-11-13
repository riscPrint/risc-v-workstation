from pathlib import Path
import pytest
from rvw.arch.compiler_export import export,check

pytestmark=pytest.mark.fast


def test_shared_compiler_roundtrip(tmp_path):
    p=Path(__file__).resolve().parents[2]/'Arch/reference/zen5-like.json'
    out=tmp_path/'model';r=export(p,out)
    assert r['parsed']['issue_width']==8
    assert r['parsed']['writes']['multiply']==('multiply',3,1)
    td=out/'model.td';td.write_text(td.read_text().replace('Latency = 3','Latency = 9'))
    with pytest.raises(ValueError,match='latency'):
        check(out)
