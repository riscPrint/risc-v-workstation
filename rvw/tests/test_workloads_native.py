"""Bounded native compiler check for workload source path reproducibility."""
import shutil

import pytest

from rvw.workloads import core

pytestmark = pytest.mark.slow


def test_default_flags_remove_absolute_source_paths(tmp_path):
    cc = shutil.which('riscv64-unknown-elf-gcc')
    if not cc:
        pytest.skip('RV64 GCC is not installed')
    argv = core.load()['workloads'][0]['build']
    # Use the pinned prefix-map policy on a small C source. __FILE__ also occurs
    # in Embench assertions. Different roots must not change the object bytes.
    flags = [arg for arg in argv if arg.startswith('-ffile-prefix-map=')]
    hashes = []
    for directory in ('first', 'second-longer-name'):
        root = tmp_path / directory
        root.mkdir()
        source = root / 'probe.c'
        source.write_text('const char *volatile source_file = __FILE__;\n'
                          'int main(void) { return source_file[0]; }\n')
        shutil.copy(core.ASSETS / 'start.S', root / 'start.S')
        shutil.copy(core.ASSETS / 'link.ld', root / 'link.ld')
        obj = root / 'probe.elf'
        mapping = {'source': str(root), 'assets': str(root / 'assets')}
        core.command([cc, '-g0', *[f.format_map(mapping) for f in flags],
                      '-march=rv64gc', '-mabi=lp64d', '-mcmodel=medany',
                      '-nostdlib', '-T', str(root / 'link.ld'), str(source),
                      str(root / 'start.S'), '-o', str(obj)])
        hashes.append(core.digest(obj))
    assert hashes[0] == hashes[1]
