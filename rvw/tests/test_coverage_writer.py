from pathlib import Path
import os
import subprocess
import pytest


@pytest.mark.parametrize('flags', ['verilator --coverage-line --coverage-per-instance', '--coverage-per-instance'])
def test_spinal_writer_preserves_hierarchy_once(tmp_path, flags):
    root = Path(__file__).resolve().parents[2]
    wrapper = tmp_path / 'VUnit__spinalWrapper.cpp'
    wrapper.write_text('void close(){VerilatedCov::write("coverage.dat");}\n')
    metadata = tmp_path / 'VUnit__verFiles.dat'
    metadata.write_text(f'C "{flags}"\n')
    make = tmp_path / 'make'
    make.write_text('#!/bin/sh\nexit 0\n')
    make.chmod(0o755)
    env = {**os.environ, 'RISCVSIM_MAKE': str(make)}
    script = root / 'RiscvSim/scripts/make-jobs.sh'
    for _ in range(2):
        subprocess.run([str(script), '-C', str(tmp_path), '-j2'], env=env, check=True)
    text = wrapper.read_text()
    assert text.count('forcePerInstance(true)') == 1
    assert text.count('VerilatedCov::write("coverage.dat")') == 1
    assert text.index('forcePerInstance(true)') < text.index('VerilatedCov::write')


@pytest.mark.parametrize('flags', ['--coverage-line', '--coverage-per-instance --no-coverage-per-instance'])
def test_shared_counter_writer_keeps_the_native_collapse_rule(tmp_path, flags):
    root = Path(__file__).resolve().parents[2]
    wrapper = tmp_path / 'VUnit__spinalWrapper.cpp'
    original = 'void close(){VerilatedCov::write("coverage.dat");}\n'
    wrapper.write_text(original)
    (tmp_path / 'VUnit__verFiles.dat').write_text(f'C "{flags}"\n')
    make = tmp_path / 'make'
    make.write_text('#!/bin/sh\nexit 0\n')
    make.chmod(0o755)
    subprocess.run([str(root / 'RiscvSim/scripts/make-jobs.sh'), '-C', str(tmp_path)],
                   env={**os.environ, 'RISCVSIM_MAKE': str(make)}, check=True)
    assert wrapper.read_text() == original
