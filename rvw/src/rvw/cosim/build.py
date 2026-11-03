"""Build the native shim from one C8 input set."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import shlex
import tempfile

from rvw.common.capture import Capture, CaptureError
from rvw.common.proc import run_group


FLAGS = ['-std=c++20', '-O2', '-fPIC', '-shared']


def build_id(inputs):
    return sha256(json.dumps(inputs, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def build(source, output, prefix=None, compiler=None):
    source, output = Path(source).absolute(), Path(output).absolute()
    prefix = Path(prefix or os.environ.get('SPIKE_PREFIX', '/opt/homebrew')).absolute()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.rvw-shim-', dir=output.parent) as temporary:
        work = Path(temporary)
        capture = Capture(work / 'inputs')
        shim = capture.file(source)
        headers = {name: capture.tree(prefix / 'include' / name, git=False)
                   for name in ('riscv', 'fesvr', 'softfloat', 'fdt')}
        library = next((prefix / 'lib' / name for name in ('libriscv.so', 'libriscv.dylib', 'libriscv.a')
                        if (prefix / 'lib' / name).is_file()), prefix / 'lib/libriscv.so')
        libraries = {'riscv': capture.file(library),
                     'disasm': capture.file(prefix / 'lib/libdisasm.a'),
                     'fesvr': capture.file(prefix / 'lib/libfesvr.a')}
        # Keep the package/source label with the captured binary hashes. This is
        # provenance supplied by the install, not an independent binary attestation.
        spike_identity = {"version": None, "revision": None, "origin": "external"}
        source_info = prefix / 'share/rvw/spike-source.json'
        receipt = library.resolve().parents[1] / 'INSTALL_RECEIPT.json'
        if source_info.is_file():
            spike_identity = json.loads(capture.file(source_info).copy.read_text())
        elif receipt.is_file():
            package = json.loads(capture.file(receipt).copy.read_text())
            spike_identity.update(origin='homebrew',
                                  version=package['source']['versions']['stable'],
                                  tap_git_head=package['source'].get('tap_git_head'))
            sbom = receipt.with_name('sbom.spdx.json')
            if sbom.is_file():
                capture.file(sbom)
        # The Python builder and shell entry point affect compilation too.
        capture.file(Path(__file__))
        capture.file(Path(__file__).resolve().parents[4] / 'Cosim/build.sh')
        env = {k: v for k, v in capture.env('PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL',
                                           'SDKROOT', 'DEVELOPER_DIR', 'MACOSX_DEPLOYMENT_TARGET',
                                           'SYSTEMROOT').items() if v is not None}
        cxx = capture.tool(compiler or os.environ.get('CXX', 'c++'))
        flags = [*FLAGS, '-MMD', '-MF', '@dependencies', '-I@headers', '-DRVW_SHIM_SOURCE_SHA256=@source_sha256',
                 '-DRVW_SHIM_BUILD_SHA256=@build_id', '@source', '@riscv', '@disasm', '@fesvr',
                 '-Wl,-rpath,' + str(library.parent), '-o', '@output']
        inputs = {'schema': 'rvw.spike-build-inputs/1', 'capture': capture.record(),
                  'source': shim.source, 'libraries': {name: item.source for name, item in libraries.items()},
                  'flags': flags, 'spike_identity': spike_identity}
        identity = build_id(inputs)
        include = work / 'include'
        for name, tree in headers.items():
            shutil.copytree(tree.copy, include / name)
        binary = work / 'librvw_spike.so'
        args = [str(cxx.path), *FLAGS, '-MMD', '-MF', str(work / 'dependencies.d'), '-I' + str(include),
                '-DRVW_SHIM_SOURCE_SHA256="' + shim.sha256 + '"',
                '-DRVW_SHIM_BUILD_SHA256="' + identity + '"', str(shim.copy),
                *(str(item.copy) for item in libraries.values()),
                '-Wl,-rpath,' + str(library.parent), '-o', str(binary)]
        result = run_group(args, capture=True, timeout=120, env=env)
        if result.timed_out or result.returncode:
            raise ValueError(f'shim compiler failed ({result.returncode}): {result.stderr}')
        # Guard the private execution inputs too. A compiler wrapper may be writable
        # by the same user, but cannot change copies and still earn a build binding.
        execution = [(shim.copy, shim), *((item.copy, item) for item in libraries.values())]
        execution.extend((include / name / item.copy.relative_to(tree.copy), item)
                         for name, tree in headers.items() for item in tree.files)
        expected_headers = {str(path.resolve()) for path, _ in execution}
        dependencies = (work / 'dependencies.d').read_text().replace('\\\n', '')
        target, separator, names = dependencies.partition(':')
        consumed = shlex.split(names)
        if not separator or not target or not consumed:
            raise CaptureError('input_not_captured:shim_headers', 'compiler did not report header dependencies')
        # Apple clang lists SDKSettings.json in -MMD output alongside user headers.
        # It belongs to the same installed SDK assumption as excluded system headers.
        sdk_roots = (Path('/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs'),
                     Path('/Library/Developer/CommandLineTools/SDKs'))
        def sdk_metadata(name):
            path = Path(name).absolute()
            return path.name == 'SDKSettings.json' and any(path.is_relative_to(root) for root in sdk_roots)
        outside = [name for name in consumed
                   if str(Path(name).resolve()) not in expected_headers and not sdk_metadata(name)]
        if outside:
            raise CaptureError('input_not_captured:shim_headers', f'compiler used headers outside the captured inputs: {outside}')
        for path, item in execution:
            if sha256(path.read_bytes()).hexdigest() != item.sha256:
                raise CaptureError('input_not_captured:shim_build', f'compiler changed private input: {path}')
        capture.verify_tools()
        built = capture.file(binary)
        manifest = {'schema': 'rvw.spike-build/1', 'shim_version': 4,
                    'shim_source_sha256': shim.sha256, 'shim_sha256': built.sha256,
                    'spike_library': libraries['riscv'].resolved,
                    'spike_library_sha256': libraries['riscv'].sha256,
                    'spike_headers': headers['riscv'].resolved,
                    'build_id': identity, 'build_inputs': inputs, 'spike_identity': spike_identity}
        staged_manifest = work / 'manifest.json'
        staged_manifest.write_text(json.dumps(manifest, indent=2) + '\n')
        os.replace(binary, output)
        os.replace(staged_manifest, Path(str(output) + '.manifest.json'))
    return manifest


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        build(args.source, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
    print(args.output)


if __name__ == '__main__':
    main()
