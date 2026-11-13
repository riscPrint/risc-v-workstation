"""Direct Verilator snapshot smoke. This does not use the Spinal bridge or a core."""
import hashlib
import shutil
from pathlib import Path

import pytest

from rvw.common.proc import run_group
from rvw.sim import checkpoint as ck


RTL = '''module SnapshotTop(input clk, input reset, input [31:0] data,
                           output reg [31:0] value);
 always @(posedge clk) if (reset) value <= 0; else value <= value + data;
 endmodule
'''
CPP = r'''
#include "VSnapshotTop.h"
#include "verilated.h"
#include "verilated_save.h"
#include "Checkpoint.h"
#include <iostream>
#include <string>
struct State {
  uint32_t cycle = 0, rng = 317, memory = 0, monitor = 0;
  void transfer(VerilatedSerialize& s) { s << cycle << rng << memory << monitor; }
  void transfer(VerilatedDeserialize& s) { s >> cycle >> rng >> memory >> monitor; }
};
int main(int argc, char** argv) {
  VerilatedContext context;
  VSnapshotTop top{&context};
  State harness;
  auto& cycle = harness.cycle; auto& rng = harness.rng;
  auto& memory = harness.memory; auto& monitor = harness.monitor;
  bool restoring = std::string(argv[1]) == "restore";
  if (restoring) {
    riscvsim::restore(argv[2], context, top, harness, true);
  } else {
    top.clk = 0; top.reset = 1; top.data = 0; top.eval();
    top.clk = 1; context.timeInc(1); top.eval();
    top.clk = 0; context.timeInc(1); top.eval(); top.reset = 0;
  }
  while (cycle < 20) {
    rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
    memory += rng & 255;
    top.data = memory;
    top.clk = 1; context.timeInc(1); top.eval();
    top.clk = 0; context.timeInc(1); top.eval();
    ++cycle; ++monitor;
    if (cycle == 8 && !restoring) {
      riscvsim::save(argv[2], context, top, harness, true);
      std::cout << "state " << cycle << " " << rng << " " << memory << " " << monitor << "\n";
    }
    if (cycle > 8) std::cout << cycle << " " << top.value << " " << rng << " " << memory << " " << monitor << "\n";
  }
  top.final();
}
'''


def test_fresh_native_restore_matches_uninterrupted_suffix(tmp_path):
    verilator = shutil.which('verilator')
    if not verilator or not shutil.which('make'):
        pytest.skip('Verilator and make are required')
    rtl, cpp = tmp_path / 'SnapshotTop.sv', tmp_path / 'main.cpp'
    rtl.write_text(RTL); cpp.write_text(CPP)
    obj = tmp_path / 'obj'
    built = run_group(['nice', '-n', '10', verilator, '--cc', '--exe', '--build',
        '--savable', '--top-module', 'SnapshotTop', '--Mdir', str(obj),
        str(rtl), str(cpp), '-CFLAGS', '-I' + str(Path(__file__).resolve().parents[2] / 'RiscvSim/src/main/cpp'), '-o', 'snapshot'], timeout=120, capture=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    binary = obj / 'snapshot'
    native = tmp_path / 'native.bin'
    baseline = run_group(['nice', '-n', '10', str(binary), 'save', str(native)], timeout=10, capture=True, text=True)
    assert baseline.returncode == 0, baseline.stderr
    lines = baseline.stdout.splitlines()
    _, cycle, rng, memory, monitor = lines[0].split()
    expected = '\n'.join(lines[1:]) + '\n'
    identity = {name: hashlib.sha256(data).hexdigest() for name, data in dict(
        rtl=rtl.read_bytes(), native_build=binary.read_bytes(), harness=cpp.read_bytes(),
        stimulus=b'seed=317;steps=20').items()}

    class Port:
        output = None
        def quiescent(self): return True  # executable saves at the falling edge after eval
        def external_effects(self): return []
        def save(self):
            state = {name: {} for name in ck.STATE}
            state.update(scheduler={'time': 2 + 2 * int(cycle)}, clock={'phase': 0},
                memory={'word': int(memory)}, rng={'xorshift32': int(rng)},
                monitors={'completed': int(monitor)}, counters={'cycles': int(cycle)})
            return native.read_bytes(), state
        def validate_restore(self, model, state):
            assert state['clock'] == {'phase': 0}
            assert state['counters'] == {'cycles': 8}
        def restore(self, model, state):
            restored = tmp_path / 'restored.bin'
            restored.write_bytes(model)
            run = run_group(['nice', '-n', '10', str(binary), 'restore', str(restored)], timeout=10, capture=True, text=True)
            assert run.returncode == 0, run.stderr
            self.output = run.stdout

    saved = tmp_path / 'snapshot.json'
    ck.save(Port(), saved, identity=identity)
    fresh = Port()
    ck.restore(fresh, saved, identity=identity)
    assert fresh.output == expected
