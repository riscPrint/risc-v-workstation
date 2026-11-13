"""Spinal enum element names in wave values and expressions (cluster database fixture)."""
import json
import subprocess
import sys

import pytest

from rvw.wave import search, temporal, typed
from rvw.wave.vcd import WaveError

FSM = """$timescale 1ns $end
$scope module TOP $end
$scope module GcdCluster $end
$var wire 1 ! clk $end
$var wire 2 " ctrl_fsm_stateReg [1:0] $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
b00 "
$end
#5
1!
b01 "
#10
0!
#15
1!
b10 "
#20
0!
#25
1!
b11 "
#30
0!
"""


@pytest.fixture
def wave(tmp_path):
    p = tmp_path / 'fsm.vcd'
    p.write_text(FSM)
    return str(p)


def test_parse_enum():
    info = typed.parse_enum('ctrl_fsm@seq[2]{BOOT=0,idle=1,run=2,done=3}')
    assert info['enum'] == 'ctrl_fsm' and info['elements']['run'] == 2 and info['names'][3] == 'done'
    assert typed.parse_enum('UInt') is None
    assert typed.label(info, '0x2') == 'run' and typed.label(info, 'b1x') is None


def test_enum_values_and_literals(cluster_db, wave):
    info = typed.enums(str(cluster_db))
    assert 'TOP.GcdCluster.ctrl_fsm_stateReg' in info
    r = search.find(wave, "ctrl_fsm_stateReg == 'run'", enums=info)
    assert r['matches'] == [{'start': 15, 'end': 25}]
    with pytest.raises(WaveError, match='not an element'):
        search.find(wave, "ctrl_fsm_stateReg == 'running'", enums=info)
    s = temporal.sequence(wave, "ctrl_fsm_stateReg == 'idle' ##1 ctrl_fsm_stateReg == 'run'", enums=info)
    assert s['matched'] == 1


def test_cli(cluster_db, wave):
    run = lambda *a: subprocess.run([sys.executable, '-m', 'rvw', 'wave', *a], capture_output=True, text=True)
    out = run('changes', wave, 'state', '--db', str(cluster_db), '--json')
    assert out.returncode == 0, out.stderr
    assert [c.get('enum') for c in json.loads(out.stdout)['changes']] == ['BOOT', 'idle', 'run', 'done']
    out = run('sample', wave, 'state', '--at', '20', '--db', str(cluster_db))
    assert 'TOP.GcdCluster.ctrl_fsm_stateReg = 0x2 (run)' in out.stdout
    out = run('find', wave, "ctrl_fsm_stateReg == 'done'", '--db', str(cluster_db), '--json')
    assert json.loads(out.stdout)['first'] == 25


STREAM = """$timescale 1ns $end
$scope module TOP $end
$scope module GcdCluster $end
$var wire 1 ! io_cmd_valid $end
$var wire 1 " io_cmd_ready $end
$var wire 16 # io_cmd_payload_0 [15:0] $end
$var wire 16 $ io_cmd_payload_1 [15:0] $end
$var wire 2 % ctrl_fsm_stateReg [1:0] $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
1!
1"
b1100 #
b1000 $
b10 %
$end
#10
"""


def test_typed_bundle_value(cluster_db, tmp_path):
    p = tmp_path / 's.vcd'
    p.write_text(STREAM)
    r = typed.value(str(cluster_db), str(p), 'io.cmd', 5)
    assert r['type'] == 'Stream' and r['fire'] is True
    assert r['value']['payload']['0']['value'] == '0xc' and r['value']['payload']['1']['value'] == '0x8'
    assert r['value']['valid']['wave'] == 'TOP.GcdCluster.io_cmd_valid'
    s = typed.value(str(cluster_db), str(p), 'ctrl.fsm.stateReg', 5)
    assert s['value']['enum'] == 'run'
    out = subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'value', str(p), 'io.cmd', '--at', '5',
                          '--db', str(cluster_db)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert 'fire=True' in out.stdout and 'payload:' in out.stdout
