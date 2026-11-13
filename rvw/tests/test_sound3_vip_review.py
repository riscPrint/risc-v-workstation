"""Conformance evidence checks must also run under Python optimization."""
from pathlib import Path
import subprocess
import sys
import pytest

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]
PROTOCOLS=('apb','ahb','axi','axis','clock_reset','coherent','gpio','i2c','interrupt','jtag','spi','sram','stress','tilelink','uart','wishbone')
SCRIPT=r'''
import importlib.util,sys
from pathlib import Path
from types import SimpleNamespace
path,out,valid=sys.argv[1:]
spec=importlib.util.spec_from_file_location('fixture_smoke',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.unpack=lambda *a:Path(out)/'unused-library'
def fake(argv,**kwargs):
    code=0;text=''
    if '--binary' not in argv and valid=='yes':
        if '+buggy' in argv:code=1;text='AXI_READ_DATA'
        elif '+bad_manager' in argv:code=1;text='AXI_WLAST'
        else:text='RVW_AXI_DONE\nUVM_ERROR :    0\nUVM_FATAL :    0\n'
    kwargs['stdout'].write(text)
    return SimpleNamespace(returncode=code,timed_out=False)
module.run_group=fake
sys.argv=['smoke','--out',out,'--archive','unused']
module.main()
'''

@pytest.mark.parametrize('protocol',PROTOCOLS)
def test_optimized_smoke_refuses_absent_evidence(tmp_path,protocol):
    path=ROOT/'Uvm/vip'/protocol/'smoke.py'
    result=subprocess.run([sys.executable,'-O','-c',SCRIPT,str(path),str(tmp_path/'out'),'no'],capture_output=True,text=True)
    assert result.returncode!=0, result.stdout
    assert 'AssertionError' in result.stderr
    assert ' native:' not in result.stdout

@pytest.mark.parametrize('optimized',[None,'-O','-OO'])
def test_guard_accepts_complete_positive_and_negative_receipts(tmp_path,optimized):
    path=ROOT/'Uvm/vip/axi/smoke.py'
    result=subprocess.run([sys.executable,*([optimized] if optimized else []),'-c',SCRIPT,str(path),str(tmp_path/'out'),'yes'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert '3 good runs and 6 expected diagnostic failures' in result.stdout


def test_generated_profile_keeps_failed_checks_active(tmp_path):
    script=r'''
import sys,types
from rvw.uvm.profiles import PYTHON
sys.modules['cocotb']=types.ModuleType('cocotb')
pyuvm=types.ModuleType('pyuvm');pyuvm.test=lambda:lambda cls:cls;pyuvm.uvm_test=object
sys.modules['pyuvm']=pyuvm
scenario=types.ModuleType('scenario');scenario.run=lambda _:None;sys.modules['scenario']=scenario
namespace={}
exec(compile(PYTHON.replace('AGENT_MODULE','rvw.vip.axi'),'generated','exec',optimize=2),namespace)
services=namespace['Services'](None,{})
services.checked(False,'expected failure')
'''
    result=subprocess.run([sys.executable,'-O','-c',script],capture_output=True,text=True)
    assert result.returncode!=0
    assert 'AssertionError: expected failure' in result.stderr

@pytest.mark.parametrize('module,constant',[('profiles','PYTHON'),('scaffold','TEST'),('composed','TEST')])
def test_generated_templates_keep_runtime_guards(module,constant):
    import ast
    import importlib
    source=getattr(importlib.import_module('rvw.uvm.'+module),constant)
    compile(source,'generated bench','exec',optimize=2)
    assert not any(isinstance(n,ast.Assert) for n in ast.walk(ast.parse(source)))
    assert 'require_evidence(' in source


def test_declared_template_keeps_runtime_guards(tmp_path,monkeypatch):
    import ast
    from rvw.vip import declared
    monkeypatch.setattr(declared,'load',lambda *a:{'buses':[{'name':'stream'}]})
    path=tmp_path/'bench.py'
    declared.skeleton(None,path,None)
    source=path.read_text()
    compile(source,'declared bench','exec',optimize=2)
    assert not any(isinstance(n,ast.Assert) for n in ast.walk(ast.parse(source)))
    assert source.count('require_evidence(')==2


def test_vip_harnesses_do_not_use_optimizable_verdict_assertions():
    import ast
    for path in (ROOT/'Uvm/vip').rglob('*.py'):
        assert not any(isinstance(n,ast.Assert) for n in ast.walk(ast.parse(path.read_text()))),path


def test_double_optimization_refuses_absent_evidence(tmp_path):
    path=ROOT/'Uvm/vip/axi/smoke.py'
    result=subprocess.run([sys.executable,'-OO','-c',SCRIPT,str(path),str(tmp_path/'out'),'no'],capture_output=True,text=True)
    assert result.returncode!=0
    assert 'AssertionError' in result.stderr
