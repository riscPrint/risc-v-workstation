from argparse import Namespace
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.formal import datapath

pytestmark = pytest.mark.fast

@pytest.mark.parametrize('case,bits,index,expected', [('all',None,None,'proved'), ('nan',None,None,'partial'), ('all',2,1,'partial')])
def test_successful_part_never_proves_whole_domain(tmp_path, monkeypatch, case, bits, index, expected):
    rtl, model = tmp_path/'dut.v', tmp_path/'reference.c'
    rtl.write_text('fixture'); model.write_text('fixture')
    tool = tmp_path/'tool';tool.write_text('fixture')
    monkeypatch.setattr(datapath.shutil, 'which', lambda _: str(tool))
    monkeypatch.setattr(datapath, 'translate', lambda *a, **k: ('', {'a':1,'b':1,'y':1}, lambda *a: [], lambda *a:'0', lambda *a:'0'))
    def execute(argv, cwd, **kwargs):
        if 'map.ys' in argv:
            (cwd/'mapped.json').write_text('{}')
            return SimpleNamespace(returncode=0, stdout='', stderr='', timed_out=False)
        props = [{'description':name, 'status':'SUCCESS'} for name in ('datapath result','defined RTL output')]
        return SimpleNamespace(returncode=0, stdout=json.dumps([{'result':props}]), stderr='', timed_out=False)
    monkeypatch.setattr(datapath, 'run_group', execute)
    args=Namespace(unit=None,confirm=False,component=None,rtl=str(rtl),model=str(model),width=32,out=str(tmp_path/'out'),
        latency=0,max_latency=None,case=case,case_width=None,rounding=0,timeout=10,unwind=10,reference_tree=None,
        reference_source=[],reference_include=[],binding=None,json=True,operand_prefix_bits=bits,operand_prefix=index)
    rc=datapath.run(args)
    result=json.loads((tmp_path/'out/result.json').read_text())
    assert result['status']==expected
    assert rc==(0 if expected=='proved' else 3)
    assert bool(result['open_parts'])==(expected=='partial')
    assert result['part_status']=='proved'


def test_unproved_part_remains_in_open_parts():
    result=dict(case='normal',case_width=32,width=32,status='inconclusive',scope='transaction')
    datapath.qualify_domain(result)
    assert result['status']=='partial'
    assert result['part_status']=='inconclusive'
    assert result['open_parts'][-1]['case']=='normal'
    assert result['split_completeness']['complete'] is False
