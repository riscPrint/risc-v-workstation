"""Preserve a requested wave before the next native test cleans its directory."""
import os
from pathlib import Path
import subprocess
import sys
import pytest

pytestmark = pytest.mark.fast
LAUNCH = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/boot-slices.sh'


@pytest.mark.parametrize('produced,code', [(True, 0), (False, 0), (True, 7)])
def test_requested_wave_is_preserved_or_refused(tmp_path, produced, code):
    root, commands = tmp_path / 'root', tmp_path / 'bin'
    (root / 'scripts').mkdir(parents=True)
    commands.mkdir()
    lock = root / 'scripts/with-lock.sh'
    lock.write_text('#!/bin/sh\nshift\nexec "$@"\n')
    lock.chmod(0o755)
    java = commands / 'java'
    java.write_text(f'''#!{sys.executable}
import os,sys
from pathlib import Path
Path(sys.argv[-4]).mkdir()
wave=Path(os.environ['RVW_BOOT_WORK'])/'VexiiRiscv/test/wave.fst'
wave.parent.mkdir(parents=True)
if {produced!r}: wave.write_bytes(b'bounded wave')
sys.exit({code})
''')
    java.chmod(0o755)
    cp = tmp_path / 'classpath.txt'
    cp.write_text('/fake/scala-library.jar')
    native, out = tmp_path / 'native', tmp_path / 'out'
    env = dict(os.environ, RVW_HOME=str(root), VEXIIRISCV=str(tmp_path),
               RVW_BOOT_CLASSPATH=str(cp), RVW_BOOT_WORK=str(native), RVW_BOOT_WAVE='100:200',
               PATH=str(commands)+os.pathsep+os.environ['PATH'])
    env.pop('RVW_BOOT_FREEZE_RUNTIME', None)
    result = subprocess.run(['bash', str(LAUNCH), 'elf', 'payloads', 'map', str(out),
                             'checkpoint', 'restore', '200'], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == (code or (0 if produced else 2)), result.stderr
    if produced and not code:
        assert (out / 'wave.fst').read_bytes() == b'bounded wave'
        assert not (native / 'VexiiRiscv/test/wave.fst').exists()
    else:
        assert not (out / 'wave.fst').exists()
