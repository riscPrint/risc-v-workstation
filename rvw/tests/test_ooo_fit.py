import json
import pytest
from rvw.ooo.fit import fit

pytestmark=pytest.mark.fast


def test_fit_uses_training_only_and_keeps_heldout(tmp_path):
    from test_ooo_evidence import inputs
    cal,data=inputs(tmp_path)
    p=tmp_path/'fit.json';p.write_text(json.dumps(dict(schema='rvw.ooo-fit-plan/1',calibration_plan=cal.name,
                                                    parameters={'latencies.alu':[1,4,8]})))
    r=fit(p,tmp_path/'first')
    # Rebind only heldout timing. The selected candidate must stay unchanged.
    for sample in data['samples'][1:]:
        c1=tmp_path/sample['c1'];obs=json.loads(c1.read_text());obs['cycles']=10000;c1.write_text(json.dumps(obs))
        from rvw.ooo.evidence import digest
        ep=tmp_path/sample['events'];e=json.loads(ep.read_text());e['c1_sha256']=digest(c1);ep.write_text(json.dumps(e))
    changed=fit(p,tmp_path/'second')
    assert changed['best']==r['best']
    assert changed['heldout'][0]['rtl_cycles']==10000
    assert r['accuracy_status']=='inconclusive'
    assert len(r['candidates'])==3


def test_missing_training_counter_is_not_a_zero(tmp_path):
    from test_ooo_evidence import inputs
    cal,data=inputs(tmp_path)
    ev=tmp_path/data['samples'][0]['events']
    row=json.loads(ev.read_text());row['counts']={};ev.write_text(json.dumps(row))
    p=tmp_path/'fit.json';p.write_text(json.dumps(dict(schema='rvw.ooo-fit-plan/1',calibration_plan=cal.name,
                                                    parameters={'latencies.alu':[1]})))
    with pytest.raises(ValueError,match='training event is missing'):
        fit(p,tmp_path/'out')
