from dataclasses import asdict,replace
import importlib
import json
from pathlib import Path
import pytest
from test_ooo import cfg,trace
from rvw.csim.cli import simpoint_json
from rvw.ooo.sampled import sampled,sampled_many
import rvw.ooo.windows as windows

pytestmark=pytest.mark.fast


def inputs(tmp_path):
    t=tmp_path/'trace';trace(t)
    p=tmp_path/'points';p.write_text(json.dumps(simpoint_json(t,2,max_k=1)))
    configs={}
    for name,c in [('base',cfg()),('slow',replace(cfg(),latencies={'alu':3,'load':4,'store':2}))]:
        path=tmp_path/name;path.write_text(json.dumps(asdict(c)));configs[name]=path
    return t,p,configs


def count_collect(monkeypatch):
    calls=[];original=windows.collect
    def collect(*args):
        calls.append(args[3])
        return original(*args)
    monkeypatch.setattr(windows,'collect',collect)
    return calls


def test_shared_reports_equal_independent_runs(tmp_path,monkeypatch):
    t,p,configs=inputs(tmp_path)
    independent={name:sampled(cp,t,p,tmp_path/(name+'-single'),1)
                 for name,cp in configs.items()}
    calls=count_collect(monkeypatch)
    shared=sampled_many(configs,t,p,{name:tmp_path/(name+'-shared') for name in configs},1)
    assert len(calls)==1
    assert shared==independent
    assert shared['slow']['sampled_ipc']<shared['base']['sampled_ipc']


def test_custom_definitions_get_separate_validation(tmp_path,monkeypatch):
    from test_ooo_custom import rule
    t,p,configs=inputs(tmp_path)
    data=json.loads(configs['slow'].read_text())
    data['custom_instructions']=[rule()];data['latencies']['custom_mac']=3
    configs['slow'].write_text(json.dumps(data))
    calls=count_collect(monkeypatch)
    sampled_many(configs,t,p,{name:tmp_path/(name+'-result') for name in configs},1)
    assert len(calls)==2
    assert calls[0]!=calls[1]


def test_changed_trace_is_refused_before_second_report(tmp_path,monkeypatch):
    module=importlib.import_module('rvw.ooo.sampled')
    t,p,configs=inputs(tmp_path);original=module.simulate
    def simulate(*args,**kwargs):
        result=original(*args,**kwargs)
        t.write_text(t.read_text().replace('"pass"','"fail"'))
        return result
    monkeypatch.setattr(module,'simulate',simulate)
    outputs={name:tmp_path/(name+'-result') for name in configs}
    with pytest.raises(ValueError,match='trace hash mismatch'):
        sampled_many(configs,t,p,outputs,1)
    assert outputs['base'].exists()
    assert not outputs['slow'].exists()


def test_each_project_selection_is_checked(tmp_path):
    t,p,configs=inputs(tmp_path)
    root=Path(__file__).resolve().parents[2]
    wrong=json.loads((root/'examples/vexriscv/rvw/arch/own.json').read_text())
    wrong['config']='not-selected';configs['slow'].write_text(json.dumps(wrong))
    outputs={name:tmp_path/(name+'-result') for name in configs}
    with pytest.raises(ValueError,match='selected config'):
        sampled_many(configs,t,p,outputs,1)
    assert not outputs['slow'].exists()
