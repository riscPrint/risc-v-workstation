import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import pytest
from rvw.common.proc import run_group
from rvw.memory.tilelink_bind import generate
from test_memory_tilelink_bind import fixture


def test_native_complete_multibeat_messages_and_faults(tmp_path):
    tool = shutil.which('verilator')
    if not tool:
        pytest.skip('Verilator is not installed')
    db, profile, config, declarations, initial = fixture(tmp_path)
    config['line_bytes'] = 64
    config['bound_cycles'] = 32
    profile.write_text(json.dumps(config))
    with sqlite3.connect(db) as connection:
        connection.execute('UPDATE signals SET width=512 WHERE id=?', (config['expected_data'],))
    declarations = [line.replace('reg [63:0] expected_data;', 'reg [511:0] expected_data;') for line in declarations]
    result = generate(db, profile, tmp_path/'out')
    assert result['beats_per_line'] == 8
    pattern = int.from_bytes(bytes(range(64)), 'little')
    program = '''
integer fault,beat;
initial begin
  if(!$value$plusargs("FAULT=%d",fault)) fault=0;
  INIT
  reset=1; expected_data=512'hPATTERN;
  c0_a_ready=1;c0_b_ready=1;c0_c_ready=1;c0_d_ready=1;c0_e_ready=1;
  c1_a_ready=1;c1_b_ready=1;c1_c_ready=1;c1_d_ready=1;c1_e_ready=1;
  c0_a_size=6;c0_b_size=6;c0_c_size=6;c0_d_size=6;
  c1_a_size=6;c1_b_size=6;c1_c_size=6;c1_d_size=6;
  repeat(2) @(negedge clock); reset=0;
  c0_a_valid=1;c0_a_opcode=6;c0_a_param=1;
  @(negedge clock);c0_a_valid=0;c0_d_valid=1;c0_d_opcode=5;c0_d_param=0;
  for(beat=0;beat<8;beat=beat+1) begin
    c0_d_data=expected_data[beat*64 +: 64]; @(negedge clock);
  end
  c0_d_valid=0;c0_e_valid=1;
  @(negedge clock);c0_e_valid=0;
  expected_data[7:0]=8'hff;
  if(fault==6) begin
    c0_c_valid=1;c0_c_opcode=7;c0_c_param=1;
    for(beat=0;beat<7;beat=beat+1) begin
      c0_c_data=expected_data[beat*64 +: 64]; @(negedge clock);
    end
    c0_c_valid=0; repeat(40) @(negedge clock);
  end else begin
    c1_a_valid=1;c1_a_opcode=6;c1_a_param=0;
    @(negedge clock);c1_a_valid=0;c0_b_valid=1;c0_b_opcode=6;c0_b_param=1;
    @(negedge clock);c0_b_valid=0;
    if(fault!=1) begin
      c0_c_valid=1;c0_c_opcode=5;c0_c_param=0;
      for(beat=0;beat<((fault==3)?7:8);beat=beat+1) begin
        c0_c_data=expected_data[beat*64 +: 64];
        if(fault==5 && beat==4) c0_c_data=c0_c_data^1;
        @(negedge clock);
      end
      c0_c_valid=0;
    end
    if(fault==3) repeat(40) @(negedge clock);
    c1_d_valid=1;c1_d_opcode=5;c1_d_param=1;
    for(beat=0;beat<8;beat=beat+1) begin
      c1_d_data=expected_data[beat*64 +: 64];
      if(fault==2 && beat==3) c1_d_data=c1_d_data^1;
      if(fault==4 && beat==4) c1_d_source=1;
      @(negedge clock);
    end
    c1_d_valid=0;c1_e_valid=1;
    @(negedge clock);c1_e_valid=0;
    c0_c_valid=1;c0_c_opcode=6;c0_c_param=2;
    @(negedge clock);c0_c_valid=0;c0_d_valid=1;c0_d_opcode=6;
    @(negedge clock);c0_d_valid=0;
    c1_c_valid=1;c1_c_opcode=6;c1_c_param=2;
    @(negedge clock);c1_c_valid=0;c1_d_valid=1;c1_d_opcode=6;c1_d_source=0;
    @(negedge clock);c1_d_valid=0;
  end
  repeat(40) @(negedge clock);
  $display("RVW_DONE");$finish;
end
'''.replace('INIT', '\n  '.join(initial)).replace('PATTERN', f'{pattern:0128x}')
    top = tmp_path/'top.sv'
    top.write_text('module top;\n'+'\n'.join(declarations)+'\n'+program+'\nendmodule\n')
    obj = tmp_path/'obj'
    build = run_group(['nice', '-n', '10', tool, '--binary', '--timing', '--top-module', 'top', '-Wno-fatal',
                       '--Mdir', str(obj), '-o', 'smoke', result['monitor'], result['bind'], str(top)],
                      timeout=100, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert build.returncode == 0, build.stderr[-5000:]
    for fault in range(7):
        run = run_group(['nice', '-n', '10', str(obj/'smoke'), f'+FAULT={fault}'], cwd=tmp_path, timeout=5,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if fault:
            assert run.returncode != 0 and 'RVW_DONE' not in run.stdout, (fault, run.stdout, run.stderr)
            if fault == 4:
                assert 'header changed' in run.stdout+run.stderr
            if fault == 6:
                assert 'incomplete data message' in run.stdout+run.stderr
        else:
            assert run.returncode == 0 and 'RVW_DONE' in run.stdout, run.stdout+run.stderr
