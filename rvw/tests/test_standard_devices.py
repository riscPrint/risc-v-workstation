import json
from pathlib import Path
import os
import shutil
import sys
import sysconfig
import pytest
from rvw.common.proc import run_group
from rvw.sim.devices import Device


def device(kind, **options):
    return Device(json.dumps(dict(model=kind, **options)))


def test_console_block_masks_and_restore():
    c = device('htif-console')
    c.write(0, 8, (0x101 << 48) | 65, 255)
    assert c.model.output == b'A' and c.read(8, 8) == 0x101 << 48
    b = device('simple-block', image_hex='0011223344556677')
    saved = b.snapshot()
    b.write(2, 2, 0xabcd, 3)
    assert b.read(2, 2) == 0xabcd
    b.restore(saved)
    assert b.read(2, 2) == 0x3322
    with pytest.raises(ValueError): b.write(0, 2, 1, 1)
    with pytest.raises(ValueError): b.read(8, 1)
    with pytest.raises(ValueError): c.restore(saved)


def test_uart_and_timer_continuation():
    u = device('ns16550')
    assert u.read(5, 1) == 0x60
    u.write(1, 1, 2, 1)
    assert u.interrupts() == 1
    saved = u.snapshot()
    assert u.read(2, 1) == 2 and u.interrupts() == 0
    u.restore(saved)
    assert u.interrupts() == 1
    t = device('aclint', map=dict(mtime=0, mtimecmp=[8], msip=[16],
                                 reset_mtime=0, reset_mtimecmp=2**64-1), cycles_per_tick=3)
    t.write(8, 8, 2, 255)
    t.tick(5)
    assert t.interrupts() == 0
    saved = t.snapshot()
    t.tick(6)
    assert t.interrupts() == 2
    t.restore(saved)
    assert t.interrupts() == 0
    t.tick(6)
    t.write(16, 4, 1, 15)
    assert t.interrupts() == 3


def test_plic_claim_and_restored_gateway():
    p = device('plic', map=dict(priority=0, pending=0x1000, enable=0x2000,
        enable_stride=128, context=0x200000, context_stride=4096,
        sources=31, contexts=1, max_priority=7))
    p.write(4, 4, 1, 15)
    p.write(0x2000, 4, 2, 15)
    p.set_level(1, True)
    saved = p.snapshot()
    assert p.interrupts() == 1 and p.read(0x200004, 4) == 1
    assert p.interrupts() == 0
    p.restore(saved)
    assert p.interrupts() == 1


def test_real_plugin_abi(tmp_path):
    cc = shutil.which('c++')
    if not cc: pytest.skip('C++ compiler required')
    root = Path(__file__).resolve().parents[2]
    headers = root / 'RiscvSim/src/main/cpp'
    libdir = Path(sysconfig.get_config_var('LIBDIR'))
    library = sysconfig.get_config_var('LDLIBRARY')
    lib = libdir / library
    if not lib.exists(): pytest.skip('shared CPython library required')
    plugin = tmp_path / 'devices.so'
    result = run_group([cc, '-std=c++17', '-shared', '-fPIC', '-I'+sysconfig.get_path('include'),
        '-I'+str(headers), str(headers/'PythonDevices.cpp'), str(lib),
        '-Wl,-rpath,'+str(libdir), *(['-Wl,-headerpad_max_install_names'] if os.uname().sysname == 'Darwin' else []), '-o', str(plugin)], timeout=30, capture=True)
    assert result.returncode == 0, result.stderr
    if os.uname().sysname == 'Darwin':
        # uv's portable CPython has an absolute build-time install name.
        import subprocess
        linked = subprocess.check_output(['otool', '-L', str(plugin)], text=True)
        name = next(line.strip().split(' (')[0] for line in linked.splitlines() if 'libpython' in line)
        subprocess.run(['install_name_tool', '-change', name, str(lib), str(plugin)], check=True)
    main = tmp_path/'main.cpp'
    main.write_text('''#include "DevicePlugin.h"
#include <cassert>
int main(int n, char** a) {
  riscvsim::DevicePlugin p(a[1], "{\\"model\\":\\"ns16550\\"}", 1);
  assert(p.read(5,1)==0x60); p.write(1,1,2,1); assert(p.interrupts()==1);
  auto s=p.snapshot(); assert(p.read(2,1)==2); assert(p.interrupts()==0);
  riscvsim::DevicePlugin fresh(a[1], "{\\"model\\":\\"ns16550\\"}", 1);
  fresh.restore(s); assert(fresh.interrupts()==1);
}''')
    exe = tmp_path/'test'
    env = dict(os.environ, PYTHONPATH=str(root/'rvw/src'), PYTHONHOME=sys.base_prefix)
    for args in ([cc, '-std=c++17', '-I'+str(headers), str(main), '-o', str(exe),
                  *(['-ldl'] if os.uname().sysname == 'Linux' else [])], [str(exe), str(plugin)]):
        result = run_group(args, env=env, timeout=30, capture=True)
        assert result.returncode == 0, result.stdout + result.stderr


