"""Compile and load native fixtures at the shared C8 race boundaries."""
from model_fixtures import load_shim
import ctypes
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys

import pytest
from race_injection import race_injector
from rvw.common.proc import run_group
from rvw.cosim import build as builder, spike


SOURCE = r'''
#include <riscv/options.h>
extern "C" int dependency_value();
extern "C" unsigned rvw_shim_version() { return 7; }
extern "C" const char* rvw_shim_source_sha256() { return RVW_SHIM_SOURCE_SHA256; }
extern "C" const char* rvw_shim_build_sha256() { return RVW_SHIM_BUILD_SHA256; }
extern "C" int observed_value() { return CAPTURED_VALUE + dependency_value(); }
'''


@pytest.fixture
def inputs(tmp_path):
    prefix = tmp_path / 'prefix'
    for name in ('riscv', 'fesvr', 'softfloat', 'fdt'):
        (prefix / 'include' / name).mkdir(parents=True)
    header = prefix / 'include/riscv/options.h'
    header.write_text('#define CAPTURED_VALUE 7\n')
    (prefix / 'lib').mkdir()
    cc = tmp_path / 'dependency.cc'
    cc.write_text('extern "C" int dependency_value(){return 1;}\n'
                  'extern "C" void _ZN11processor_t4stepEm(){}\n')
    library = prefix / 'lib/libriscv.dylib'
    cxx = shutil.which('c++')
    assert cxx
    obj = tmp_path / 'dependency.o'
    linker_id = '-Wl,-install_name,' if sys.platform == 'darwin' else '-Wl,-soname,'
    for argv in ([cxx, '-c', str(cc), '-o', str(obj)],
                 [cxx, '-shared', '-fPIC', str(cc), linker_id + str(library), '-o', str(library)],
                 ['ar', 'rcs', str(prefix / 'lib/libdisasm.a'), str(obj)],
                 ['ar', 'rcs', str(prefix / 'lib/libfesvr.a'), str(obj)]):
        result = run_group(argv, timeout=30, capture=True)
        assert result.returncode == 0, result.stderr
    source = tmp_path / 'spike_shim.cc'
    source.write_text(SOURCE)
    return source, header, library, prefix, tmp_path / 'shim.so'


@pytest.mark.parametrize('target', ['source', 'header', 'library', 'archive'])
@pytest.mark.parametrize('revert', [False, True])
def test_compiler_uses_captured_build_inputs(inputs, race_injector, target, revert):
    source, header, library, prefix, output = inputs
    path = {'source': source, 'header': header, 'library': library,
            'archive': prefix / 'lib/libdisasm.a'}[target]
    changed = {'source': SOURCE.replace('return CAPTURED_VALUE + dependency_value()', 'return 99').encode(),
               'header': b'#define CAPTURED_VALUE 99\n', 'library': b'not a library',
               'archive': b'not an archive'}[target]
    original = source.read_bytes()
    original_library = library.read_bytes()
    edit = race_injector.file(builder, 'run_group', path, changed, replace=True, revert=revert)
    manifest = builder.build(source, output, prefix)
    assert edit.fired
    library.write_bytes(original_library)
    assert ctypes.CDLL(str(output)).observed_value() == 8
    assert manifest['shim_source_sha256'] == sha256(original).hexdigest()
    assert manifest['build_id'] == builder.build_id(manifest['build_inputs'])
    assert manifest['shim_sha256'] == sha256(output.read_bytes()).hexdigest()


