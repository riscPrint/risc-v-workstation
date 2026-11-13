import shutil
import subprocess
import pytest
from rvw.formal.power_checks import render


@pytest.mark.parametrize('kind', ['clock_gate', 'isolation', 'retention', 'test_isolation'])
@pytest.mark.parametrize('bad', [False, True])
def test_power_reference(tmp_path, kind, bad):
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus is not installed')
    if kind == 'clock_gate':
        ports = 'reg enable=1, source_low=1, clock_edge=1, work_pending=0, wakeup=0;'
        drive = f'#11; reset=0; #10; enable=0; clock_edge=0; work_pending={int(bad)}; #10;'
    elif kind == 'isolation':
        ports = 'reg power_good=1, isolated=0, consumer_use=0, output_valid=1; reg [7:0] value=0, clamp=0;'
        drive = f'#11; reset=0; #10; isolated={int(not bad)}; #10; power_good=0; output_valid=0; #10;'
    elif kind == 'retention':
        ports = 'reg power_good=1, save=0, restore=0, functional_use=0; reg [7:0] state=42;'
        drive = ('#11; reset=0; save=1; #10; save=0; power_good=0; '
                 '#10; power_good=1; restore=1; ' + f'state={43 if bad else 42}; #10; restore=0; #10;')
    else:
        ports = 'reg functional_mode=1, scan_enable=0, test_enable=0, authorized=0, power_good=1, protected_write=0, test_access=0; reg [7:0] test_output=0, clamp=0;'
        drive = f'#11; reset=0; #10; scan_enable={int(bad)}; #10;'
    (tmp_path/'monitor.sv').write_text(render(kind, 8, 4))
    (tmp_path/'tb.sv').write_text('module tb; reg clk=0; always #5 clk=~clk; reg reset=1;\n' + ports +
                                f'\nrvw_{kind} dut(.*); initial begin {drive} $finish; end endmodule')
    build = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(tmp_path/'sim'),
                            str(tmp_path/'monitor.sv'), str(tmp_path/'tb.sv')], capture_output=True, text=True, timeout=15)
    assert build.returncode == 0, build.stderr
    run = subprocess.run(['vvp', str(tmp_path/'sim')], capture_output=True, text=True, timeout=15)
    assert ('ERROR:' in run.stdout) == bad, run.stdout + run.stderr


def intent():
    return {'schema': 'rvw.power-intent/1', 'event_model': 'always_on_sampled', 'domains': [
        {'name': 'core', 'width': 8, 'wake_bound': 4, 'checks': ['clock_gate', 'isolation', 'retention', 'test_isolation'],
         'initial': 'on', 'states': {'on': {'power_good': True, 'isolated': False},
                                   'isolated': {'power_good': True, 'isolated': True},
                                   'off': {'power_good': False, 'isolated': True}},
         'transitions': [['on', 'isolated'], ['isolated', 'off'], ['off', 'isolated'], ['isolated', 'on']]}],
        'dft': [{'signal': 'core.scan', 'role': 'scan_mode', 'controllability': 'test strap only', 'observability': 'not measured'}]}


def test_intent_generation(tmp_path):
    import json
    from rvw.formal.power_intent import generate
    path = tmp_path/'intent.json'
    path.write_text(json.dumps(intent()))
    result = generate(path, tmp_path/'out')
    assert result['status'] == 'generated'
    assert result['dft'][0]['binding'] == 'not_verified'
    text = (tmp_path/'out'/'power.sv').read_text()
    assert 'module rvw_core_supply' in text
    assert 'module rvw_core_retention' in text
    assert 'previous == supply_state' in text


@pytest.mark.parametrize('change', [
    lambda p: p.update(event_model='gated_clock'),
    lambda p: p['domains'][0]['transitions'].append(['off', 'missing']),
    lambda p: p['domains'][0]['states']['off'].update(isolated=False),
    lambda p: p['domains'][0]['checks'].append('guess_physical_glitches'),
    lambda p: p['dft'][0].update(role='ATPG'),
])
def test_refuse_unsupported_intent(change):
    from rvw.formal.power_intent import validate
    obj = intent()
    change(obj)
    with pytest.raises(ValueError): validate(obj)


@pytest.mark.parametrize('bad', [False, True])
def test_native_supply_sequence(tmp_path, bad):
    from rvw.formal.power_intent import transitions
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus is not installed')
    (tmp_path/'monitor.sv').write_text(transitions(intent()['domains'][0]))
    sequence = ('#11; reset=0; #10; ' +
                ('' if bad else 'supply_state=1; isolated=1; #10; ') +
                'supply_state=2; power_good=0; isolated=1; #10; '
                'supply_state=1; power_good=1; #10; supply_state=0; isolated=0; #10;')
    (tmp_path/'tb.sv').write_text('''module tb;
reg clk=0; always #5 clk=~clk;
reg reset=1, power_good=1, isolated=0;
reg [1:0] supply_state=0;
rvw_core_supply dut(.*);
initial begin ''' + sequence + ' $finish; end endmodule')
    build = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(tmp_path/'sim'),
                            str(tmp_path/'monitor.sv'), str(tmp_path/'tb.sv')], capture_output=True, text=True, timeout=15)
    assert build.returncode == 0, build.stderr
    run = subprocess.run(['vvp', str(tmp_path/'sim')], capture_output=True, text=True, timeout=15)
    assert ('ERROR:' in run.stdout) == bad, run.stdout + run.stderr
