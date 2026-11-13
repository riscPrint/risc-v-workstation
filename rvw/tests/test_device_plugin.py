import os
from pathlib import Path
import shutil

import pytest

from rvw.common.proc import run_group

HEADER = Path(__file__).resolve().parents[2] / 'RiscvSim/src/main/cpp'
PLUGIN = r'''
#include "DevicePlugin.h"
#include <cstring>
using namespace riscvsim;
struct State { uint64_t value; uint64_t cycle; };
void* create(const char*, uint64_t seed) { return new State{seed, 0}; }
void destroy(void* p) { delete static_cast<State*>(p); }
int read(void* p, uint64_t, uint32_t, uint64_t* value) { *value = static_cast<State*>(p)->value; return 0; }
int write(void* p, uint64_t, uint32_t, uint64_t value, uint64_t) { static_cast<State*>(p)->value = value; return 0; }
int tick(void* p, uint64_t cycle) { static_cast<State*>(p)->cycle = cycle; return 0; }
uint64_t irq(void* p) { return static_cast<State*>(p)->cycle >= 8; }
size_t snapshot(void* p, uint8_t* out, size_t size) {
  if (!out) return sizeof(State);
  if (size != sizeof(State)) return 0;
  std::memcpy(out, p, size); return size;
}
int restore(void* p, const uint8_t* in, size_t size) {
  if (size != sizeof(State)) return 1;
  std::memcpy(p, in, size); return 0;
}
extern "C" const DeviceApiV1* rvw_device_plugin_v1() {
  static DeviceApiV1 api{1, create, destroy, read, write, tick, irq, snapshot, restore};
  return &api;
}
'''
MAIN = r'''
#include "DevicePlugin.h"
#include <cassert>
extern "C" void* rvw_device_open(const char*, const char*, uint64_t);
extern "C" void rvw_device_close(void*);
extern "C" int rvw_device_read(void*, uint64_t, unsigned, uint64_t*);
extern "C" int rvw_device_tick(void*, uint64_t, uint64_t*);
int main(int argc, char** argv) {
  auto* dpi = rvw_device_open(argv[1], "{}", 123);
  assert(dpi);
  uint64_t value = 0;
  assert(rvw_device_read(dpi, 0, 8, &value) == 0 && value == 123);
  assert(rvw_device_tick(dpi, 8, &value) == 0 && value == 1);
  assert(rvw_device_read(dpi, 0, 9, &value) == 1);
  rvw_device_close(dpi);
  assert(rvw_device_open("/nonexistent/rvw-plugin.so", "{}", 1) == nullptr);
  riscvsim::DevicePlugin a(argv[1], "{}", 317);
  assert(a.read(0, 8) == 317);
  a.tick(8); a.write(0, 8, 123, 255);
  auto saved = a.snapshot();
  riscvsim::DevicePlugin fresh(argv[1], "{}", 1);
  assert(fresh.interrupts() == 0);
  fresh.restore(saved);
  assert(fresh.interrupts() == 1 && fresh.read(0, 8) == 123);
  bool rejected = false;
  try { fresh.restore({1}); } catch (...) { rejected = true; }
  assert(rejected);
}
'''


def test_native_plugin_load_and_fresh_device_restore(tmp_path):
    compiler = shutil.which('c++')
    if not compiler: pytest.skip('C++ compiler required')
    plugin, main = tmp_path / 'plugin.cpp', tmp_path / 'main.cpp'
    plugin.write_text(PLUGIN); main.write_text(MAIN)
    library, exe = tmp_path / 'device.so', tmp_path / 'test'
    flags = ['-std=c++17', '-I' + str(HEADER)]
    for args in ([compiler, *flags, '-shared', '-fPIC', str(plugin), '-o', str(library)],
                 [compiler, *flags, str(main), str(HEADER / 'DeviceDpi.cpp'), '-o', str(exe), *(['-ldl'] if os.uname().sysname == 'Linux' else [])],
                 [str(exe), str(library)]):
        result = run_group(['nice', '-n', '10', *args], timeout=30, capture=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr


def test_verilator_dpi_device_binding(tmp_path):
    verilator, compiler = shutil.which('verilator'), shutil.which('c++')
    if not verilator or not compiler or not shutil.which('make'):
        pytest.skip('Verilator, C++ and make required')
    plugin = tmp_path / 'plugin.cpp'; plugin.write_text(PLUGIN)
    library = tmp_path / 'device.so'
    built = run_group(['nice', '-n', '10', compiler, '-std=c++17', '-I' + str(HEADER),
        '-shared', '-fPIC', str(plugin), '-o', str(library)], timeout=30, capture=True, text=True)
    assert built.returncode == 0, built.stderr
    rtl = tmp_path / 'tb.sv'
    rtl.write_text(r'''
module tb;
import "DPI-C" function chandle rvw_device_open(input string library_path,
    input string config_json, input longint unsigned seed);
import "DPI-C" function void rvw_device_close(input chandle device);
import "DPI-C" function int rvw_device_read(input chandle device,
    input longint unsigned offset, input int unsigned bytes, output longint unsigned value);
import "DPI-C" function int rvw_device_write(input chandle device,
    input longint unsigned offset, input int unsigned bytes,
    input longint unsigned value, input longint unsigned mask);
import "DPI-C" function int rvw_device_tick(input chandle device,
    input longint unsigned cycle, output longint unsigned interrupts);
chandle device;
longint unsigned value;
string path;
initial begin
  if (!$value$plusargs("device=%s", path)) $fatal(1, "missing device");
  device = rvw_device_open(path, "{}", 317);
  if (device == null) $fatal(1, "open");
  if (rvw_device_read(device, 0, 8, value) != 0 || value != 317) $fatal(1, "seed");
  if (rvw_device_write(device, 0, 8, 123, 255) != 0) $fatal(1, "write");
  if (rvw_device_read(device, 0, 8, value) != 0 || value != 123) $fatal(1, "read");
  if (rvw_device_tick(device, 8, value) != 0 || value != 1) $fatal(1, "irq");
  rvw_device_close(device);
  $display("RVW_PASS"); $finish;
end
endmodule
''')
    obj = tmp_path / 'obj'
    built = run_group(['nice', '-n', '10', verilator, '--binary', '--top-module', 'tb',
        '--Mdir', str(obj), str(rtl), str(HEADER / 'DeviceDpi.cpp'), '-o', 'dpi-test'],
        timeout=120, capture=True, text=True)
    assert built.returncode == 0, built.stdout + built.stderr
    run = run_group(['nice', '-n', '10', str(obj / 'dpi-test'), '+device=' + str(library)],
                    timeout=10, capture=True, text=True)
    assert run.returncode == 0 and 'RVW_PASS' in run.stdout, run.stdout + run.stderr
