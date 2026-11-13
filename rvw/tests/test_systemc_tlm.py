"""Real Verilator --sc model connected to a blocking TLM-2 memory target."""
import os
from pathlib import Path
import shutil
import pytest
from rvw.common.proc import run_group
from native_sdks import systemc_home


def test_verilator_systemc_and_tlm_memory(tmp_path):
    verilator=shutil.which('verilator');pkg=shutil.which('pkg-config')
    if not verilator:pytest.skip('native Verilator required')
    home=systemc_home()
    if not home:
        if not pkg:pytest.skip('SYSTEMC_HOME or pkg-config required')
        found=run_group([pkg,'--exists','systemc'],timeout=10,capture=True)
        if found.returncode:pytest.skip('SystemC development library required')
    def variable(name):
        r=run_group([pkg,'--variable='+name,'systemc'],timeout=10,capture=True)
        assert r.returncode==0,r.stderr
        return r.stdout.strip()
    root=Path(__file__).resolve().parents[2]
    example=root/'RiscvSim/examples/systemc'
    include=str(Path(home)/'include') if home else variable('includedir')
    lib=str(Path(home)/'lib') if home else variable('libdir')
    assert (Path(include)/'systemc').is_file(),include
    env=dict(os.environ,SYSTEMC_INCLUDE=include,SYSTEMC_LIBDIR=lib)
    command=[verilator,'--sc','--exe','--build','-j','2','--top-module','MemoryMaster',
        '--prefix','RVWTlmDevice','--Mdir',str(tmp_path/'obj'),'-Wno-fatal',
        '-CFLAGS','-std=c++17 -I'+str(root/'RiscvSim/src/main/cpp'),
        '-LDFLAGS','-Wl,-rpath,'+env['SYSTEMC_LIBDIR'],str(example/'MemoryMaster.sv'),str(example/'main.cpp')]
    built=run_group(['nice','-n','10',*command],env=env,timeout=90,capture=True)
    (tmp_path/'build.log').write_text(built.stdout+built.stderr)
    assert built.returncode==0,built.stdout+built.stderr
    ran=run_group(['nice','-n','10',str(tmp_path/'obj/RVWTlmDevice')],env=env,timeout=15,capture=True)
    (tmp_path/'run.log').write_text(ran.stdout+ran.stderr)
    assert ran.returncode==0,ran.stdout+ran.stderr
    assert 'RVW_SYSTEMC_TLM_PASS rtl_writes=1 rtl_reads=1' in ran.stdout
