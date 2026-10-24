"""Native compiler pinning keeps the selected command's driver mode."""
import os
import json
import shlex
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from rvw.common.proc import run_group
from test_native_identity import helper, native


@pytest.mark.parametrize('alias', ['clang++', 'g++'])
def test_pinned_compiler_keeps_cxx_driver_mode(tmp_path, monkeypatch, alias):
    module = helper('native-identity.py')
    compiler = shutil.which('clang++')
    assert compiler, 'This regression requires the installed Clang C++ compiler'
    homebrew = Path('/opt/homebrew/opt/llvm/bin/clang++')
    if homebrew.is_file():
        compiler = str(homebrew)
    lookup = tmp_path / 'lookup'
    lookup.mkdir()
    (lookup / alias).symlink_to(compiler)
    monkeypatch.setenv('PATH', str(lookup) + os.pathsep + os.environ['PATH'])
    # Select both commands in verilated.mk, as a normal Verilator installation does.
    root = tmp_path / 'verilator'
    (root / 'include').mkdir(parents=True)
    (root / 'include/verilated.mk').write_text(f'CXX = {alias}\nLINK = {alias}\n')
    original = module.run_group
    def version_probe(command, **kwargs):
        if command[-1:] == ['-V']:
            return SimpleNamespace(returncode=0, stdout=f'VERILATOR_ROOT = {root}\n')
        return original(command, **kwargs)
    monkeypatch.setattr(module, 'run_group', version_probe)
    record = json.loads(json.dumps(module.collect()))
    assert record['tools']['compiler']['path'] == str(Path(compiler).resolve())
    source = tmp_path / 'driver.cpp'
    source.write_text('int main() { volatile int *p = new int(7); int n = *p; delete p; return n != 7; }\n')
    output = tmp_path / 'driver'
    invoked = []

    def java_probe(command, **kwargs):
        # Inspect the launch boundary and exercise the exact make command it supplies.
        environment = kwargs['env']
        for name in ['RISCVSIM_PINNED_CXX', 'RISCVSIM_PINNED_LINK']:
            selected = Path(environment[name])
            result = original([str(selected), str(source), '-o', str(output)],
                              capture=True, timeout=30)
            assert result.returncode == 0, result.stderr
            assert selected.name == alias
            assert selected.resolve() == Path(record['tools']['compiler']['path'])
            invoked.append(selected)
        # The wrapper must pass the same paths to make.
        makefile = tmp_path / 'driver.mk'
        makefile.write_text('all:\n\t$(LINK) ' + shlex.quote(str(source)) + ' -o ' + shlex.quote(str(output)) + '\n')
        result = original([record['make_wrapper_path'], '-f', str(makefile)],
                          env=environment, capture=True, timeout=30)
        assert result.returncode == 0, result.stderr
        assert original([str(output)], capture=True, timeout=10).returncode == 0
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module, 'run_group', java_probe)
    assert module.launch(record, tmp_path, []) == 0
    assert len(invoked) == 2
    assert not list(tmp_path.glob('native-bin.*'))


def test_native_provenance_keeps_execution_paths(native):
    record = native.module.collect()
    published = record['provenance']
    assert published['sha256'] == record['sha256']
    assert published['environment'] == record['environment']
    assert published['tools'] == record['tools']
    assert 'capture' not in published and 'file_stamps' not in published
    assert all('stamp' not in item for item in published['tools'].values())
