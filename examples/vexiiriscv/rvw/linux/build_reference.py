"""Build the project Linux reference profile against the same Spike as the shim."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from rvw.common.capture import Capture
from rvw.common.proc import run_group
from rvw.cosim.spike import capture_shim


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--shim', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    capture = Capture(a.out / 'inputs')
    shim = capture_shim(capture, a.shim)
    source = capture.file(Path(__file__).with_name('reference-profile.cc'))
    capture.file(Path(__file__))
    prefix = Path(shim['manifest_data']['spike_headers']).parent.parent
    include = a.out / 'include'
    include.mkdir()
    for name in ('riscv', 'fesvr', 'softfloat', 'fdt'):
        tree = capture.tree(prefix / 'include' / name, git=False)
        shutil.copytree(tree.copy, include / name)
    cxx = capture.tool(os.environ.get('CXX', 'c++'))
    library = a.out / 'vexii-linux.so'
    spike = Path(shim['dependency']['copy'])
    command = [str(cxx.path), '-std=c++20', '-O2', '-shared', '-fPIC', '-I'+str(include.resolve()),
               str(source.copy), str(spike), '-o', str(library.resolve())]
    run = run_group(command, capture=True, timeout=120)
    (a.out / 'build.log').write_text(run.stdout+run.stderr)
    if run.returncode:
        raise ValueError('reference extension build failed; see build.log')
    capture.verify_tools()
    result = dict(schema='rvw.vexii-reference-build/1', name='rvw_vexii_linux', physical_bits=32,
                  pmp_regions=8, source_sha256=source.sha256,
                  library_sha256=hashlib.sha256(library.read_bytes()).hexdigest(),
                  spike_library_sha256=shim['dependency']['sha256'], capture=capture.record())
    Path(str(library)+'.json').write_text(json.dumps(result, indent=2)+'\n')
    print(library)


if __name__ == '__main__':
    main()
