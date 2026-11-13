from pathlib import Path
import json
import pytest
from rvw.ooo.project import configuration
from rvw.ooo.core import Instruction, simulate

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('name',['zen5-like','m1-like','boom-large','boom-mega','vexriscv-class'])
def test_reference_description(name):
    path=Path(__file__).resolve().parents[2]/'Arch/reference'/f'{name}.json'
    c=configuration(json.loads(path.read_text()))
    r=simulate([Instruction('alu',dest=1),Instruction('alu',(1,),2)],c)
    assert r['instret']==2
    assert r['cycles']>0
