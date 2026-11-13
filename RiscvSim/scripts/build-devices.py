#!/usr/bin/env python3
"""Build the optional DeviceApiV1 CPython library with this interpreter."""
import argparse
from pathlib import Path
import platform
import shutil
import sys
import sysconfig
from rvw.common.proc import run_group


def step(args):
    result = run_group(['nice', '-n', '10', *args], timeout=30, capture=True)
    if result.returncode or result.timed_out:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    output = args.out.resolve()
    if output.exists(): raise ValueError('output already exists')
    cc = shutil.which('c++')
    if not cc: raise ValueError('missing C++ compiler')
    header = Path(__file__).resolve().parents[1] / 'src/main/cpp'
    library = Path(sysconfig.get_config_var('LIBDIR')) / sysconfig.get_config_var('LDLIBRARY')
    if not library.is_file(): raise ValueError('shared CPython library required')
    output.parent.mkdir(parents=True, exist_ok=True)
    darwin = platform.system() == 'Darwin'
    step([cc, '-std=c++17', '-shared', '-fPIC', '-I'+sysconfig.get_path('include'),
          '-I'+str(header), str(header/'PythonDevices.cpp'), str(library),
          '-Wl,-rpath,'+str(library.parent),
          *(['-Wl,-headerpad_max_install_names'] if darwin else []), '-o', str(output)])
    if darwin:
        linked = step(['otool', '-L', str(output)])
        name = next(line.strip().split(' (')[0] for line in linked.splitlines() if 'libpython' in line)
        step(['install_name_tool', '-change', name, str(library), str(output)])
    print('Library: '+str(output))
    print('PYTHONHOME: '+sys.base_prefix)
    print('Set PYTHONPATH to the selected workstation rvw/src directory.')

if __name__ == '__main__': main()
