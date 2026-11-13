import json
import pytest
from rvw.checks.qualification import summarize

pytestmark = pytest.mark.fast


def inputs(tmp_path, firings=()):
    inventory = tmp_path/'checks.json'
    inventory.write_text(json.dumps(dict(schema='rvw.checks/1',checks=[
        dict(id='one',kind='csr.state',status='inserted'),
        dict(id='two',kind='stream.stable',status='disabled',reason='project scope') ])))
    run = dict(schema='rvw.run/1',status='fail' if firings else 'pass',elf_sha256='abc',
        artifacts=dict(inventory='checks.json',checks='monitor.json'))
    (tmp_path/'c1.json').write_text(json.dumps(run))
    (tmp_path/'monitor.json').write_text(json.dumps(dict(schema='rvw.checks-run/1',inserted=1,
        elf_sha256='abc',status=run['status'],fired=len(firings),firings=list(firings))))
    return inventory, tmp_path/'c1.json'


def test_absent_runs_are_not_zero_firings(tmp_path):
    inventory, _ = inputs(tmp_path)
    result = summarize(inventory)
    row = result['counts']['csr.state']
    assert row == dict(generated=1,bound=1,proven=None,bounded=None,fired=None,
        firing_count=None,unbound=0,reasons=[],activated_simulation=0,
        no_activation_simulation=0,activation_unmeasured=1,activated_formal=0)
    assert result['status']=='inconclusive'
    assert result['counts']['stream.stable']['reasons'][0]['reason']=='project scope'


def test_clean_run_has_observed_zero_but_no_proof(tmp_path):
    inventory, run = inputs(tmp_path)
    row=summarize(inventory,[run])['counts']['csr.state']
    assert row['fired']==0 and row['proven'] is None


def test_repeat_firing_counts_one_check(tmp_path):
    inventory, run = inputs(tmp_path,[dict(id='one',kind='csr.state',count=3)])
    result=summarize(inventory,[run,run])
    assert result['status']=='findings'
    assert result['counts']['csr.state']['fired']==1
    assert result['counts']['csr.state']['firing_count']==6


@pytest.mark.parametrize('change', ['pass','inventory','hash'])
def test_conflicting_evidence_is_refused(tmp_path,change):
    inventory, run = inputs(tmp_path,[dict(id='one',kind='csr.state',count=1)])
    obj=json.loads(run.read_text())
    if change=='pass': obj['status']='pass'
    if change=='inventory': obj['artifacts']['inventory']='other.json'
    if change=='hash': obj['elf_sha256']='bad'
    run.write_text(json.dumps(obj))
    with pytest.raises(ValueError): summarize(inventory,[run])


def test_formal_results_are_joined_only_by_declared_requirements(tmp_path):
    inventory, _=inputs(tmp_path)
    formal=tmp_path/'formal.json'
    formal.write_text(json.dumps(dict(schema='rvw.formal-regress/1',properties=[
        dict(id='proof',status='pass',formal_status='proven',requirements=['one']),
        dict(id='bmc',status='pass',formal_status='bounded-pass',requirements=['one'])])))
    row=summarize(inventory,formal=formal)['counts']['csr.state']
    assert row['proven']==0 and row['bounded']==0
    assert row['fired'] is None


def test_unbound_firing_is_refused(tmp_path):
    inventory,run=inputs(tmp_path,[dict(id='two',kind='stream.stable',count=1)])
    with pytest.raises(ValueError,match='absent from bound'): summarize(inventory,[run])


def test_formal_unknown_requirement_is_refused(tmp_path):
    inventory,_=inputs(tmp_path)
    formal=tmp_path/'formal.json'
    formal.write_text(json.dumps(dict(schema='rvw.formal-regress/1',properties=[
        dict(id='proof',status='pass',formal_status='proven',requirements=['typo'])])))
    with pytest.raises(ValueError,match='absent from bound'): summarize(inventory,formal=formal)


def test_cli_report_preserves_inconclusive(tmp_path,capsys):
    from argparse import Namespace
    from rvw.checks.cli import report_run
    inventory,run=inputs(tmp_path)
    out=tmp_path/'summary.json'
    assert report_run(Namespace(inventory=inventory,run=[run],formal=None,out=out))==3
    assert json.loads(out.read_text())['status']=='inconclusive'


def test_partial_field_proof_cannot_prove_a_packed_check(tmp_path):
    inventory,_=inputs(tmp_path)
    formal=tmp_path/'formal.json'
    formal.write_text(json.dumps(dict(schema='rvw.formal-regress/1',properties=[
        dict(id='field0',status='pass',formal_status='proven',requirements=['one']),
        dict(id='field1',status='fail',formal_status='failed',requirements=['one'])])))
    row=summarize(inventory,formal=formal)['counts']['csr.state']
    assert row['proven']==row['bounded']==0


def test_activation_counts_and_formal_cover_gate(tmp_path):
    inventory, run = inputs(tmp_path)
    monitor = tmp_path/'monitor.json'
    data = json.loads(monitor.read_text())
    data['activations'] = [dict(id='one', count=0)]
    monitor.write_text(json.dumps(data))
    assert summarize(inventory,[run])['activation'][0]['simulation_status']=='no_activation'
    data['activations'][0]['count']=7
    monitor.write_text(json.dumps(data))
    assert summarize(inventory,[run])['activation'][0]['simulation_count']==7
    formal=tmp_path/'formal.json'
    formal.write_text(json.dumps(dict(schema='rvw.formal-regress/1',properties=[
        dict(id='proof',status='pass',formal_status='proven',requirements=['one'],
             activation=dict(status='reached',depth=4))])))
    assert summarize(inventory,formal=formal)['counts']['csr.state']['proven']==1


def test_activation_rejects_unknown_duplicate_or_negative(tmp_path):
    inventory, run = inputs(tmp_path)
    monitor=tmp_path/'monitor.json'
    data=json.loads(monitor.read_text())
    for acts in ([dict(id='bad',count=1)], [dict(id='one',count=-1)],
                 [dict(id='one',count=1)]*2):
        data['activations']=acts
        monitor.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            summarize(inventory,[run])
