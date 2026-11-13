import importlib.util
import json
from pathlib import Path
import pytest

pytestmark=pytest.mark.fast
spec=importlib.util.spec_from_file_location('check_group',Path(__file__).resolve().parents[2]/'SpinalChecks/scripts/prepare-check-group.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


def inputs(tmp_path):
    rtl=tmp_path/'rtl';rtl.mkdir()
    (rtl/'Unit.v').write_text('module Unit(input clk,reset);\nwire bad=0, state_bad=0, trigger=1;\nendmodule\n')
    clock=dict(clock='clk',reset='reset',edge='RISING',reset_active='HIGH')
    rows=[dict(id='csr.read:x',kind='csr.read',status='inserted',path='',module='Unit',fail_signal='bad',trigger_signal='trigger',clock_domain=clock),
          dict(id='csr.state:x',kind='csr.state',status='inserted',path='',module='Unit',fail_signal='state_bad',clock_domain=clock)]
    inv=tmp_path/'checks.json';inv.write_text(json.dumps(dict(schema='rvw.checks/1',formal=True,toplevel='Unit',checks=rows)))
    return rtl,inv


def test_implied_state_is_asserted_not_assumed(tmp_path):
    rtl,inv=inputs(tmp_path)
    result=helper.prepare(rtl,inv,tmp_path/'out','csr.read:x')
    assert result['helpers']==['csr.state:x']
    assert result['assertions']==2
    text=(tmp_path/'out/0/monitor.sv').read_text()
    assert text.count('assert(')==2
    assert 'assume(' not in text
    assert '.helper_0(state_bad)' in (tmp_path/'out/0/Unit.v').read_text()
    assert 'helper_0' in (tmp_path/'out/0/activation.sv').read_text()
    assert not (tmp_path/'out/regress.toml').exists()


def test_reject_helper_from_different_clock_domain(tmp_path):
    rtl,inv=inputs(tmp_path)
    data=json.loads(inv.read_text());data['checks'][1]['clock_domain']['clock']='other_clk';inv.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='same module instance and clock domain'):
        helper.prepare(rtl,inv,tmp_path/'out','csr.read:x')
