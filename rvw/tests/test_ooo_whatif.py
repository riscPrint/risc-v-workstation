from dataclasses import asdict
import json
import pytest
from test_ooo import cfg, trace
from rvw.ooo.whatif import what_if

pytestmark = pytest.mark.fast


def test_single_parameter_delta(tmp_path):
    c,t = tmp_path/'config',tmp_path/'trace'
    c.write_text(json.dumps(asdict(cfg())))
    trace(t)
    r = what_if(c,t,'latencies.alu',3,tmp_path/'out')
    assert r['delta']['cycles'] > 0
    assert r['delta']['ipc'] < 0
    assert r['baseline']['trace_sha256'] == r['candidate']['trace_sha256']
    assert json.loads(c.read_text())['latencies']['alu'] == 1
    assert (tmp_path/'out/report.json').is_file()
    assert 'Delta' in (tmp_path/'out/report.md').read_text()
    assert r['baseline_value'] == 1
    with pytest.raises(ValueError):
        what_if(c,t,'latencies.alu',0,tmp_path/'invalid')
    assert not (tmp_path/'invalid').exists()


@pytest.mark.parametrize('parameter,value', [('branch_speculation',True),('issue_order','in_order')])
def test_scalar_policy_change(tmp_path,parameter,value):
    c,t = tmp_path/'config',tmp_path/'trace'
    original=json.dumps(asdict(cfg()));c.write_text(original);trace(t)
    r=what_if(c,t,parameter,value,tmp_path/'out')
    assert r['candidate']['config'][parameter]==value
    assert c.read_text()==original
    assert r['baseline']['trace_sha256']==r['candidate']['trace_sha256']


def test_boolean_cannot_replace_integer(tmp_path):
    c,t=tmp_path/'config',tmp_path/'trace'
    c.write_text(json.dumps(asdict(cfg())));trace(t)
    with pytest.raises(ValueError):
        what_if(c,t,'issue_width',True,tmp_path/'out')
    assert not (tmp_path/'out').exists()
