"""The Vexii database launcher must honor a private core lock."""
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def test_database_uses_selected_private_lock(tmp_path):
    scripts = tmp_path/'scripts'; scripts.mkdir()
    lock = scripts/'with-lock.sh'
    lock.write_text('#!/bin/bash\nprintf "%s\\n" "$1" > "$LOCK_LOG"\n')
    lock.chmod(0o755)
    log = tmp_path/'lock-name'
    env = dict(os.environ, RVW_HOME=str(tmp_path), VEXIIRISCV=str(tmp_path),
               RVW_VEX_LOCK='vex-vexii', LOCK_LOG=str(log))
    result = subprocess.run(['bash', str(ROOT/'examples/vexiiriscv/rvw/build-db.sh'),
                             'rv32im', str(tmp_path/'design.db')], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert log.read_text().strip() == 'vex-vexii'
