"""Exercise the example's actual C++ device model without an RTL build."""
from pathlib import Path
import shutil
import pytest
from rvw.common.proc import run_group
pytestmark = pytest.mark.fast


def test_ibex_device_registers_and_irq_levels(tmp_path):
    compiler=shutil.which('c++')
    if not compiler: pytest.skip('C++ compiler is not installed')
    root=Path(__file__).resolve().parents[2]
    source=tmp_path/'devices.cpp'
    source.write_text('''#include "devices.h"
#include <cassert>
int main() {
 Devices d;
 assert(d.levels()==0);
 assert(Devices::mapped(0x0200bffc));
 assert(!Devices::mapped(0x10000000));
 d.write(0x02000000,1,1); assert(d.levels()==8);
 d.write(0x02000000,0,2); assert(d.read(0x02000000)==1);
 d.write(0x02000000,0,1); assert(d.levels()==0);
 d.write(0x02004000,3,15); d.write(0x02004004,0,15);
 d.tick();d.tick(); assert(d.levels()==0);
 d.tick(); assert(d.levels()==128);
 d.write(0x02004000,5,1); assert(d.read(0x02004000)==5);
 assert(d.levels()==0);
 d.write(0x0c000004,0x80000800,15); assert(d.levels()==2048);
 d.write(0x0c000004,0x800,1); assert(d.levels()==2048);
 d.write(0x0c000004,0x800,15); assert(d.levels()==0);
 d.write(0x0200bff8,0xffffffff,15); d.write(0x0200bffc,0,15);
 d.tick(); assert(d.read(0x0200bff8)==0 && d.read(0x0200bffc)==1);
}
''')
    exe=tmp_path/'devices'
    built=run_group(['nice','-n','15',compiler,'-std=c++17','-I',str(root/'examples/ibex/rvw'),str(source),'-o',str(exe)],capture=True,timeout=30)
    assert built.returncode==0, built.stderr
    checked=run_group([str(exe)],capture=True,timeout=5)
    assert checked.returncode==0,checked.stderr
