"""Boot the exact prepared bytes under QEMU; this is not RTL evidence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import pytest
from rvw.common.proc import run_group


def test_prepared_linux_marker_and_shutdown(tmp_path):
    source = os.environ.get('RVW_LINUX_INPUTS')
    qemu = shutil.which('qemu-system-riscv64')
    if not source or not qemu:
        pytest.skip('set RVW_LINUX_INPUTS to prepared boot inputs and install QEMU')
    source = Path(source)
    receipt = json.loads((source / 'inputs.json').read_text())
    for name, digest in receipt['sha256'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    manifest = json.loads((source / 'payloads.json').read_text())
    command = [qemu, '-machine', 'virt', '-m', '32M', '-smp', '1', '-nographic', '-bios', 'none',
               '-device', f'loader,file={source}/reset.elf,cpu-num=0']
    for row in manifest['payloads']:
        command += ['-device', f'loader,file={source / row["file"]},addr={row["address"]},force-raw=on']
    result = run_group(command, capture=True, timeout=60)
    (tmp_path / 'qemu.log').write_text(result.stdout + result.stderr)
    assert not result.timed_out and result.returncode == 0, result.stdout[-2000:] + result.stderr
    assert 'RVW_LINUX_USERSPACE' in result.stdout
    assert 'Power down' in result.stdout
