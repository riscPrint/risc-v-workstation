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
