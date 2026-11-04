"""Launcher guards. Native generation is measured separately."""
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[2]/'scripts/riscv-dv-pygen.py'


@pytest.mark.parametrize('instructions,timeout', [('0','1'),('1001','1'),('1','nan'),('1','0')])
def test_invalid_bounds(tmp_path, instructions, timeout):
    out=tmp_path/'out'
    r=subprocess.run([sys.executable,str(SCRIPT),'--checkout',str(tmp_path),
                      '--target','rv32imc','--seed','48','--instructions',instructions,
                      '--timeout',timeout,'--out',str(out)],capture_output=True,text=True)
    assert r.returncode == 2 and not out.exists()
    assert 'instructions must be' in r.stderr


def test_wrong_generator_revision(tmp_path):
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    subprocess.run(['git','-C',str(tmp_path),'-c','user.name=Fixture',
                    '-c','user.email=fixture@example.com','commit','--allow-empty','-qm','fixture'],check=True)
    out=tmp_path/'out'
    r=subprocess.run([sys.executable,str(SCRIPT),'--checkout',str(tmp_path),
                      '--target','rv32imc','--seed','48','--out',str(out)],capture_output=True,text=True)
    assert r.returncode == 2 and not out.exists()
    assert 'generator checkout must be clean' in r.stderr


def test_timeout_cannot_report_generated_even_with_zero_exit(tmp_path, monkeypatch):
    import importlib.util
    import json
    from types import SimpleNamespace
    from rvw.common import proc
    spec = importlib.util.spec_from_file_location('pygen_launcher', SCRIPT)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    monkeypatch.setattr(launcher.subprocess, 'check_output',
                        lambda argv, **kw: '' if 'status' in argv else launcher.REVISION+'\n')
    out = tmp_path/'out'
    def timed_out(*args, **kwargs):
        (out/'program_0.S').write_text('addi x1,x0,1\n')
        return SimpleNamespace(returncode=0, timed_out=True)
    monkeypatch.setattr(proc, 'run_group', timed_out)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--checkout', str(tmp_path),
                        '--target', 'rv32imc', '--seed', '48', '--out', str(out)])
    assert launcher.main() == 2
    assert json.loads((out/'generation.json').read_text())['status'] == 'error'
