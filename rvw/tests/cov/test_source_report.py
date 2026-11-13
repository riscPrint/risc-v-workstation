"""Source links must bind both coverage contexts and leave missing mappings visible."""
import importlib
import json
import pytest
m=importlib.import_module('rvw.cov.source_report')
pytestmark=pytest.mark.fast


def inputs(tmp_path,monkeypatch):
    native={'point_universe':'native','points':[
        {'id':'a','fields':{'t':'line'},'count':1,'scala':{'file':'Core.scala','line':4}},
        {'id':'b','fields':{'t':'toggle'},'count':0,'scala':{'file':'Core.scala','line':4}},
        {'id':'c','fields':{'t':'line'},'count':0,'scala':None}]}
    functional={'schema':'rvw.functional-coverage/1','config_sha256':'semantic','groups':{
        'add':{'expected_bins':2,'expected_hit':1,'holes':[['zero']]},
        'load':{'expected_bins':1,'expected_hit':0,'holes':[['word']]}}}
    links={'schema':'rvw.source-bindings/1','point_universe':'native','functional_config_sha256':'semantic',
           'links':[{'file':'Core.scala','line':4,'groups':['add']}]}
    monkeypatch.setattr(m,'code_report',lambda data:{'sources':{}})
    paths=[]
    for name,data in [('native',native),('functional',functional),('links',links)]:
        path=tmp_path/(name+'.json');path.write_text(json.dumps(data));paths.append(path)
    return paths


def test_separate_denominators_and_unmapped_evidence(tmp_path,monkeypatch):
    result=m.source_report(*inputs(tmp_path,monkeypatch))
    assert result['code_targets']==['b','c']
    assert result['functional_targets']==['add:["zero"]']
    assert result['unmapped_native_points']==1
    assert result['unmapped_functional_groups']==['load']
    assert result['lines'][0]['native_points']['b']['metric']=='toggle'


@pytest.mark.parametrize('field',['point_universe','functional_config_sha256'])
def test_stale_bindings_are_rejected(tmp_path,monkeypatch,field):
    paths=inputs(tmp_path,monkeypatch)
    links=json.loads(paths[2].read_text());links[field]='different';paths[2].write_text(json.dumps(links))
    with pytest.raises(ValueError,match='differ'):
        m.source_report(*paths)


def test_unmapped_line_cannot_get_functional_credit(tmp_path,monkeypatch):
    paths=inputs(tmp_path,monkeypatch)
    links=json.loads(paths[2].read_text());links['links'][0]['line']=5;paths[2].write_text(json.dumps(links))
    with pytest.raises(ValueError,match='existing native'):
        m.source_report(*paths)


def test_native_parser_and_cli_keep_source_holes(tmp_path,capsys):
    from rvw.cov.code import merge
    from rvw.cli import main
    from .test_code import dat
    (tmp_path/'logic.v').write_text('assign x=y; // @ Core.scala l4\n')
    native=merge([str(dat(tmp_path/'coverage.dat',[0]))],root=tmp_path)
    semantic={'schema':'rvw.functional-coverage/1','config_sha256':'plan','groups':{
        'add':{'expected_bins':1,'expected_hit':0,'holes':[['zero']]}}}
    links={'schema':'rvw.source-bindings/1','point_universe':native['point_universe'],
           'functional_config_sha256':'plan','links':[{'file':'Core.scala','line':4,'groups':['add']}]}
    paths=[]
    for name,obj in [('native',native),('semantic',semantic),('links',links)]:
        path=tmp_path/(name+'.json');path.write_text(json.dumps(obj));paths.append(str(path))
    assert main(['cov','source-report','--database',paths[0],'--functional',paths[1],
                 '--bindings',paths[2],'--json'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['code_targets']==[native['points'][0]['id']]
    assert result['lines'][0]['functional_holes']==['add:["zero"]']
