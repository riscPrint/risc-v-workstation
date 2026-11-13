import importlib.util
import json
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
spec = importlib.util.spec_from_file_location('connected_formal', Path(__file__).resolve().parents[2] /
    'SpinalChecks/scripts/prepare-connected-formal.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def test_separate_monitor_survives_native_assert_removal(tmp_path):
    rtl = tmp_path/'rtl'; rtl.mkdir()
    (rtl/'Unit.v').write_text('module Unit(input clk,reset);\nwire check_fail = 0;\n'
                              'always @(posedge clk) assert(!check_fail);\nendmodule\n')
    (rtl/'Unit.mem.bin').write_text('00\n')
    inventory = tmp_path/'checks.json'
    inventory.write_text(json.dumps(dict(schema='rvw.checks/1', formal=True, toplevel='Unit', checks=[
        dict(id='stream.valid_hold:x', status='inserted', path='', fail_signal='check_fail',
             clock_domain=dict(clock='clk', reset='reset', edge='RISING', reset_active='HIGH'))])))
    out = tmp_path/'out'
    helper.prepare(rtl, inventory, out, ['stream.valid_hold:x'])
    job = (out/'0/job.sby').read_text()
    assert job.index('chformal -assert -remove') < job.index('read_verilog -formal -sv monitor.sv')
    assert 'depth 4' in job
    assert (out/'0/Unit.mem.bin').read_text() == '00\n'
    assert 'Unit.mem.bin' in job
    assert (out/'0/monitor.sv').read_text().count('assert(') == 1
    assert '.fail(check_fail)' in (out/'0/Unit.v').read_text()
    assert 'requirements = ["stream.valid_hold:x"]' in (out/'regress.toml').read_text()
    data = json.loads(inventory.read_text()); data['formal'] = False
    inventory.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='formal-mode'):
        helper.prepare(rtl, inventory, tmp_path/'invalid', ['stream.valid_hold:x'])


def test_nested_check_keeps_root_and_rejects_shared_owner_module(tmp_path):
    rtl = tmp_path/'rtl'; rtl.mkdir()
    text = ('module Unit(input clk, reset);\nChild child(.clk(clk), .reset(reset));\nendmodule\n'
            'module Child(input clk,reset);\nwire check_fail = 0;\nendmodule\n')
    (rtl/'Unit.v').write_text(text)
    inventory = tmp_path/'checks.json'
    inventory.write_text(json.dumps(dict(schema='rvw.checks/1', formal=True, toplevel='Unit', checks=[
        dict(id='stream.valid_hold:child.x', status='inserted', path='child', module='Child', fail_signal='child.check_fail',
             clock_domain=dict(clock='child.clk', reset='child.reset', edge='RISING', reset_active='HIGH'))])))
    helper.prepare(rtl, inventory, tmp_path/'out', ['stream.valid_hold:child.x'])
    assert 'prep -top Unit' in (tmp_path/'out/0/job.sby').read_text()
    generated = (tmp_path/'out/0/Unit.v').read_text()
    assert generated.index('module Child') < generated.index('rvw_selected_check_instance')
    (rtl/'Unit.v').write_text(text.replace('Child child(', 'Child other(.clk(clk), .reset(reset));\nChild child('))
    with pytest.raises(ValueError, match='one instance'):
        helper.prepare(rtl, inventory, tmp_path/'shared', ['stream.valid_hold:child.x'])

def test_trigger_gets_independent_cover_at_same_depth(tmp_path):
    rtl=tmp_path/'rtl'; rtl.mkdir()
    (rtl/'Unit.v').write_text('module Unit(input clk,reset);\nwire bad=0, trigger=1;\nendmodule\n')
    inventory=tmp_path/'checks.json'
    inventory.write_text(json.dumps(dict(schema='rvw.checks/1',formal=True,toplevel='Unit',checks=[
        dict(id='enum.legal:x',status='inserted',path='',fail_signal='bad',trigger_signal='trigger',
             clock_domain=dict(clock='clk',reset='reset',edge='RISING',reset_active='HIGH'))])))
    helper.prepare(rtl,inventory,tmp_path/'out',['enum.legal:x'])
    assert 'activation_sby = "0/activation.sby"' in (tmp_path/'out/regress.toml').read_text()
    assert 'mode cover' in (tmp_path/'out/0/activation.sby').read_text()
    assert '.fail(trigger)' in (tmp_path/'out/0/activation_Unit.v').read_text()
    assert '.fail(bad)' in (tmp_path/'out/0/Unit.v').read_text()
