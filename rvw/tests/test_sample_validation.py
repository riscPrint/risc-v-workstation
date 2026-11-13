import json
import pytest
from rvw.sample import validation

pytestmark = pytest.mark.fast


def test_validation_reports_observed_gap(tmp_path, monkeypatch):
    manifest = tmp_path/'study'
    manifest.write_text('{}')
    elf = tmp_path/'elf'; elf.write_text('elf')
    platform = tmp_path/'platform'; platform.write_text('platform')
    monkeypatch.setattr(validation, 'load', lambda _:dict(instructions=100,elf=str(elf),platform=str(platform)))
    monkeypatch.setattr(validation.flow, 'profile', lambda *a:None)
    monkeypatch.setattr(validation.flow.simpoint, 'bbvs', lambda *a:([{}],100))
    monkeypatch.setattr(validation.flow, 'run_point',lambda *a:dict(ipc=.5))
    monkeypatch.setattr(validation.flow, 'run',lambda *a,**kw:dict(weighted_ipc=.55,points=[{}],status='estimated'))
    r = validation.validate(manifest,tmp_path/'out',intervals=[10,20],clusters=[1,2])
    assert len(r['rows'])==4 and r['max_observed_error_percent']==pytest.approx(10)
    assert 'no statistical confidence' in r['confidence']
    assert json.loads((tmp_path/'out/validation.json').read_text())['status']=='reported'


def test_validation_never_hides_failed_setting(tmp_path, monkeypatch):
    p=tmp_path/'input'; p.write_text('x')
    monkeypatch.setattr(validation,'load',lambda _:dict(instructions=100,elf=str(p),platform=str(p)))
    monkeypatch.setattr(validation.flow,'profile',lambda *a:None)
    monkeypatch.setattr(validation.flow.simpoint,'bbvs',lambda *a:([{}],100))
    monkeypatch.setattr(validation.flow,'run_point',lambda *a:dict(ipc=.5))
    monkeypatch.setattr(validation.flow,'run',lambda *a,**kw:dict(weighted_ipc=None,points=[{}],status='inconclusive'))
    r=validation.validate(p,tmp_path/'out',intervals=[10],clusters=[1])
    assert r['status']=='inconclusive' and r['max_observed_error_percent'] is None
