import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='session')
def engine(tmp_path_factory):
    binary = tmp_path_factory.mktemp('component-build') / 'branch-sim'
    subprocess.run(['c++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                    str(ROOT / 'branch_sim.cc'), '-o', str(binary)], check=True)
    return binary

