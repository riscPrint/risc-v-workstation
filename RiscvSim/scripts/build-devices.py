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


def python_library(config=sysconfig.get_config_var):
    name = config('LDLIBRARY')
    if name:
        for key in ('LIBDIR', 'PYTHONFRAMEWORKPREFIX'):
            directory = config(key)
            if directory and (library := Path(directory) / name).is_file():
                return library
    raise ValueError('shared CPython library required')


def python_load_name(listing, library):
    for line in listing.splitlines()[1:]:
        name = line.strip().split(' (')[0]
        if Path(name).name == library.name:
            return name
    raise ValueError('Python library is absent from the linked dependencies')


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    output = args.out.resolve()
    if output.exists(): raise ValueError('output already exists')
    cc = shutil.which('c++')
    if not cc: raise ValueError('missing C++ compiler')
    header = Path(__file__).resolve().parents[1] / 'src/main/cpp'
    library = python_library()
    output.parent.mkdir(parents=True, exist_ok=True)
    darwin = platform.system() == 'Darwin'
    source = Path(__file__).resolve().parents[2] / 'rvw/src'
    # Embed the interpreter home and rvw/src: the library then needs no PYTHONHOME/PYTHONPATH.
    embedded = [f'-DRVW_DEVICE_PYTHON_HOME="{sys.base_prefix}"', f'-DRVW_DEVICE_PYTHON_PATH="{source}"']
    step([cc, '-std=c++17', '-shared', '-fPIC', *embedded, '-I'+sysconfig.get_path('include'),
          '-I'+str(header), str(header/'PythonDevices.cpp'), str(library),
          '-Wl,-rpath,'+str(library.parent),
          *(['-Wl,-headerpad_max_install_names'] if darwin else []), '-o', str(output)])
    if darwin:
        linked = step(['otool', '-L', str(output)])
        name = python_load_name(linked, library)
        step(['install_name_tool', '-change', name, str(library), str(output)])
    print('Library: '+str(output))
    print('Embedded Python home: '+sys.base_prefix)
    print('Embedded module path: '+str(source))
    print('Leave PYTHONHOME and PYTHONPATH unset; the library is isolated from them.')

if __name__ == '__main__': main()
