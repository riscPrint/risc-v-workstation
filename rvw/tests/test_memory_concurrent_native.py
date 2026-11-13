from pathlib import Path
import shutil
import pytest
from rvw.memory.concurrent_native import assembly, smoke


def test_completion_wrapper_retains_each_generated_program():
    text = assembly(7, 3, 20)
    assert text.count('_start:') == 1
    assert text.count('  ret\n') == 3
    assert 'rvw_wait_2:' in text and '  sd t1, 0(t0)' in text
    assert 'lr.d.aq' in text and 'amoadd.d' in text


def test_native_three_hart_completion(tmp_path):
    compiler = shutil.which('riscv64-unknown-elf-gcc') or '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
    if not Path(compiler).is_file() or not shutil.which('spike'):
        pytest.skip('RISC-V GCC and Spike are required')
    result = smoke(tmp_path, seed=7, harts=3, length=20, gcc=compiler, timeout=30)
    assert result['status'] == 'pass', result
    assert result['ordering'] == 'not_checked' and result['rtl'] == 'not_run'
    assert len(result['elf_sha256']) == 64


def test_timeout_cannot_become_a_concurrent_ordering_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import rvw.memory.concurrent_native as native
    monkeypatch.setattr(native.shutil, 'which', lambda name: '/tool/'+name)
    def run(command, **kwargs):
        if '-o' in command:
            Path(command[command.index('-o')+1]).write_bytes(b'\x7fELFtest')
            return SimpleNamespace(returncode=0, timed_out=False, stdout='', stderr='')
        return SimpleNamespace(returncode=124, timed_out=True, stdout='', stderr='')
    monkeypatch.setattr(native, 'run_group', run)
    result = native.smoke(tmp_path)
    assert result['status'] == 'inconclusive' and result['ordering'] == 'not_checked'