def test_project_options_select_every_model():
    root = Path(__file__).resolve().parents[2]
    options = json.loads((root/'examples/qemu-linux/sim-plugin-options.json').read_text())
    assert {v['model'] for v in options.values()} == {'ns16550', 'clint', 'plic', 'htif-console', 'simple-block'}
    for config in options.values():
        original = Device(json.dumps(config))
        original.tick(11)
        saved = original.snapshot()
        fresh = Device(json.dumps(config))
        fresh.restore(saved)
        assert fresh.snapshot() == saved


def test_device_maps_take_hex_strings_and_refuse_rounded_floats():
    # A host that writes JSON numbers as doubles turns 2**64-1 into 1.8446744073709552e19.
    layout = dict(mtime=0, mtimecmp=[8], msip=[16], reset_mtime=0)
    rounded = json.loads(json.dumps(float(2**64 - 1)))
    with pytest.raises(ValueError, match='exact'):
        device('clint', map=dict(layout, reset_mtimecmp=rounded), cycles_per_tick=1)
    t = device('clint', map=dict(layout, mtimecmp=['0x8'], reset_mtimecmp='0xffffffffffffffff'),
               cycles_per_tick=1)
    assert t.model.compare == [2**64 - 1]
    p = device('plic', map=dict(priority='0', pending='0x1000', enable=0x2000, enable_stride=0x80,
                                context='0x200000', context_stride=0x1000, sources=1, contexts=1))
    assert p.model.map.context == 0x200000
    with pytest.raises(ValueError, match='boolean'):
        device('plic', map=dict(priority=0, pending=0x1000, enable=0x2000, enable_stride=0x80,
                                context=0x200000, context_stride=0x1000, sources=True, contexts=1))


def test_built_library_needs_no_python_environment(tmp_path):
    cc = shutil.which('c++')
    if not cc: pytest.skip('C++ compiler required')
    root = Path(__file__).resolve().parents[2]
    plugin = tmp_path / 'devices.so'
    built = run_group([sys.executable, str(root/'RiscvSim/scripts/build-devices.py'), '--out', str(plugin)],
                      timeout=120, capture=True)
    if built.returncode and 'shared CPython library required' in built.stderr:
        pytest.skip('shared CPython library required')
    assert built.returncode == 0, built.stdout + built.stderr
    main = tmp_path/'main.cpp'
    main.write_text('''#include "DevicePlugin.h"
#include <cassert>
int main(int n, char** a) {
  riscvsim::DevicePlugin p(a[1], "{\\"model\\":\\"ns16550\\"}", 1);
  assert(p.read(5,1)==0x60);
}''')
    exe = tmp_path/'test'
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONHOME', 'PYTHONPATH')}
    compiled = run_group([cc, '-std=c++17', '-I'+str(root/'RiscvSim/src/main/cpp'), str(main), '-o', str(exe),
                          *(['-ldl'] if os.uname().sysname == 'Linux' else [])], env=env, timeout=60, capture=True)
    assert compiled.returncode == 0, compiled.stderr
    for extra in ({}, {'PYTHONHOME': str(tmp_path / 'absent'), 'PYTHONPATH': str(tmp_path / 'absent')}):
        result = run_group([str(exe), str(plugin)], env=dict(env, **extra), timeout=30, capture=True)
        assert result.returncode == 0, result.stdout + result.stderr
