import pytest
from pathlib import Path
from types import SimpleNamespace
from rvw.formal.compiled_variants import script
from rvw.formal import portfolio

pytestmark = pytest.mark.fast


def test_cut_classes_are_explicit():
    assert 't:$mem_v2' in script('ram')
    assert script('counter') == 'cutpoint t:$add'
    assert 't:$dff' in script('cut-points')
    with pytest.raises(ValueError): script('uf')


def test_rtlil_is_not_reparsed_as_verilog(tmp_path, monkeypatch):
    import hashlib
    src=tmp_path/'top.il';src.write_text('module \\top\nend\n')
    monkeypatch.setattr(portfolio.shutil,'which',lambda _: __file__)
    def run(cmd,**kwargs):
        assert cmd[0]=='yosys'
        assert 'read_rtlil input0.il' in cmd[-1]
        (Path(kwargs['cwd'])/'design.json').write_text('{"modules":{"top":{"cells":{}}}}')
        return SimpleNamespace(returncode=0,timed_out=False,stdout='',stderr='')
    monkeypatch.setattr(portfolio,'run_group',run)
    r=portfolio.race({'top':'top','sources':[{'path':str(src),'format':'rtlil','sha256':hashlib.sha256(src.read_bytes()).hexdigest()}], 'engines':['abc:pdr']},tmp_path,tmp_path/'out')
    assert r['reason']=='no_checks'