def test_runtime_refuses_build_record_tampering(inputs):
    source, _, _, prefix, output = inputs
    manifest = builder.build(source, output, prefix)
    manifest['build_inputs']['flags'].append('-DWRONG_BUILD=1')
    Path(str(output) + '.manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='build.*binding.*rebuild'):
        load_shim(output, source)


def test_runtime_loads_matching_build_binding(inputs):
    source, _, _, prefix, output = inputs
    builder.build(source, output, prefix)
    assert load_shim(output, source).observed_value() == 8


def test_runtime_refuses_rebound_manifest(inputs):
    source, _, _, prefix, output = inputs
    manifest = builder.build(source, output, prefix)
    manifest['build_inputs']['flags'].append('-DWRONG_BUILD=1')
    manifest['build_id'] = builder.build_id(manifest['build_inputs'])
    Path(str(output) + '.manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='embedded build input binding'):
        load_shim(output, source)


@pytest.mark.parametrize('revert', [False, True])
def test_compiler_change_preserves_previous_output(inputs, race_injector, revert):
    source, _, _, prefix, output = inputs
    compiler = output.parent / 'compiler'
    compiler.write_text('#!/bin/sh\nexec /usr/bin/c++ "$@"\n')
    compiler.chmod(0o755)
    output.write_bytes(b'previous library')
    manifest = Path(str(output) + '.manifest.json')
    manifest.write_bytes(b'previous manifest')
    race = race_injector.file(builder, 'run_group', compiler,
                              compiler.read_bytes() + b'# changed compiler\n', replace=True, revert=revert)
    from rvw.common.capture import CaptureError
    with pytest.raises(CaptureError, match='tool'):
        builder.build(source, output, prefix, compiler)
    assert race.fired
    assert output.read_bytes() == b'previous library'
    assert manifest.read_bytes() == b'previous manifest'


@pytest.mark.parametrize('revert', [False, True])
def test_uncaptured_transitive_header_refuses_publication(inputs, race_injector, revert):
    from rvw.common.capture import CaptureError
    source, _, _, prefix, output = inputs
    external = source.parent / 'external.h'
    external.write_text('#define EXTERNAL 1\n')
    source.write_text(f'#include "{external}"\n' + SOURCE)
    race = race_injector.file(builder, 'run_group', external, b'#define EXTERNAL 2\n',
                              replace=True, revert=revert)
    with pytest.raises(CaptureError, match='shim_headers'):
        builder.build(source, output, prefix)
    assert race.fired and not output.exists()
    assert not Path(str(output) + '.manifest.json').exists()


def test_source_version_is_bound_to_build(inputs):
    source, _, _, prefix, output = inputs
    metadata = prefix / 'share/rvw/spike-source.json'
    metadata.parent.mkdir(parents=True)
    identity = {'version': '1.1.1-dev', 'revision': 'test-revision', 'origin': 'fixture'}
    metadata.write_text(json.dumps(identity))
    manifest = builder.build(source, output, prefix)
    assert manifest['spike_identity'] == identity
    assert manifest['build_inputs']['spike_identity'] == identity
    assert any(row['source'] == str(metadata) for row in manifest['build_inputs']['capture']['files'])


def test_runtime_refuses_source_version_label_tampering(inputs):
    source, _, _, prefix, output = inputs
    manifest = builder.build(source, output, prefix)
    manifest['spike_identity']['revision'] = 'wrong-revision'
    Path(str(output) + '.manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='build.*binding.*rebuild'):
        load_shim(output, source)


@pytest.mark.parametrize('soname', [None, 'libriscv.so.1'])
def test_versioned_library_survives_build_cleanup(inputs, soname):
    source, _, old_library, prefix, output = inputs
    library = prefix / 'lib/libriscv.so.1.2'
    cxx = shutil.which('c++')
    cc = source.parent / 'dependency.cc'
    # On macOS use its native install name. Linux also tests Spike's no-SONAME build.
    identity = (['-Wl,-install_name,@rpath/libriscv.so.1'] if sys.platform == 'darwin'
                else (['-Wl,-soname,' + soname] if soname else []))
    result = run_group([cxx, '-shared', '-fPIC', str(cc), *identity, '-o', str(library)],
                       capture=True, timeout=30)
    assert result.returncode == 0, result.stderr
    old_library.unlink()
    (prefix / 'lib/libriscv.so.1').symlink_to(library.name)
    (prefix / 'lib/libriscv.so').symlink_to('libriscv.so.1')
    original = library.read_bytes()
    manifest = builder.build(source, output, prefix)
    assert not list(output.parent.glob('.rvw-shim-*'))
    # The installed self-check must also load after the temporary build is gone.
    result = run_group([sys.executable, '-c',
                        'import ctypes,sys; assert ctypes.CDLL(sys.argv[1]).observed_value() == 8',
                        str(output)], capture=True, timeout=30)
    assert result.returncode == 0, result.stderr
    # Prove that loading uses the capture, without a fallback to the live prefix.
    from rvw.common.capture import Capture
    capture = Capture(source.parent / 'runtime-inputs')
    prepared = spike.capture_shim(capture, output, source)
    library.unlink()
    lib = spike.load_shim(prepared)
    assert lib.observed_value() == 8
    assert manifest['spike_library_sha256'] == sha256(original).hexdigest()
    assert any(row['symlinks'] for row in manifest['build_inputs']['capture']['files']
               if row['source'] == str(prefix / 'lib/libriscv.so'))
    assert Path(prepared['dependency']['copy']).read_bytes() == original
