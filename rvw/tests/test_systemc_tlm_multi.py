"""Two real SystemC initiators share the generic blocking memory target."""
import os
from pathlib import Path
import shlex
import shutil
import pytest
from rvw.common.proc import run_group


def test_two_initiators(tmp_path):
    cxx=shutil.which(os.environ.get('CXX','c++'))
    if not cxx: pytest.skip('native C++ compiler required')
    home=os.environ.get('SYSTEMC_HOME')
    if home:
        flags=['-I'+str(Path(home)/'include'), '-L'+str(Path(home)/'lib'),
               '-Wl,-rpath,'+str(Path(home)/'lib'), '-lsystemc']
    else:
        pkg=shutil.which('pkg-config')
        if not pkg: pytest.skip('SystemC development library required')
        found=run_group([pkg,'--cflags','--libs','systemc'],timeout=10,capture=True)
        if found.returncode: pytest.skip('SystemC development library required')
        flags=shlex.split(found.stdout)
    root=Path(__file__).resolve().parents[2]
    binary=tmp_path/'multi'
    built=run_group(['nice','-n','10',cxx,'-std=c++17',
        '-I'+str(root/'RiscvSim/src/main/cpp'),
        str(root/'RiscvSim/examples/systemc/multi.cpp'),*flags,'-o',str(binary)],
        timeout=90,capture=True)
    assert built.returncode==0,built.stdout+built.stderr
    ran=run_group(['nice','-n','10',str(binary)],timeout=15,capture=True)
    assert ran.returncode==0,ran.stdout+ran.stderr
    assert 'RVW_TLM_MULTI_PASS initiators=2 reads=4 writes=4' in ran.stdout
