import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import pytest
from rvw.common.proc import run_group
from rvw.memory.tilelink_bind import FIELDS, generate


def fixture(tmp_path):
    db = tmp_path/'design.sqlite'
    connection = sqlite3.connect(db)
    connection.executescript('''CREATE TABLE components(id INTEGER, module TEXT);
        CREATE TABLE bundles(id INTEGER, component_id INTEGER, class_name TEXT);
        CREATE TABLE signals(id INTEGER, component_id INTEGER, name TEXT, width INTEGER, pruned INTEGER);''')
    connection.execute('INSERT INTO components VALUES (1, "top")')
    connection.executemany('INSERT INTO bundles VALUES (?, 1, "spinal.lib.bus.tilelink.Bus")', [(1,), (2,)])
    config = dict(schema='rvw.tlc-bind/1', fairness='bounded ready/response service', oracle_kind='independent-stimulus', source_bits=1,
                  sink_bits=1, address_bits=16, data_bits=64, size_bits=4, line_bytes=8,
                  line_address='0x0', bound_cycles=8, trunk_dirty=True, clients=[])
    declarations, initial = ['reg clock=0; always #5 clock=~clock;'], []
    identity = 0
    def signal(name, width):
        nonlocal identity
        identity += 1
        connection.execute('INSERT INTO signals VALUES (?,1,?,?,0)', (identity, name, width))
        declarations.append(f'reg [{width-1}:0] {name};')
        initial.append(f'{name}=0;')
        return identity
    for name, width in [('clock', 1), ('reset', 1), ('expected_data', 64)]:
        if name == 'clock':
            identity += 1
            connection.execute('INSERT INTO signals VALUES (?,1,?,1,0)', (identity, name))
            config[name] = identity
        else:
            config[name] = signal(name, width)
    widths = dict(source=1, sink=1, address=16, data=64, size=4)
    for client in range(2):
        config['clients'].append(dict(bundle_id=client+1, signals={
            name: signal(f'c{client}_{name}', widths.get(width, width)) for name, width in FIELDS.items()}))
    connection.commit(); connection.close()
    profile = tmp_path/'profile.json'; profile.write_text(json.dumps(config))
    return db, profile, config, declarations, initial


def test_typed_database_bind_and_no_clobber(tmp_path):
    db, profile, config, _, _ = fixture(tmp_path)
    result = generate(db, profile, tmp_path/'out')
    assert result['status'] == 'generated' and not result['executed']
    assert 'bind top rvw_tlc_monitor' in Path(result['bind']).read_text()
    assert '.c1_e_sink(c1_e_sink)' in Path(result['bind']).read_text()
    with pytest.raises(FileExistsError):
        generate(db, profile, tmp_path/'out')
    config['clients'][0]['signals'].pop('e_sink')
    profile.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='complete'):
        generate(db, profile, tmp_path/'bad')


def test_native_bound_channel_monitor_with_seeded_defects(tmp_path):
    tool = shutil.which('verilator')
    if not tool:
        pytest.skip('Verilator is not installed')
    db, profile, _, declarations, initial = fixture(tmp_path)
    result = generate(db, profile, tmp_path/'out')
    program = '''
integer fault;
initial begin
  if(!$value$plusargs("FAULT=%d",fault)) fault=0;
  INIT
  reset=1; expected_data=64'h1;
  c0_a_ready=1;c0_b_ready=1;c0_c_ready=1;c0_d_ready=1;c0_e_ready=1;
  c1_a_ready=1;c1_b_ready=1;c1_c_ready=1;c1_d_ready=1;c1_e_ready=1;
  c0_a_size=3;c0_b_size=3;c0_c_size=3;c0_d_size=3;
  c1_a_size=3;c1_b_size=3;c1_c_size=3;c1_d_size=3;
  repeat(2) @(negedge clock); reset=0;
  c0_a_valid=1;c0_a_opcode=6;c0_a_param=1;
  @(negedge clock);c0_a_valid=0;c0_d_valid=1;c0_d_opcode=5;c0_d_param=0;c0_d_data=1;
  @(negedge clock);c0_d_valid=0;c0_e_valid=1;
  @(negedge clock);c0_e_valid=0;c1_a_valid=1;c1_a_opcode=6;c1_a_param=0;
  @(negedge clock);c1_a_valid=0;c0_b_valid=1;c0_b_opcode=6;c0_b_param=1;
  @(negedge clock);c0_b_valid=0;c0_c_valid=(fault!=1);c0_c_opcode=5;c0_c_param=0;c0_c_data=(fault==5)?0:1;
  @(negedge clock);c0_c_valid=0;c1_d_valid=(fault!=4);c1_d_opcode=5;c1_d_param=1;c1_d_data=(fault==2)?0:1;
  @(negedge clock);c1_d_valid=0;c1_e_valid=(fault!=3 && fault!=4);
  @(negedge clock);c1_e_valid=0;
  repeat(12) @(negedge clock);
  $display("RVW_DONE");$finish;
end
'''.replace('INIT', '\n  '.join(initial))
    top = tmp_path/'top.sv'
    top.write_text('module top;\n'+'\n'.join(declarations)+'\n'+program+'\nendmodule\n')
    obj = tmp_path/'obj'
    build = run_group(['nice', '-n', '10', tool, '--binary', '--timing', '--top-module', 'top',
                       '-Wno-fatal', '--Mdir', str(obj), '-o', 'smoke', result['monitor'], result['bind'], str(top)],
                      timeout=100, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert build.returncode == 0, build.stderr[-5000:]
    for fault in range(6):
        run = run_group(['nice', '-n', '10', str(obj/'smoke'), f'+FAULT={fault}'], cwd=tmp_path, timeout=5,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if fault:
            assert run.returncode != 0 and 'RVW_DONE' not in run.stdout
            assert 'RVW' in run.stdout or 'rvw' in run.stdout + run.stderr
        else:
            assert run.returncode == 0 and 'RVW_DONE' in run.stdout, run.stdout + run.stderr
