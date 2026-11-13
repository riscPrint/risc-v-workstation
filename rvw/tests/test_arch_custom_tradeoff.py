from dataclasses import asdict,replace
import json
import pytest
from rvw.arch.custom_tradeoff import tradeoff

pytestmark=pytest.mark.fast


def test_custom_tradeoff_keeps_missing_evidence_explicit(tmp_path):
    from test_ooo import cfg,trace
    t=tmp_path/'trace';trace(t)
    (tmp_path/'elf').write_bytes(b'example')
    for n,lat in [('a',5),('b',1)]:
        (tmp_path/n).write_text(json.dumps(asdict(replace(cfg(),latencies={'alu':lat}))))
    spec=dict(schema='rvw.custom-tradeoff-plan/1',workload_id='project/kernel1',
            baseline=dict(config='a',trace='trace',elf='elf'),candidate=dict(config='b',trace='trace',elf='elf'),
            software_cost=dict(baseline=1,candidate=3,unit='developer_hours',source='project estimate'))
    p=tmp_path/'plan';p.write_text(json.dumps(spec));r=tradeoff(p,tmp_path/'out')
    assert r['predicted_speedup']>1
    assert r['software_cost']['delta']==2
    assert r['cases']['candidate']['rtl_status']=='no_checks'
    assert r['cases']['candidate']['ppa_status']=='no_checks'
    assert 'rtl_speedup' not in r
    spec['candidate']['ppa']='ppa'
    (tmp_path/'ppa').write_text(json.dumps(dict(schema='rvw.early-ppa/1',source='synthesis report',rtl_revision='abc',area_mm2=2)))
    p.write_text(json.dumps(spec));r=tradeoff(p,tmp_path/'ppa-out')
    assert r['cases']['candidate']['ppa']['metrics']['area_mm2']==2


def test_saved_rtl_identity_and_speedup(tmp_path):
    from test_ooo_evidence import inputs
    cal,data=inputs(tmp_path)
    cases=[]
    for sample in data['samples'][:2]:
        cases.append(dict(config=data['config'],trace=sample['trace'],elf=sample['elf'],c1=sample['c1']))
    p=tmp_path/'study';spec=dict(schema='rvw.custom-tradeoff-plan/1',workload_id='kernel',
            baseline=cases[0],candidate=cases[1],
            software_cost=dict(baseline=0,candidate=1,unit='hours',source='estimate'))
    p.write_text(json.dumps(spec));r=tradeoff(p,tmp_path/'out')
    assert r['rtl_speedup']==8/9
    c1=tmp_path/cases[1]['c1'];raw=json.loads(c1.read_text());raw['elf_sha256']='a'*64;c1.write_text(json.dumps(raw))
    with pytest.raises(ValueError,match='match the ELF'):
        tradeoff(p,tmp_path/'bad')
