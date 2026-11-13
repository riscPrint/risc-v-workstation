"""Regression cases from the result-builder sweep. No native work runs."""
import json
import pytest
from rvw.sec.suite import collect
from rvw.sec.pairs import compare
from rvw.uvm.features import table
from rvw.uvm.qualification import generate
from rvw.debug import ntrace, ntrace_check
from rvw.formal import rtl_grid, grid_farm

pytestmark = pytest.mark.fast


def write(path, data):
    path.write_text(json.dumps(data))
    return path


@pytest.mark.parametrize('extra', [dict(status='inconclusive'),
    dict(verdict='inconclusive'), dict(verdict='unsupported'), dict(verdict='not_installed'),
    dict(inconclusive='missing observation')])
def test_security_complete_flag_does_not_override_missing_evidence(tmp_path, extra):
    data=dict(schema='rvw.sec/1',technique='ift',status='no_leak_observed',complete=True,findings=[])
    data.update(extra)
    result=collect([write(tmp_path/'child.json',data)],tmp_path/'out')
    assert result['status']=='inconclusive' and result['complete'] is False
    assert json.loads((tmp_path/'out/results.json').read_text())['tests'][0]['status']=='error'


def test_conclusive_security_violation_still_has_complete_evidence(tmp_path):
    data=dict(schema='rvw.sec/1',technique='ift',status='violation',complete=True,findings=[{'cycle':1}])
    result=collect([write(tmp_path/'child.json',data)],tmp_path/'out')
    assert result['status']=='violation' and result['complete'] is True


@pytest.mark.parametrize('modes', [(3,3),(1,3),(None,None)])
def test_missing_observer_retirements_cannot_establish_no_leak(modes):
    a=dict(public={},secret=1,reference=[dict(mode=modes[0],pc=0)],observations={'cycles':1})
    b=dict(public={},secret=2,reference=[dict(mode=modes[1],pc=0)],observations={'cycles':1})
    plan=dict(contract='constant-time',clauses=['pc'],observations=['cycles'],observer_mode=1)
    assert compare(a,b,plan)['status']=='inconclusive'


@pytest.mark.parametrize('extra', [dict(inconclusive='missing binding'),dict(verdict='inconclusive'),
                                    dict(verdict='unsupported'),dict(verdict='not_installed')])
def test_uvm_features_and_qualification_require_conclusive_pass(tmp_path, extra):
    tests=[dict(id=name,status='pass',**extra) for name in ('phases_config_factory_tlm','spike_retirements')]
    path=write(tmp_path/'results.json',dict(schema='rvw.results/1',run_id='r',suite='fixture',core='fixture',
        config='fixture',created='fixture',source={},tests=tests))
    assert table(path)['features'][0]['status']=='not established'
    probes=write(tmp_path/'probes.json',dict(probes=[]))
    out=tmp_path/'matrix.md';generate(path,probes,out)
    assert '| spike_retirements | 1 | not established |' in out.read_text()


def test_empty_packet_vector_does_not_qualify_a_trace_adapter(tmp_path):
    rows=ntrace_check.verify_vectors([dict(bytes='',messages=[])],ntrace.normalize({}))
    assert rows[0]['status']=='inconclusive'
    adapter=tmp_path/'adapter.toml'
    adapter.write_text("schema='rvw.trace-adapter/1'\nname='fixture'\ncodec="+json.dumps(ntrace.CODEC)+
        "\nspecification='fixture'\nlicense='fixture'\n[[vectors]]\nbytes=''\nmessages=[]\n")
    result=ntrace_check.load_adapter(adapter)
    assert result['verified'] is False
    with pytest.raises(ntrace_check.AdapterError):
        ntrace_check.params_for(adapter=result)


@pytest.mark.parametrize('distributed', [False,True])
def test_empty_rtl_grid_fails_before_any_dispatch(tmp_path,monkeypatch,distributed):
    def forbidden(*args,**kwargs):
        raise AssertionError('no solver or SSH dispatch is allowed')
    monkeypatch.setattr(rtl_grid,'race',forbidden)
    monkeypatch.setattr(grid_farm,'run_group',forbidden)
    model=dict(input_kind='rtl',properties={},blobs={});out=tmp_path/'out'
    with pytest.raises(ValueError,match='needs properties'):
        if distributed:grid_farm.distributed(model,[dict(name='fixture',address='unused')],out)
        else:rtl_grid.local(model,out)
    assert not out.exists()


@pytest.mark.parametrize('extra',[dict(ignored_feature_warning=True),dict(inconclusive='missing observation'),
                                  dict(verdict='unsupported'),dict(verdict='not_installed')])
def test_uvm_probe_positive_status_does_not_override_blockers(tmp_path,extra):
    cpu=write(tmp_path/'cpu.json',dict(schema='rvw.results/1',run_id='r',suite='fixture',core='fixture',
        config='fixture',created='fixture',source={},tests=[]))
    probe=dict(feature='transition',status='pass',**extra)
    probes=write(tmp_path/'probes.json',dict(probes=[probe]))
    out=tmp_path/'matrix.md';generate(cpu,probes,out)
    line=next(line for line in out.read_text().splitlines() if '| SV transition |' in line)
    assert '| not established' in line and '| pass' not in line
