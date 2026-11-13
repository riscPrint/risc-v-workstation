import importlib.util
import os
from pathlib import Path
import re
import pytest


def fixture():
    rtl=os.environ.get('RVW_VEX_ENGINE_RTL');elf=os.environ.get('RVW_VEX_ENGINE_ELF')
    if not rtl or not elf:pytest.skip('captured VexTop RTL and ELF must be selected explicitly')
    path=Path(__file__).resolve().parents[1]/'four-state-probe.py'
    spec=importlib.util.spec_from_file_location('four_state_probe',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module,Path(rtl),Path(elf)


def test_whole_core_x_reset_and_known_reset_recovery(tmp_path):
    module,rtl,elf=fixture()
    report=module.run(rtl,elf,tmp_path/'baseline')
    assert report['status']=='pass'
    assert report['counts']['retired']==17
    assert report['counts']['reset_x']>=1
    assert report['counts']['active_x']==0
    assert report['counts']['inactive_x']>0


def test_active_retirement_x_is_never_a_pass(tmp_path):
    module,rtl,elf=fixture()
    altered,count=re.subn(r'assign rvfi_rd_wdata = [^;]+;', "assign rvfi_rd_wdata = 32'bx;",rtl.read_text())
    assert count==1
    bad=tmp_path/'VexTop.v';bad.write_text(altered)
    report=module.run(bad,elf,tmp_path/'active-x')
    assert report['status']!='pass' and report['counts']['active_x']>0
